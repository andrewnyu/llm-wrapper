from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ImageJob


@login_required
def image_view(request):
    jobs = ImageJob.objects.filter(user=request.user)[:12]
    return render(request, "imaging/image.html", {"jobs": jobs})
