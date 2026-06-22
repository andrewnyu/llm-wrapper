from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("imaging", "0003_imagejob_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagejob",
            name="settings",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
