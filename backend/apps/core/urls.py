from django.urls import path

from apps.core.csrf import protect_csrf

from . import api, views

app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("health/ready/", views.ready, name="ready"),
    # Staff-only: the panel's validated image upload (see apps/core/images.py).
    path("admin/images/", protect_csrf(api.ImageUploadView.as_view()), name="image-upload"),
]
