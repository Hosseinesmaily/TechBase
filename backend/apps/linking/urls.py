from django.urls import path

from . import api

app_name = "linking"

urlpatterns = [
    path("hovercard/", api.HoverCardView.as_view(), name="hovercard"),
    path("backlinks/<slug:slug>/", api.BacklinkListView.as_view(), name="backlinks"),
    path("redlinks/", api.RedLinkListView.as_view(), name="redlinks"),
    path("orphans/", api.OrphanPageListView.as_view(), name="orphans"),
]
