from django.urls import path

from . import views

app_name = "compat"

urlpatterns = [
    path("check/", views.CompatibilityCheckView.as_view(), name="check"),
    path("rules/", views.CompatibilityRuleListView.as_view(), name="rule-list"),
]
