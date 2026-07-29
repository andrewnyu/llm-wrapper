import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("imaging", "0004_imagejob_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImageConversation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(default="New image chat", max_length=120)),
                (
                    "kind",
                    models.CharField(
                        choices=[("studio", "Studio"), ("feedback", "Feedback")],
                        default="studio",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_conversations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["user", "kind", "updated_at"], name="img_conv_user_kind_upd_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="imagejob",
            name="conversation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="jobs",
                to="imaging.imageconversation",
            ),
        ),
        migrations.AddIndex(
            model_name="imagejob",
            index=models.Index(fields=["conversation", "created_at"], name="img_job_conv_created_idx"),
        ),
        migrations.AddIndex(
            model_name="imagejob",
            index=models.Index(fields=["user", "kind", "created_at"], name="img_job_user_kind_idx"),
        ),
    ]
