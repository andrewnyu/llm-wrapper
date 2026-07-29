from django.urls import path

from . import api_views

urlpatterns = [
    path("chat/complete", api_views.chat_complete, name="chat_complete"),
    path("image/conversations", api_views.image_conversations, name="image_conversations"),
    path(
        "image/conversations/<uuid:conversation_id>",
        api_views.image_conversation_detail,
        name="image_conversation_detail",
    ),
    path(
        "image/conversations/<uuid:conversation_id>/jobs",
        api_views.image_conversation_jobs,
        name="image_conversation_jobs",
    ),
    path("image/generate", api_views.image_generate, name="image_generate"),
    path("image/edit", api_views.image_edit, name="image_edit"),
    path("image/feedback", api_views.image_feedback, name="image_feedback"),
]
