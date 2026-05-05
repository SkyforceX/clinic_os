from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0005_remove_legacy_knowledge_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ai_conversations",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Nguoi dung",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="profile",
            field=models.CharField(
                choices=[
                    ("customer", "Customer Bot"),
                    ("staff", "Staff Bot"),
                    ("manager", "Manager Bot"),
                ],
                default="manager",
                max_length=16,
                verbose_name="Ho so tro ly",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="session_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
            preserve_default=False,
        ),
    ]
