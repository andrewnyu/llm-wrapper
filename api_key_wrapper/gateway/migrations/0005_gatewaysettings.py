from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("gateway", "0004_alter_providerkey_provider_and_more")]

    operations = [
        migrations.CreateModel(
            name="GatewaySettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("default_chat_provider", models.CharField(default="glm", max_length=32)),
                ("default_chat_model", models.CharField(default="glm-5.2", max_length=128)),
                ("enabled_providers", models.JSONField(default=list, help_text="Provider IDs whose shared environment keys may be used.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Gateway settings", "verbose_name_plural": "Gateway settings"},
        ),
    ]
