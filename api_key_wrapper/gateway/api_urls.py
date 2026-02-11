from django.urls import path

from . import api_views

urlpatterns = [
    path("chat/complete", api_views.chat_complete, name="chat_complete"),
    path("image/generate", api_views.image_generate, name="image_generate"),
]
