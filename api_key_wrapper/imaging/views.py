from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ImageJob


@login_required
def image_view(request):
    jobs = list(
        ImageJob.objects.filter(user=request.user, kind=ImageJob.KIND_STUDIO).order_by("-created_at")[:24]
    )[::-1]
    return render(request, "imaging/image.html", {"jobs": jobs})


@login_required
def image_feedback_view(request):
    jobs = list(
        ImageJob.objects.filter(user=request.user, kind=ImageJob.KIND_FEEDBACK).order_by("-created_at")[:36]
    )[::-1]
    return render(request, "imaging/feedback.html", {"jobs": jobs})
