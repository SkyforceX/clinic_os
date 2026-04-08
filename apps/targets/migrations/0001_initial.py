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
            name="SalesTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_type", models.CharField(
                    choices=[("MONTHLY", "Tháng"), ("QUARTERLY", "Quý"), ("YEARLY", "Năm")],
                    db_index=True, max_length=12,
                )),
                ("year",          models.PositiveIntegerField(db_index=True)),
                ("period_number", models.PositiveSmallIntegerField()),
                ("revenue_target",        models.BigIntegerField(default=0, verbose_name="Doanh thu mục tiêu (VNĐ)")),
                ("contract_count_target", models.PositiveIntegerField(default=0, verbose_name="Số HĐ mục tiêu")),
                ("quotation_count_target",models.PositiveIntegerField(default=0, verbose_name="Số báo giá mục tiêu")),
                ("pax_target",            models.PositiveIntegerField(default=0, verbose_name="Số người khám mục tiêu")),
                ("new_client_target",    models.PositiveIntegerField(default=0, verbose_name="Số KH mới mục tiêu")),
                ("renewal_target",       models.PositiveIntegerField(default=0, verbose_name="Số HĐ gia hạn mục tiêu")),
                ("avg_deal_size_target", models.BigIntegerField(default=0, verbose_name="Giá trị HĐ TB mục tiêu")),
                ("notes",      models.TextField(blank=True, verbose_name="Ghi chú")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sales_targets",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Sale phụ trách",
                )),
                ("created_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_sales_targets",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "targets_sales_target", "ordering": ["-year", "period_type", "period_number"]},
        ),
        migrations.AddConstraint(
            model_name="salestarget",
            constraint=models.UniqueConstraint(
                fields=["user", "period_type", "year", "period_number"],
                name="uq_targets_user_period",
            ),
        ),
        migrations.CreateModel(
            name="TargetNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("body",       models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("target", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="target_notes",
                    to="targets.salestarget",
                )),
                ("author", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="target_notes_authored",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "targets_target_note", "ordering": ["-created_at"]},
        ),
    ]
