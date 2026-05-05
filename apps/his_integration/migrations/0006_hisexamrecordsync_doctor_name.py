from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('his_integration', '0005_hisdbodanhsachdichvudinhnghiatruockhamtheodoan_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='hisexamrecordsync',
            name='doctor_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='Tên BS'),
        ),
    ]
