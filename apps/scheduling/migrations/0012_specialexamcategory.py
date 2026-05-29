from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0011_contractscheduleconfig_is_ended"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpecialExamCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True, verbose_name="Tên danh mục")),
                ("description", models.TextField(blank=True, verbose_name="Mô tả")),
                ("display_order", models.PositiveIntegerField(default=0, verbose_name="Thứ tự hiển thị")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Đang sử dụng")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Tạo lúc")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Cập nhật lúc")),
            ],
            options={
                "verbose_name": "Mục khám đặc biệt",
                "verbose_name_plural": "Mục khám đặc biệt",
                "db_table": "scheduling_special_exam_category",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="contractscheduleconfig",
            name="special_exam_categories",
            field=models.ManyToManyField(
                blank=True,
                related_name="schedule_configs",
                to="scheduling.specialexamcategory",
                verbose_name="Mục khám đặc biệt",
            ),
        ),
    ]
