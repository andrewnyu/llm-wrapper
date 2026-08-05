from django.urls import path

from . import views

app_name = "gateway"

urlpatterns = [
    path("", views.provider_keys_list, name="keys"),
    path("settings/", views.gateway_settings, name="settings"),
    path("add/", views.provider_key_create, name="key_add"),
    path("<int:key_id>/edit/", views.provider_key_edit, name="key_edit"),
    path("<int:key_id>/delete/", views.provider_key_delete, name="key_delete"),
]
