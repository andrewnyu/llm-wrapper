from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from api_key_wrapper.gateway.model_catalog import (
    DEFAULT_IMAGE_ASPECT_RATIO,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_IMAGE_RESOLUTION,
    get_image_model,
    serialize_image_models,
)
from .models import ImageJob


@login_required
def image_view(request):
    jobs = list(
        ImageJob.objects.filter(user=request.user, kind=ImageJob.KIND_STUDIO).order_by("-created_at")[:24]
    )[::-1]
    for job in jobs:
        model_id = job.settings.get("model", "gemini-2.5-flash-image")
        model = get_image_model(model_id)
        job.model_label = model["label"] if model else model_id
        job.aspect_ratio = job.settings.get("aspect_ratio", "1:1")
        job.image_size = job.settings.get("image_size", "1K")
    return render(
        request,
        "imaging/image.html",
        {
            "jobs": jobs,
            "image_models": serialize_image_models(),
            "default_image_model": DEFAULT_IMAGE_MODEL,
            "default_aspect_ratio": DEFAULT_IMAGE_ASPECT_RATIO,
            "default_resolution": DEFAULT_IMAGE_RESOLUTION,
        },
    )


@login_required
def image_feedback_view(request):
    jobs = list(
        ImageJob.objects.filter(user=request.user, kind=ImageJob.KIND_FEEDBACK).order_by("-created_at")[:36]
    )[::-1]
    return render(request, "imaging/feedback.html", {"jobs": jobs})
