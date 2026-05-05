import django.db.models.manager
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0002_knowledgedocument_knowledgechunk"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="knowledgechunk",
            managers=[
                ("records", django.db.models.manager.Manager()),
            ],
        ),
        migrations.AlterModelManagers(
            name="knowledgedocument",
            managers=[
                ("records", django.db.models.manager.Manager()),
            ],
        ),
    ]
