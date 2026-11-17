from django.urls import path

from apps.core.csrf import protect_csrf

from . import api

app_name = "support"

urlpatterns = [
    path("tickets/", protect_csrf(api.TicketListCreateView.as_view()), name="ticket-list"),
    path(
        "tickets/<uuid:ticket_id>/",
        protect_csrf(api.TicketDetailView.as_view()),
        name="ticket-detail",
    ),
    path(
        "tickets/<uuid:ticket_id>/messages/",
        protect_csrf(api.TicketMessageCreateView.as_view()),
        name="ticket-messages",
    ),
]
