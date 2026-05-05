import json

from django.contrib import messages as django_messages
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from .models import Conversation
from .permissions import ManagerAssistantAccessMixin, StaffAssistantAccessMixin
from .selectors import (
    get_conversation_for_session,
    get_conversation_for_user,
    list_conversation_messages,
    list_conversations_for_session,
    list_conversations_for_user,
)
from .services.chat import create_conversation, stream_conversation_reply
from .services.llm_client import check_ai_health
from .services.profiles import get_assistant_profile_config


def _ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


class ProfileContextMixin:
    profile = Conversation.PROFILE_MANAGER
    access_mixin = None

    def get_profile_config(self):
        return get_assistant_profile_config(self.profile)

    def get_profile_label(self) -> str:
        return self.get_profile_config().get("label", self.profile)

    def get_page_title(self) -> str:
        return self.get_profile_config().get("page_title", self.get_profile_label())

    def get_named_url(self, name: str, **kwargs) -> str:
        return reverse(f"ai_assistant:{self.profile}_{name}", kwargs=kwargs)

    def get_user(self, request):
        if self.profile == Conversation.PROFILE_CUSTOMER:
            return getattr(request, "user", None)
        return request.user

    def get_conversation(self, request, pk: int):
        if self.profile == Conversation.PROFILE_CUSTOMER:
            return get_conversation_for_session(
                pk=pk,
                session_key=_ensure_session_key(request),
                profile=self.profile,
            )
        return get_conversation_for_user(
            pk=pk,
            user=request.user,
            profile=self.profile,
        )

    def list_conversations(self, request, *, limit: int | None = None):
        if self.profile == Conversation.PROFILE_CUSTOMER:
            return list_conversations_for_session(
                session_key=_ensure_session_key(request),
                profile=self.profile,
                limit=limit,
            )
        return list_conversations_for_user(
            request.user,
            profile=self.profile,
            limit=limit,
        )

    def create_profile_conversation(self, request):
        kwargs = {"profile": self.profile}
        if self.profile == Conversation.PROFILE_CUSTOMER:
            kwargs["session_key"] = _ensure_session_key(request)
            kwargs["user"] = None
        else:
            kwargs["user"] = request.user
        return create_conversation(**kwargs)

    def get_common_context(self):
        return {
            "assistant_profile": self.profile,
            "assistant_label": self.get_profile_label(),
            "page_title": self.get_page_title(),
            "assistant_is_public": bool(self.get_profile_config().get("is_public")),
            "assistant_index_url": self.get_named_url("index"),
            "assistant_new_url": self.get_named_url("new"),
            "assistant_health_url": self.get_named_url("health"),
            "assistant_chat_url_name": f"ai_assistant:{self.profile}_chat",
            "assistant_delete_url_name": f"ai_assistant:{self.profile}_delete",
        }

    def build_chat_context(self, request, conversation):
        context = self.get_common_context()
        context.update(
            {
                "conversation": conversation,
                "chat_messages": list_conversation_messages(conversation),
                "sidebar_conversations": self.list_conversations(request, limit=30),
                "page_title": conversation.get_title_display(),
                "assistant_chat_url_name": f"ai_assistant:{self.profile}_chat",
                "assistant_stream_url": self.get_named_url("stream", pk=conversation.pk),
                "assistant_delete_url": self.get_named_url("delete", pk=conversation.pk),
                "assistant_rename_url": self.get_named_url("rename", pk=conversation.pk),
            }
        )
        return context


class AssistantIndexView(ProfileContextMixin, ListView):
    template_name = "ai_assistant/index.html"
    context_object_name = "conversations"
    paginate_by = 30

    def get_queryset(self):
        return self.list_conversations(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_common_context())
        return ctx


class CustomerAssistantIndexView(ProfileContextMixin, View):
    profile = Conversation.PROFILE_CUSTOMER

    def get(self, request):
        conversation = self.list_conversations(request, limit=1).first()
        if conversation is None:
            conversation = self.create_profile_conversation(request)
        return redirect(self.get_named_url("chat", pk=conversation.pk))


class StaffAssistantIndexView(StaffAssistantAccessMixin, AssistantIndexView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantIndexView(ManagerAssistantAccessMixin, AssistantIndexView):
    profile = Conversation.PROFILE_MANAGER


class AssistantNewView(ProfileContextMixin, View):
    def post(self, request):
        conversation = self.create_profile_conversation(request)
        return redirect(self.get_named_url("chat", pk=conversation.pk))


class CustomerAssistantNewView(AssistantNewView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantNewView(StaffAssistantAccessMixin, AssistantNewView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantNewView(ManagerAssistantAccessMixin, AssistantNewView):
    profile = Conversation.PROFILE_MANAGER


class AssistantChatView(ProfileContextMixin, View):
    template_name = "ai_assistant/chat.html"

    def get(self, request, pk):
        conversation = self.get_conversation(request, pk)
        if conversation is None:
            return redirect(self.get_named_url("index"))
        return render(request, self.template_name, self.build_chat_context(request, conversation))


class CustomerAssistantChatView(AssistantChatView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantChatView(StaffAssistantAccessMixin, AssistantChatView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantChatView(ManagerAssistantAccessMixin, AssistantChatView):
    profile = Conversation.PROFILE_MANAGER


class AssistantDeleteView(ProfileContextMixin, View):
    def post(self, request, pk):
        conversation = self.get_conversation(request, pk)
        if conversation is None:
            return redirect(self.get_named_url("index"))
        conversation.delete()
        if self.profile != Conversation.PROFILE_CUSTOMER:
            django_messages.success(request, "Da xoa cuoc hoi thoai.")
        return redirect(self.get_named_url("index"))


class CustomerAssistantDeleteView(AssistantDeleteView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantDeleteView(StaffAssistantAccessMixin, AssistantDeleteView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantDeleteView(ManagerAssistantAccessMixin, AssistantDeleteView):
    profile = Conversation.PROFILE_MANAGER


class AssistantMessageStreamView(ProfileContextMixin, View):
    def post(self, request, pk):
        conversation = self.get_conversation(request, pk)
        if conversation is None:
            return JsonResponse({"error": "Khong tim thay cuoc hoi thoai."}, status=404)

        try:
            body = json.loads(request.body)
            user_content = body.get("content", "").strip()
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Du lieu khong hop le."}, status=400)

        if not user_content:
            return JsonResponse({"error": "Noi dung khong duoc de trong."}, status=400)

        response = StreamingHttpResponse(
            stream_conversation_reply(
                conversation=conversation,
                user=self.get_user(request),
                user_content=user_content,
            ),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class CustomerAssistantMessageStreamView(AssistantMessageStreamView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantMessageStreamView(StaffAssistantAccessMixin, AssistantMessageStreamView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantMessageStreamView(ManagerAssistantAccessMixin, AssistantMessageStreamView):
    profile = Conversation.PROFILE_MANAGER


class AssistantRenameView(ProfileContextMixin, View):
    def post(self, request, pk):
        conversation = self.get_conversation(request, pk)
        if conversation is None:
            return JsonResponse({"error": "Khong tim thay cuoc hoi thoai."}, status=404)
        try:
            body = json.loads(request.body)
            title = body.get("title", "").strip()[:200]
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Du lieu khong hop le."}, status=400)

        conversation.title = title
        conversation.save(update_fields=["title"])
        return JsonResponse({"ok": True, "title": conversation.get_title_display()})


class CustomerAssistantRenameView(AssistantRenameView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantRenameView(StaffAssistantAccessMixin, AssistantRenameView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantRenameView(ManagerAssistantAccessMixin, AssistantRenameView):
    profile = Conversation.PROFILE_MANAGER


class AssistantQuickStartView(ProfileContextMixin, View):
    """Tạo hoặc lấy conversation gần nhất, trả JSON cho sticky chat widget."""

    def post(self, request):
        force_new = request.GET.get("new") == "1"
        if force_new:
            conversation = self.create_profile_conversation(request)
        else:
            conversation = self.list_conversations(request, limit=1).first()
            if conversation is None:
                conversation = self.create_profile_conversation(request)
        return JsonResponse(
            {
                "pk": conversation.pk,
                "stream_url": self.get_named_url("stream", pk=conversation.pk),
            }
        )


class StaffAssistantQuickStartView(StaffAssistantAccessMixin, AssistantQuickStartView):
    profile = Conversation.PROFILE_STAFF


class CustomerAssistantQuickStartView(AssistantQuickStartView):
    """Không cần auth — customer profile dùng session_key."""
    profile = Conversation.PROFILE_CUSTOMER


class AssistantHealthView(ProfileContextMixin, View):
    def get(self, request):
        is_ready, error_message = check_ai_health()
        if is_ready:
            return JsonResponse({"ok": True, "ready": True})
        return JsonResponse(
            {
                "ok": False,
                "ready": False,
                "error": error_message or "Dich vu AI hien chua san sang.",
            },
            status=503,
        )


class CustomerAssistantHealthView(AssistantHealthView):
    profile = Conversation.PROFILE_CUSTOMER


class StaffAssistantHealthView(StaffAssistantAccessMixin, AssistantHealthView):
    profile = Conversation.PROFILE_STAFF


class ManagerAssistantHealthView(ManagerAssistantAccessMixin, AssistantHealthView):
    profile = Conversation.PROFILE_MANAGER
