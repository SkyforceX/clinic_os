from django.urls import path

from apps.engagement.api.webhook_views import (
    messenger_webhook, webchat_init, webchat_poll, webchat_send, zalo_webhook,
)
from apps.engagement.web.views.contact_views import (
    ajax_assign, ajax_log_call, ajax_upload_excel,
    contact_detail, contact_list_create, contact_list_detail, contact_list_index,
)
from apps.engagement.web.views.inbox_views import (
    inbox, poll_messages, send_message, update_conversation,
)
from apps.engagement.web.views.settings_views import (
    canned_delete, canned_save, channel_delete, channel_form, settings_overview,
)

app_name = "engagement"

urlpatterns = [
    # ── Inbox ──────────────────────────────────────────────────────────────────
    path("inbox/",                             inbox,               name="inbox"),
    path("inbox/conv/<int:conv_id>/send/",     send_message,        name="send_message"),
    path("inbox/conv/<int:conv_id>/update/",   update_conversation, name="update_conversation"),
    path("inbox/conv/<int:conv_id>/poll/",     poll_messages,       name="poll_messages"),

    # ── Contacts ───────────────────────────────────────────────────────────────
    path("contacts/",                              contact_list_index,  name="contact_list_index"),
    path("contacts/new/",                          contact_list_create, name="contact_list_create"),
    path("contacts/<int:list_id>/",                contact_list_detail, name="contact_list_detail"),
    path("contacts/<int:list_id>/upload/",         ajax_upload_excel,   name="ajax_upload_excel"),
    path("contacts/detail/<int:contact_id>/",      contact_detail,      name="contact_detail"),
    path("contacts/detail/<int:contact_id>/call/", ajax_log_call,       name="ajax_log_call"),
    path("contacts/assign/",                       ajax_assign,         name="ajax_assign"),

    # ── Settings ───────────────────────────────────────────────────────────────
    path("settings/",                        settings_overview, name="settings"),
    path("settings/channel/new/",            channel_form,      name="channel_create"),
    path("settings/channel/<int:channel_id>/edit/",   channel_form,   name="channel_edit"),
    path("settings/channel/<int:channel_id>/delete/", channel_delete, name="channel_delete"),
    path("settings/canned/save/",            canned_save,   name="canned_save"),
    path("settings/canned/<int:canned_id>/delete/", canned_delete, name="canned_delete"),

    # ── Webhooks (external, csrf exempt) ──────────────────────────────────────
    path("webhook/zalo/<int:channel_id>/",        zalo_webhook,      name="zalo_webhook"),
    path("webhook/messenger/<int:channel_id>/",   messenger_webhook, name="messenger_webhook"),
    path("webhook/webchat/<str:widget_key>/init/", webchat_init,     name="webchat_init"),
    path("webhook/webchat/<str:widget_key>/send/", webchat_send,     name="webchat_send"),
    path("webhook/webchat/<str:widget_key>/poll/", webchat_poll,     name="webchat_poll"),
]
