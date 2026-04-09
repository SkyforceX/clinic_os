from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title",
                    models.CharField(blank=True, max_length=255, verbose_name="Tiêu đề"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_conversations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người dùng",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cuộc hội thoại",
                "verbose_name_plural": "Lịch sử hội thoại",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "Người dùng"),
                            ("assistant", "Trợ lý"),
                            ("system", "Hệ thống"),
                        ],
                        max_length=16,
                        verbose_name="Vai trò",
                    ),
                ),
                ("content", models.TextField(verbose_name="Nội dung")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="ai_assistant.conversation",
                        verbose_name="Hội thoại",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tin nhắn",
                "verbose_name_plural": "Tin nhắn",
                "ordering": ["created_at"],
            },
        ),
    ]
