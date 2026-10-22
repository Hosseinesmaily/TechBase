from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.images import urls as wagtailimages_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    # API
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/catalog/", include("apps.catalog.urls")),
    path("api/v1/compat/", include("apps.compat.urls")),
    path("api/v1/benchmarks/", include("apps.benchmarks.urls")),
    path("api/v1/search/", include("apps.search.urls")),
    path("api/v1/wiki/", include("apps.content.urls")),
    path("api/v1/linking/", include("apps.linking.urls")),
    path("api/v1/ai/", include("apps.ai.urls")),
    # The Wagtail editorial admin.
    path("cms/", include(wagtailadmin_urls)),
    path("cms/documents/", include(wagtaildocs_urls)),
    path("cms/images/", include(wagtailimages_urls)),
    # Public wiki pages, served by Wagtail. The Nuxt app is the primary
    # frontend, but these URLs must work (they are the canonical page
    # addresses used in citations).
    path("wiki/", include(wagtail_urls)),
    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]


def homepage(_request) -> JsonResponse:
    """Root smoke endpoint; the real site is the Nuxt app on :3000."""
    return JsonResponse({"service": "techbase-api", "docs": "/api/docs/"})


urlpatterns.insert(0, path("", homepage))
