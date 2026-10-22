from django.urls import path

from . import views

app_name = "benchmarks"

urlpatterns = [
    path("", views.BenchmarkListView.as_view(), name="benchmark-list"),
]
