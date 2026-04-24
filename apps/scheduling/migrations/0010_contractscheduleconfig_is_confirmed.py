import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0009_contractscheduleconfig_allowed_weekdays'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contractscheduleconfig',
            name='is_confirmed',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Đã chốt lịch'),
        ),
        migrations.AddField(
            model_name='contractscheduleconfig',
            name='confirmed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='confirmed_schedule_configs',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Người chốt lịch',
            ),
        ),
        migrations.AddField(
            model_name='contractscheduleconfig',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Thời điểm chốt'),
        ),
    ]
