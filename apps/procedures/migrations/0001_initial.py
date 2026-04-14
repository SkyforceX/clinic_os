import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Procedure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Tên quy trình')),
                ('code', models.CharField(blank=True, max_length=50, unique=True, verbose_name='Mã quy trình')),
                ('category', models.CharField(
                    choices=[
                        ('sale', 'Kinh doanh / Bán hàng'), ('marketing', 'Marketing'),
                        ('clinical', 'Khám chữa bệnh'), ('operations', 'Vận hành nội bộ'),
                        ('customer_care', 'Chăm sóc khách hàng'), ('hr', 'Nhân sự'),
                        ('accounting', 'Kế toán'), ('quality', 'Chất lượng'),
                        ('it', 'Công nghệ thông tin'), ('other', 'Khác'),
                    ],
                    default='other', max_length=50, verbose_name='Loại',
                )),
                ('description', models.TextField(blank=True, verbose_name='Mô tả tổng quan')),
                ('status', models.CharField(
                    choices=[('draft', 'Bản nháp'), ('published', 'Đã ban hành'), ('archived', 'Lưu trữ')],
                    default='draft', max_length=20, verbose_name='Trạng thái',
                )),
                ('version', models.CharField(default='1.0', max_length=20, verbose_name='Phiên bản')),
                ('effective_date', models.DateField(blank=True, null=True, verbose_name='Ngày hiệu lực')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_procedures', to=settings.AUTH_USER_MODEL,
                    verbose_name='Người tạo',
                )),
            ],
            options={
                'verbose_name': 'Quy trình',
                'verbose_name_plural': 'Danh sách quy trình',
                'db_table': 'procedures_procedure',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProcedureStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Tên bước')),
                ('description', models.TextField(blank=True, verbose_name='Mô tả chi tiết')),
                ('responsible', models.CharField(blank=True, max_length=255, verbose_name='Người / Bộ phận thực hiện')),
                ('duration', models.CharField(blank=True, max_length=100, verbose_name='Thời gian thực hiện')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Thứ tự')),
                ('color', models.CharField(default='#0d6efd', max_length=7, verbose_name='Màu sắc')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='children', to='procedures.procedurestep', verbose_name='Bước cha',
                )),
                ('procedure', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='steps', to='procedures.procedure', verbose_name='Quy trình',
                )),
            ],
            options={
                'verbose_name': 'Bước quy trình',
                'db_table': 'procedures_step',
                'ordering': ['order', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='ProcedureAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Tên tài liệu')),
                ('file', models.FileField(upload_to='procedures/attachments/', verbose_name='Tệp')),
                ('file_type', models.CharField(
                    choices=[('image', 'Hình ảnh'), ('pdf', 'PDF'), ('other', 'Khác')],
                    default='other', max_length=10, verbose_name='Loại tệp',
                )),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('procedure', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments', to='procedures.procedure',
                )),
                ('step', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments', to='procedures.procedurestep',
                )),
                ('uploaded_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='procedure_attachments', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'procedures_attachment',
                'ordering': ['uploaded_at'],
            },
        ),
    ]
