from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0014_quotationline_for_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImplementationPlanLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_stt", models.PositiveIntegerField(blank=True, null=True)),
                ("row_owner", models.CharField(blank=True, default="", max_length=255)),
                ("row_category", models.CharField(blank=True, default="", max_length=255)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("edit", "Chỉnh sửa"),
                            ("confirm", "Xác nhận"),
                            ("unlock", "Gỡ xác nhận / mở khóa"),
                        ],
                        max_length=20,
                    ),
                ),
                ("department_key", models.CharField(blank=True, default="", max_length=50)),
                ("department_label", models.CharField(blank=True, default="", max_length=120)),
                ("actor_name", models.CharField(blank=True, default="", max_length=255)),
                ("detail_before", models.TextField(blank=True, default="")),
                ("detail_after", models.TextField(blank=True, default="")),
                ("note_before", models.TextField(blank=True, default="")),
                ("note_after", models.TextField(blank=True, default="")),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contract_implementation_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="contract.implementationplan",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log kế hoạch triển khai",
                "verbose_name_plural": "Log kế hoạch triển khai",
                "db_table": "contract_implementation_plan_log",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="implementationplanlog",
            index=models.Index(fields=["plan", "row_stt", "-created_at"], name="impl_log_plan_row_idx"),
        ),
        migrations.AddIndex(
            model_name="implementationplanlog",
            index=models.Index(fields=["plan", "action", "-created_at"], name="impl_log_plan_act_idx"),
        ),
    ]
