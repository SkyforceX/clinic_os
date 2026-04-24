from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0008_contractscheduleconfig_his_package'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractscheduleconfig',
            name='allowed_weekdays',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Danh sách weekday (0=T2,1=T3,2=T4,3=T5,4=T6,5=T7). Rỗng = tất cả ngày làm việc.',
                verbose_name='Các thứ trong tuần được phân slot',
            ),
        ),
    ]
