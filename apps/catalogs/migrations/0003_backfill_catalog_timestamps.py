from django.db import migrations
from django.utils import timezone


def backfill_timestamps(apps, schema_editor):
    now = timezone.now()

    GroupCheckup = apps.get_model("catalogs", "GroupCheckup")
    CheckupCategory = apps.get_model("catalogs", "CheckupCategory")

    GroupCheckup.objects.filter(created_at__isnull=True).update(created_at=now)
    GroupCheckup.objects.filter(updated_at__isnull=True).update(updated_at=now)

    CheckupCategory.objects.filter(created_at__isnull=True).update(created_at=now)
    CheckupCategory.objects.filter(updated_at__isnull=True).update(updated_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0002_alter_checkupcategory_options_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_timestamps, migrations.RunPython.noop),
    ]