import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hrm", "0003_doctorschedule"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("schedule_date", models.DateField(db_index=True, verbose_name="Ngày làm việc")),
                ("shift", models.CharField(
                    blank=True, default="", max_length=1,
                    choices=[
                        ("F", "Cả ngày"), ("S", "Ca sáng"), ("C", "Ca chiều"),
                        ("L", "Nghỉ lễ / Tết"), ("O", "Không làm việc"),
                    ],
                    verbose_name="Ca làm việc",
                )),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employee", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="work_schedules",
                    to="hrm.employee",
                    verbose_name="Nhân viên",
                )),
                ("registered_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="work_schedules_registered",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người đăng ký",
                )),
            ],
            options={
                "verbose_name": "Lịch làm việc",
                "verbose_name_plural": "Lịch làm việc toàn phòng khám",
                "db_table": "hrm_work_schedule",
                "ordering": ["schedule_date", "employee__department__display_order", "employee__full_name"],
            },
        ),
        migrations.AddIndex(
            model_name="workschedule",
            index=models.Index(fields=["schedule_date"], name="hrm_ws_date_idx"),
        ),
        migrations.AddIndex(
            model_name="workschedule",
            index=models.Index(fields=["employee", "schedule_date"], name="hrm_ws_emp_date_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="workschedule",
            unique_together={("employee", "schedule_date")},
        ),
        migrations.CreateModel(
            name="WorkScheduleLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("old_shift", models.CharField(blank=True, max_length=1, verbose_name="Ca cũ")),
                ("new_shift", models.CharField(blank=True, max_length=1, verbose_name="Ca mới")),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="Ghi chú")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="work_schedule_logs",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Người thực hiện",
                )),
                ("work_schedule", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="logs",
                    to="hrm.workschedule",
                    verbose_name="Lịch làm việc",
                )),
            ],
            options={
                "verbose_name": "Log lịch làm việc",
                "db_table": "hrm_work_schedule_log",
                "ordering": ["-created_at"],
            },
        ),
    ]
