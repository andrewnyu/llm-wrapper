from django.contrib import admin
from django.conf import settings
from django.urls import re_path
from django.urls import path, include
from django.views.static import serve
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/chat/", permanent=False)),
    path("admin/", admin.site.urls),
    path("account/", include("api_key_wrapper.accounts.urls")),
    path("chat/", include("api_key_wrapper.chat.urls")),
    path("image/", include("api_key_wrapper.imaging.urls")),
    path("keys/", include("api_key_wrapper.gateway.urls")),
    path("api/", include("api_key_wrapper.chat.api_urls")),
    path("api/", include("api_key_wrapper.gateway.api_urls")),
]

# Fallback static serving for non-debug deployments that run Gunicorn
# directly without a reverse proxy static alias.
if not settings.DEBUG:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    ]
