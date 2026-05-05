from __future__ import annotations

import time
from statistics import mean

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.models import Conversation
from apps.ai_assistant.services.internal_tool_runtime import execute_internal_tool
from apps.ai_assistant.services.llm_client import (
    complete_openai_chat_message,
    complete_openai_chat_with_tools,
    get_toolcall_candidate_models,
)
from apps.ai_assistant.services.nlu_planner import (
    _build_nlu_messages,
    extract_native_tool_payload,
    get_native_planning_tool_choice,
    get_native_planning_tools,
    parse_tool_payload,
)
from apps.ai_assistant.services.prompting import build_messages_payload


class Command(BaseCommand):
    help = "Benchmark native AI tool-calling across candidate models."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="", help="Username to execute permission-scoped tools.")
        parser.add_argument(
            "--profile",
            default=Conversation.PROFILE_STAFF,
            choices=[
                Conversation.PROFILE_CUSTOMER,
                Conversation.PROFILE_STAFF,
                Conversation.PROFILE_MANAGER,
            ],
            help="Assistant profile to benchmark.",
        )
        parser.add_argument(
            "--question",
            default="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
            help="Natural-language question to benchmark.",
        )
        parser.add_argument(
            "--models",
            default="",
            help="Comma-separated model list. Default uses configured candidate models.",
        )
        parser.add_argument("--repeats", type=int, default=2, help="Number of runs per model.")
        parser.add_argument("--planner-timeout", type=int, default=20, help="Timeout for planner tool call step.")
        parser.add_argument("--final-timeout", type=int, default=20, help="Timeout for final assistant response step.")

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        profile = options["profile"]
        question = (options["question"] or "").strip()
        repeats = max(1, int(options["repeats"]))
        planner_timeout = max(5, int(options["planner_timeout"]))
        final_timeout = max(5, int(options["final_timeout"]))

        user = self._resolve_user(username=username, profile=profile)
        models = self._resolve_models(raw_models=(options["models"] or "").strip())
        if not models:
            raise CommandError("No benchmark models available.")

        self.stdout.write(self.style.SUCCESS("AI native tool-calling benchmark"))
        self.stdout.write(f"Profile: {profile}")
        self.stdout.write(f"Question: {question}")
        self.stdout.write(f"User: {getattr(user, 'username', 'anonymous') if user else 'anonymous'}")
        self.stdout.write(f"Models: {', '.join(models)}")
        self.stdout.write(f"Repeats: {repeats}")
        self.stdout.write(f"Planner timeout: {planner_timeout}s")
        self.stdout.write(f"Final timeout: {final_timeout}s")

        results = []
        for model in models:
            model_result = self._benchmark_model(
                user=user,
                model=model,
                profile=profile,
                question=question,
                repeats=repeats,
                planner_timeout=planner_timeout,
                final_timeout=final_timeout,
            )
            results.append(model_result)

        self.stdout.write("\nResults:")
        for item in results:
            self.stdout.write(
                "- {model}: planner_ok={planner_ok}/{repeats}, final_ok={final_ok}/{repeats}, "
                "avg_planner={avg_planner:.2f}s, avg_final={avg_final:.2f}s".format(
                    model=item["model"],
                    planner_ok=item["planner_ok"],
                    final_ok=item["final_ok"],
                    repeats=repeats,
                    avg_planner=item["avg_planner"],
                    avg_final=item["avg_final"],
                )
            )

        winner = self._pick_winner(results)
        if winner:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nSuggested config:\n"
                    f"AI_TOOLCALL_MODEL={winner['model']}\n"
                    f"AI_TOOLCALL_TIMEOUT={planner_timeout}\n"
                    f"AI_TOOLCALL_FINAL_TIMEOUT={final_timeout}"
                )
            )
            fallback = next((item for item in results if item["model"] != winner["model"]), None)
            if fallback:
                self.stdout.write(f"AI_TOOLCALL_FALLBACK_MODEL={fallback['model']}")

    def _resolve_user(self, *, username: str, profile: str):
        if profile == Conversation.PROFILE_CUSTOMER:
            return None
        User = get_user_model()
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                raise CommandError(f"User not found: {username}")
            return user
        user = User.objects.order_by("id").first()
        if not user:
            raise CommandError("No user found for benchmark.")
        return user

    def _resolve_models(self, *, raw_models: str) -> list[str]:
        if raw_models:
            models = [item.strip() for item in raw_models.split(",") if item.strip()]
            seen = []
            for item in models:
                if item not in seen:
                    seen.append(item)
            return seen
        return get_toolcall_candidate_models()

    def _benchmark_model(
        self,
        *,
        user,
        model: str,
        profile: str,
        question: str,
        repeats: int,
        planner_timeout: int,
        final_timeout: int,
    ) -> dict:
        planner_times: list[float] = []
        final_times: list[float] = []
        planner_ok = 0
        final_ok = 0

        for _ in range(repeats):
            planner_elapsed, final_elapsed, planner_success, final_success = self._single_run(
                user=user,
                model=model,
                profile=profile,
                question=question,
                planner_timeout=planner_timeout,
                final_timeout=final_timeout,
            )
            planner_times.append(planner_elapsed)
            final_times.append(final_elapsed)
            planner_ok += int(planner_success)
            final_ok += int(final_success)

        return {
            "model": model,
            "planner_ok": planner_ok,
            "final_ok": final_ok,
            "avg_planner": mean(planner_times) if planner_times else 0.0,
            "avg_final": mean(final_times) if final_times else 0.0,
        }

    def _single_run(
        self,
        *,
        user,
        model: str,
        profile: str,
        question: str,
        planner_timeout: int,
        final_timeout: int,
    ) -> tuple[float, float, bool, bool]:
        planner_messages = _build_nlu_messages(question=question, profile=profile)
        planner_tools = get_native_planning_tools(profile)
        tool_choice = get_native_planning_tool_choice()

        planner_started = time.perf_counter()
        planner_message = complete_openai_chat_with_tools(
            planner_messages,
            tools=planner_tools,
            model=model,
            temperature=0.1,
            max_tokens=120,
            timeout=planner_timeout,
            tool_choice=tool_choice,
        )
        planner_elapsed = time.perf_counter() - planner_started
        if not planner_message:
            return planner_elapsed, 0.0, False, False

        payload = extract_native_tool_payload(planner_message)
        if not payload:
            return planner_elapsed, 0.0, False, False

        planned = parse_tool_payload(
            user=user,
            question=question,
            profile=profile,
            payload={"action": "tool_call", **payload},
        )
        if planned.intent is None:
            return planner_elapsed, 0.0, False, False

        planner_ok = True
        tool_result = execute_internal_tool(user=user, intent=planned.intent, profile=profile)
        if not tool_result:
            return planner_elapsed, 0.0, planner_ok, False

        chat_messages = build_messages_payload(
            conversation_messages=[],
            knowledge_context="",
            profile=profile,
            conversation_state="",
        )
        chat_messages.append({"role": "user", "content": question})
        chat_messages.append(
            {
                "role": "assistant",
                "content": (planner_message.get("content") or "").strip(),
                "tool_calls": planner_message.get("tool_calls") or [],
            }
        )
        first_tool_call = (planner_message.get("tool_calls") or [{}])[0]
        chat_messages.append(
            {
                "role": "tool",
                "tool_call_id": first_tool_call.get("id"),
                "content": tool_result,
            }
        )

        final_started = time.perf_counter()
        final_choice = complete_openai_chat_message(
            chat_messages,
            model=model,
            temperature=0.2,
            max_tokens=220,
            timeout=final_timeout,
        )
        final_elapsed = time.perf_counter() - final_started
        final_ok = bool(final_choice and ((final_choice.get("message") or {}).get("content") or "").strip())
        return planner_elapsed, final_elapsed, planner_ok, final_ok

    def _pick_winner(self, results: list[dict]) -> dict | None:
        successful = [item for item in results if item["final_ok"] > 0]
        if successful:
            return sorted(successful, key=lambda item: (-item["final_ok"], item["avg_final"], item["avg_planner"]))[0]
        planned = [item for item in results if item["planner_ok"] > 0]
        if planned:
            return sorted(planned, key=lambda item: (-item["planner_ok"], item["avg_planner"]))[0]
        return results[0] if results else None
