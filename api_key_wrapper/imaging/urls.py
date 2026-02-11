from django.urls import path

from . import views

app_name = "imaging"

urlpatterns = [
    path("", views.image_view, name="image"),
]
