from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # API
    path("api/v1/", include("apps.core.urls")),
    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Wagtail CMS mounts here in Phase 2 (docs/DECISIONS.md A1).
]


def homepage(_request) -> JsonResponse:
    """Root smoke endpoint; the real site is the Nuxt app on :3000."""
    return JsonResponse({"service": "techbase-api", "docs": "/api/docs/"})


urlpatterns.insert(0, path("", homepage))
