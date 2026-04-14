import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("patients", "0001_initial"),
        ("scheduling", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckInRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("snapshot_ma_bn",        models.CharField(max_length=20, verbose_name="Mã bệnh nhân")),
                ("snapshot_ho_ten",       models.CharField(max_length=100, verbose_name="Họ và tên")),
                ("snapshot_gioi_tinh",    models.CharField(blank=True, max_length=10, verbose_name="Giới tính")),
                ("snapshot_ngay_sinh",    models.DateField(blank=True, null=True, verbose_name="Ngày sinh")),
                ("snapshot_company_name", models.CharField(blank=True, max_length=200, verbose_name="Tên công ty")),
                ("snapshot_exam_start",   models.DateField(blank=True, null=True, verbose_name="Ngày bắt đầu khám")),
                ("snapshot_exam_end",     models.DateField(blank=True, null=True, verbose_name="Ngày kết thúc khám")),
                ("exam_date",   models.DateField(db_index=True, verbose_name="Ngày khám thực tế")),
                ("status",      models.CharField(
                    choices=[("CHECKED_IN", "Đã check-in"), ("CHECKED_OUT", "Đã check-out"), ("DEFERRED", "Quay lại sau")],
                    db_index=True, default="CHECKED_IN", max_length=16, verbose_name="Trạng thái",
                )),
                ("checked_in_at",  models.DateTimeField(blank=True, null=True, verbose_name="Thời gian check-in")),
                ("checked_out_at", models.DateTimeField(blank=True, null=True, verbose_name="Thời gian check-out")),
                ("deferred_at",    models.DateTimeField(blank=True, null=True, verbose_name="Thời gian hoãn")),
                ("note",       models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="checkin_records", to="organizations.company", verbose_name="Công ty",
                )),
                ("operator", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="checkin_operations", to=settings.AUTH_USER_MODEL, verbose_name="Thư ký thực hiện",
                )),
                ("patient", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="checkin_records", to="patients.patient", verbose_name="Bệnh nhân",
                )),
                ("schedule_config", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="checkin_records", to="scheduling.contractscheduleconfig",
                    verbose_name="Cấu hình lịch khám",
                )),
            ],
            options={
                "verbose_name": "Bản ghi check-in",
                "verbose_name_plural": "Bản ghi check-in / check-out",
                "db_table": "reception_checkin_record",
                "ordering": ["-exam_date", "-checked_in_at"],
            },
        ),
        migrations.AddIndex(
            model_name="checkinrecord",
            index=models.Index(fields=["exam_date", "status"], name="reception_ci_date_status_idx"),
        ),
        migrations.AddIndex(
            model_name="checkinrecord",
            index=models.Index(fields=["snapshot_ma_bn", "exam_date"], name="reception_ci_mabn_date_idx"),
        ),
    ]
