import json
import logging

from django.contrib import messages as django_messages
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from .models import Conversation, Message
from .permissions import AiAssistantAccessMixin
from .services import (
    auto_generate_title,
    build_messages_payload,
    stream_completion,
)

logger = logging.getLogger(__name__)


class ConversationListView(AiAssistantAccessMixin, ListView):
    template_name = "ai_assistant/index.html"
    context_object_name = "conversations"
    paginate_by = 30

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).order_by("-updated_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Trợ lý AI"
        return ctx


class ConversationNewView(AiAssistantAccessMixin, View):
    """Tạo cuộc hội thoại mới và redirect vào chat."""

    def post(self, request):
        conversation = Conversation.objects.create(user=request.user, title="")
        return redirect(reverse("ai_assistant:chat", kwargs={"pk": conversation.pk}))


class ConversationChatView(AiAssistantAccessMixin, View):
    template_name = "ai_assistant/chat.html"

    def get(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        all_messages = conversation.messages.exclude(role=Message.ROLE_SYSTEM).order_by(
            "created_at"
        )
        sidebar_conversations = Conversation.objects.filter(
            user=request.user
        ).order_by("-updated_at")[:30]
        return render(
            request,
            self.template_name,
            {
                "conversation": conversation,
                "chat_messages": all_messages,
                "sidebar_conversations": sidebar_conversations,
                "page_title": conversation.get_title_display(),
            },
        )


class ConversationDeleteView(AiAssistantAccessMixin, View):
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        conversation.delete()
        django_messages.success(request, "Đã xóa cuộc hội thoại.")
        return redirect(reverse("ai_assistant:index"))


class MessageStreamView(AiAssistantAccessMixin, View):
    """
    POST endpoint: nhận tin nhắn của user, stream phản hồi AI dưới dạng SSE.
    Frontend dùng fetch() với ReadableStream để đọc từng chunk.

    Request body (JSON):
        { "content": "..." }

    Response: text/event-stream
        data: <json-encoded-chunk>\n\n
        data: [DONE]\n\n
        data: [ERROR] <json-encoded-message>\n\n
    """

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

        try:
            body = json.loads(request.body)
            user_content = body.get("content", "").strip()
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Dữ liệu không hợp lệ."}, status=400)

        if not user_content:
            return JsonResponse({"error": "Nội dung không được để trống."}, status=400)

        user_msg = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content=user_content,
        )

        is_first_message = (
            conversation.messages.filter(role=Message.ROLE_USER).count() == 1
        )

        all_msgs = conversation.messages.exclude(role=Message.ROLE_SYSTEM).order_by(
            "created_at"
        )
        messages_payload = build_messages_payload(all_msgs)

        def event_stream():
            full_response_parts = []

            try:
                for chunk in stream_completion(messages_payload):
                    full_response_parts.append(chunk)
                    yield f"data: {json.dumps(chunk)}\n\n"

                assistant_content = "".join(full_response_parts).strip()

                if assistant_content:
                    Message.objects.create(
                        conversation=conversation,
                        role=Message.ROLE_ASSISTANT,
                        content=assistant_content,
                    )

                Conversation.objects.filter(pk=conversation.pk).update(
                    updated_at=timezone.now()
                )

                if is_first_message and not conversation.title:
                    title = auto_generate_title(user_content)
                    if title:
                        Conversation.objects.filter(pk=conversation.pk).update(
                            title=title
                        )

                yield "data: [DONE]\n\n"

            except RuntimeError as exc:
                logger.warning("AI stream RuntimeError: %s", exc)
                user_msg.delete()
                yield f"data: [ERROR] {json.dumps(str(exc))}\n\n"

            except Exception as exc:
                logger.exception("AI stream unexpected error: %s", exc)
                user_msg.delete()
                yield f"data: [ERROR] {json.dumps('Đã xảy ra lỗi không xác định.')}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class ConversationRenameView(AiAssistantAccessMixin, View):
    """AJAX: đổi tiêu đề cuộc hội thoại."""

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        try:
            body = json.loads(request.body)
            title = body.get("title", "").strip()[:200]
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Dữ liệu không hợp lệ."}, status=400)

        conversation.title = title
        conversation.save(update_fields=["title"])
        return JsonResponse({"ok": True, "title": conversation.get_title_display()})


class OllamaHealthView(AiAssistantAccessMixin, View):
    """
    AJAX GET: kiểm tra kết nối và trạng thái Ollama server.
    Trả về JSON { ok, model, base_url, model_loaded, available_models?, error? }
    """

    def get(self, request):
        import requests as http_requests
        from django.conf import settings

        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")

        try:
            resp = http_requests.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()

            available_models = [m.get("name") for m in data.get("models", []) if m.get("name")]

            model_loaded = any(
                m == model or m.startswith(model.split(":")[0])
                for m in available_models
            )

            return JsonResponse(
                {
                    "ok": True,
                    "model": model,
                    "model_loaded": model_loaded,
                    "available_models": available_models,
                    "base_url": base_url,
                }
            )

        except Exception as exc:
            return JsonResponse(
                {
                    "ok": False,
                    "model": model,
                    "base_url": base_url,
                    "error": str(exc),
                },
                status=503,
            )