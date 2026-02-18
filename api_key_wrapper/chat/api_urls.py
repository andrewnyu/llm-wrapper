from django.urls import path

from . import views

urlpatterns = [
    path("conversations", views.conversations_view, name="conversations"),
    path(
        "conversations/<uuid:conversation_id>",
        views.conversation_detail_view,
        name="conversation_detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages",
        views.conversation_messages_view,
        name="conversation_messages",
    ),
    path("generate/cancel", views.cancel_generate_view, name="generate_cancel"),
]
