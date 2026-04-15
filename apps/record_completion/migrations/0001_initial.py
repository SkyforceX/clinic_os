import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("reception", "0002_alter_checkinrecord_exam_date_alter_checkinrecord_id"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecordCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("current_step", models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="Bước hiện tại")),
                ("is_completed", models.BooleanField(db_index=True, default=False, verbose_name="Hoàn tất")),
                ("checklist_note", models.TextField(blank=True, verbose_name="Ghi chú checklist")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "checkin_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="record_completion",
                        to="reception.checkinrecord",
                        verbose_name="Bản ghi check-in",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="record_completions",
                        to="organizations.company",
                        verbose_name="Công ty",
                    ),
                ),
            ],
            options={
                "verbose_name": "Hoàn tất hồ sơ",
                "verbose_name_plural": "Hoàn tất hồ sơ",
                "db_table": "record_completion",
                "ordering": ["checkin_record__exam_date", "checkin_record__snapshot_ho_ten"],
            },
        ),
        migrations.CreateModel(
            name="RecordCompletionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step", models.PositiveSmallIntegerField(verbose_name="Bước")),
                ("note", models.TextField(blank=True, verbose_name="Ghi chú")),
                ("confirmed_at", models.DateTimeField(auto_now_add=True, verbose_name="Thời gian xác nhận")),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="record_completion_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người xác nhận",
                    ),
                ),
                (
                    "record_completion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="record_completion.recordcompletion",
                        verbose_name="Hồ sơ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log hoàn tất hồ sơ",
                "verbose_name_plural": "Log hoàn tất hồ sơ",
                "db_table": "record_completion_log",
                "ordering": ["step", "confirmed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="recordcompletion",
            index=models.Index(fields=["company", "is_completed"], name="rc_company_completed_idx"),
        ),
        migrations.AddIndex(
            model_name="recordcompletion",
            index=models.Index(fields=["current_step", "is_completed"], name="rc_step_completed_idx"),
        ),
        migrations.AddIndex(
            model_name="recordcompletionlog",
            index=models.Index(fields=["record_completion", "step"], name="rcl_completion_step_idx"),
        ),
    ]
