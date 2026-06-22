from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gateway", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="providerkey",
            name="provider",
            field=models.CharField(
                choices=[
                    ("openai", "OpenAI"),
                    ("anthropic", "Anthropic"),
                    ("google", "Google"),
                    ("nano_banana", "Nano Banana"),
                    ("deepseek", "DeepSeek"),
                    ("custom", "Custom"),
                ],
                max_length=32,
            ),
        ),
    ]
