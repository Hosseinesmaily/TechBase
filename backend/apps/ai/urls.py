from django.urls import path

from . import api

app_name = "ai"

urlpatterns = [
    path("chat/", api.ChatView.as_view(), name="chat"),
    path("chat/feedback/", api.ChatFeedbackView.as_view(), name="feedback"),
    path("logs/", api.QueryLogListView.as_view(), name="logs"),
]
