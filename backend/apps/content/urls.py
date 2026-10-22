from django.urls import path

from .api import WikiPageDetailView, WikiPageListView

app_name = "content"

urlpatterns = [
    path("pages/", WikiPageListView.as_view(), name="page-list"),
    path("pages/<slug:slug>/", WikiPageDetailView.as_view(), name="page-detail"),
]
