from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_assistant.models import Conversation, Message
from apps.ai_assistant.services import build_messages_payload, get_guardrail_response
from apps.ai_assistant.services.assistant_runtime import build_knowledge_context
from apps.ai_assistant.services.chat import stream_conversation_reply
from apps.ai_assistant.services.internal_tool_runtime import ToolIntent
from apps.ai_assistant.services.native_tool_chat import run_native_tool_chat_reply
from apps.ai_assistant.services.nlu_planner import PlannedToolCall, plan_tool_call
from apps.ai_assistant.services.tool_router import route_tool_call
from apps.booking.models import Appointment, AppointmentStatus
from apps.scheduling.models import ScheduleSlot, TimeShift


class AIAssistantRefactorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="assistant_user",
            password="secret",
        )
        self.conversation = Conversation.objects.create(user=self.user, title="")

    def test_build_knowledge_context_uses_retrieval_service(self):
        with patch(
            "apps.ai_assistant.services.assistant_runtime.retrieve_context_for_question",
            return_value=[
                {
                    "id": 1,
                    "source_type": "procedure",
                    "source_id": "10",
                    "title": "Quy trinh A",
                    "section_title": "Quy trinh A",
                    "content": "Noi dung A",
                    "similarity": 0.92,
                }
            ],
        ):
            context = build_knowledge_context(
                "hoi gi do",
                user=self.user,
                profile=Conversation.PROFILE_STAFF,
            )

        self.assertIn("Quy trinh A", context)
        self.assertIn("Noi dung A", context)

    def test_stream_conversation_reply_saves_assistant_message(self):
        with (
            patch(
                "apps.ai_assistant.services.chat.build_knowledge_context",
                return_value="Context noi bo",
            ),
            patch(
                "apps.ai_assistant.services.chat.run_native_tool_chat_reply",
                return_value=None,
            ),
            patch(
                "apps.ai_assistant.services.chat.stream_completion",
                return_value=iter(["Xin ", "chao"]),
            ),
            patch(
                "apps.ai_assistant.services.chat.auto_generate_title",
                return_value="Hoi tham",
            ),
        ):
            events = list(
                stream_conversation_reply(
                    conversation=self.conversation,
                    user=self.user,
                    user_content="Cho toi biet quy trinh",
                )
            )

        self.assertTrue(any("[DONE]" in event for event in events))
        self.assertEqual(
            list(self.conversation.messages.values_list("role", flat=True)),
            [Message.ROLE_USER, Message.ROLE_ASSISTANT],
        )
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "Hoi tham")

    def test_stream_conversation_reply_uses_native_tool_loop_when_available(self):
        with (
            patch(
                "apps.ai_assistant.services.chat.build_knowledge_context",
                return_value="Context noi bo",
            ),
            patch(
                "apps.ai_assistant.services.chat.route_pre_llm_action",
                return_value=None,
            ),
            patch(
                "apps.ai_assistant.services.chat.run_native_tool_chat_reply",
                return_value="Co 2 lich hen da xac nhan ngay 24/04/2026.",
            ),
            patch(
                "apps.ai_assistant.services.chat.stream_completion",
                side_effect=AssertionError("stream_completion should not be called"),
            ),
            patch(
                "apps.ai_assistant.services.chat.auto_generate_title",
                return_value="Lich hen 24 04",
            ),
        ):
            events = list(
                stream_conversation_reply(
                    conversation=self.conversation,
                    user=self.user,
                    user_content="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                )
            )

        self.assertTrue(any("[DONE]" in event for event in events))
        self.assertTrue(
            self.conversation.messages.filter(
                role=Message.ROLE_ASSISTANT,
                content__contains="2 lich hen",
            ).exists()
        )

    def test_legacy_service_exports_still_work(self):
        payload = build_messages_payload([], knowledge_context="Nguon 1")
        self.assertEqual(payload[0]["role"], "system")
        self.assertTrue(any("Nguon 1" in item["content"] for item in payload))
        self.assertTrue(get_guardrail_response("Ban la model gi?"))

    def test_route_tool_call_counts_confirmed_appointments_for_explicit_date(self):
        morning_slot = ScheduleSlot.objects.create(
            date=date(2026, 4, 24),
            shift=TimeShift.MORNING,
            slot_type="INDIVIDUAL",
            capacity=5,
            booked_count=1,
        )
        afternoon_slot = ScheduleSlot.objects.create(
            date=date(2026, 4, 24),
            shift=TimeShift.AFTERNOON,
            slot_type="INDIVIDUAL",
            capacity=5,
            booked_count=1,
        )
        Appointment.objects.create(
            schedule_slot=morning_slot,
            status=AppointmentStatus.CONFIRMED,
        )
        Appointment.objects.create(
            schedule_slot=afternoon_slot,
            status=AppointmentStatus.CONFIRMED,
        )
        Appointment.objects.create(
            schedule_slot=ScheduleSlot.objects.create(
                date=date(2026, 4, 25),
                shift=TimeShift.MORNING,
                slot_type="INDIVIDUAL",
                capacity=5,
                booked_count=1,
            ),
            status=AppointmentStatus.CONFIRMED,
        )

        with patch(
            "apps.ai_assistant.services.nlu_planner.complete_openai_chat_with_tools",
            return_value={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "clinicos_data_query",
                            "arguments": (
                                '{"tool_name":"appointments","operation":"count","status":"CONFIRMED",'
                                '"target_date":"2026-04-24","today_only":false,"active_only":false,"limit":5}'
                            ),
                        },
                    }
                ],
            },
        ):
            response = route_tool_call(
                user=self.user,
                question="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                profile=Conversation.PROFILE_STAFF,
            )

        self.assertIsNotNone(response)
        self.assertIn("2", response)
        self.assertIn("24/04/2026", response)

    def test_plan_tool_call_returns_structured_intent(self):
        with patch(
            "apps.ai_assistant.services.nlu_planner.complete_openai_chat_with_tools",
            return_value={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "clinicos_data_query",
                            "arguments": (
                                '{"tool_name":"appointments","operation":"count","status":"CONFIRMED",'
                                '"target_date":"2026-04-24","today_only":false,"active_only":false,"limit":3}'
                            ),
                        },
                    }
                ],
            },
        ):
            planned = plan_tool_call(
                user=self.user,
                question="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                profile=Conversation.PROFILE_STAFF,
            )

        self.assertIsNotNone(planned.intent)
        self.assertEqual(planned.intent.tool_name, "appointments")
        self.assertEqual(planned.intent.operation, "count")
        self.assertEqual(planned.intent.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(planned.intent.target_date, date(2026, 4, 24))

    def test_plan_tool_call_normalizes_tool_name_aliases(self):
        with patch(
            "apps.ai_assistant.services.nlu_planner.complete_openai_chat_with_tools",
            return_value={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_3",
                        "type": "function",
                        "function": {
                            "name": "clinicos_data_query",
                            "arguments": (
                                '{"tool_name":"lich hen","operation":"dem","status":"da xac nhan",'
                                '"target_date":"2026-04-24","today_only":false,"active_only":false,"limit":3}'
                            ),
                        },
                    }
                ],
            },
        ):
            planned = plan_tool_call(
                user=self.user,
                question="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                profile=Conversation.PROFILE_STAFF,
            )

        self.assertIsNotNone(planned.intent)
        self.assertEqual(planned.intent.tool_name, "appointments")
        self.assertEqual(planned.intent.operation, "count")
        self.assertEqual(planned.intent.status, AppointmentStatus.CONFIRMED)

    def test_run_native_tool_chat_reply_executes_round_trip(self):
        messages_payload = [
            {"role": "system", "content": "Ban la tro ly."},
            {"role": "user", "content": "Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?"},
        ]

        with (
            patch(
                "apps.ai_assistant.services.native_tool_chat.complete_openai_chat_with_tools",
                return_value={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_native_1",
                            "type": "function",
                            "function": {
                                "name": "clinicos_data_query",
                                "arguments": (
                                    '{"tool_name":"appointments","operation":"count","status":"CONFIRMED",'
                                    '"target_date":"2026-04-24","today_only":false,"active_only":false,"limit":5}'
                                ),
                            },
                        }
                    ],
                },
            ),
            patch(
                "apps.ai_assistant.services.native_tool_chat.execute_internal_tool",
                return_value="Hiện tại có 2 lịch hẹn đã xác nhận ngày 24/04/2026.",
            ),
            patch(
                "apps.ai_assistant.services.native_tool_chat.complete_openai_chat_message",
                return_value={
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "Ngày 24/04/2026 có 2 lịch hẹn đã xác nhận.",
                    },
                },
            ),
        ):
            reply = run_native_tool_chat_reply(
                user=self.user,
                question="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                profile=Conversation.PROFILE_STAFF,
                messages_payload=messages_payload,
            )

        self.assertEqual(reply, "Ngày 24/04/2026 có 2 lịch hẹn đã xác nhận.")
    def test_run_native_tool_chat_reply_falls_back_to_structured_planner(self):
        messages_payload = [
            {"role": "system", "content": "Ban la tro ly."},
            {"role": "user", "content": "Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?"},
        ]

        with (
            patch(
                "apps.ai_assistant.services.native_tool_chat.complete_openai_chat_with_tools",
                return_value=None,
            ),
            patch(
                "apps.ai_assistant.services.native_tool_chat.plan_tool_call",
                return_value=PlannedToolCall(
                    intent=ToolIntent(
                        tool_name="appointments",
                        operation="count",
                        status=AppointmentStatus.CONFIRMED,
                        target_date=date(2026, 4, 24),
                    )
                ),
            ),
            patch(
                "apps.ai_assistant.services.native_tool_chat.execute_internal_tool",
                return_value="Hien tai co 2 lich hen da xac nhan ngay 24/04/2026.",
            ),
        ):
            reply = run_native_tool_chat_reply(
                user=self.user,
                question="Ngay 24/04/2026 co bao nhieu ca dang ky kham da xac nhan?",
                profile=Conversation.PROFILE_STAFF,
                messages_payload=messages_payload,
            )

        self.assertEqual(reply, "Hien tai co 2 lich hen da xac nhan ngay 24/04/2026.")
