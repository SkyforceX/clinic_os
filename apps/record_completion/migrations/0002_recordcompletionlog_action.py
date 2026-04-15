from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("record_completion", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="recordcompletionlog",
            name="action",
            field=models.CharField(
                choices=[("ADVANCE", "Xác nhận tiến"), ("RETURN", "Trả về bước trước")],
                db_index=True,
                default="ADVANCE",
                max_length=10,
                verbose_name="Hành động",
            ),
        ),
        migrations.AddIndex(
            model_name="recordcompletionlog",
            index=models.Index(
                fields=["record_completion", "action"],
                name="rcl_completion_action_idx",
            ),
        ),
        migrations.AlterModelOptions(
            name="recordcompletionlog",
            options={
                "ordering": ["confirmed_at"],
                "verbose_name": "Log hoàn tất hồ sơ",
                "verbose_name_plural": "Log hoàn tất hồ sơ",
            },
        ),
    ]
