from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from api_key_wrapper.gateway.model_catalog import (
    DEFAULT_IMAGE_ASPECT_RATIO,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_IMAGE_RESOLUTION,
    serialize_image_models,
)


@login_required
def image_view(request):
    return render(
        request,
        "imaging/image.html",
        {
            "image_models": serialize_image_models(),
            "default_image_model": DEFAULT_IMAGE_MODEL,
            "default_aspect_ratio": DEFAULT_IMAGE_ASPECT_RATIO,
            "default_resolution": DEFAULT_IMAGE_RESOLUTION,
        },
    )


@login_required
def image_feedback_view(request):
    return render(request, "imaging/feedback.html")
