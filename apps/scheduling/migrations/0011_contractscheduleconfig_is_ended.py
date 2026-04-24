from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0010_contractscheduleconfig_is_confirmed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="contractscheduleconfig",
            name="is_ended",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Đã kết thúc"),
        ),
        migrations.AddField(
            model_name="contractscheduleconfig",
            name="ended_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ended_schedule_configs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Người kết thúc",
            ),
        ),
        migrations.AddField(
            model_name="contractscheduleconfig",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm kết thúc"),
        ),
    ]
