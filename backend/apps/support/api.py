"""Support ticket API.

Two audiences share one model:

* the **customer** — opens a ticket, reads the thread, may add a follow-up;
* the **staff** (`is_staff`) — reads every ticket, answers it and moves its status.

Authorisation is decided here, on the server. A customer's queryset contains
their own tickets only, so a guessed id is a 404 — never somebody else's thread.
"""

from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket, TicketMessage, TicketStatus

MAX_SUBJECT_LENGTH = 200
MAX_BODY_LENGTH = 4000
#: How many tickets one list request returns. Both panels show the newest ones.
LIST_LIMIT = 200


def is_staff_user(user: Any) -> bool:
    """Whether this requester is on the support side of the desk."""
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False))


def _display_name(user: Any) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.email or user.get_username()


def serialize_message(message: TicketMessage) -> dict:
    return {
        "id": str(message.id),
        "body": message.body,
        "from_staff": message.from_staff,
        "author": _display_name(message.author),
        "created_at": message.created_at.isoformat(),
    }


def serialize_ticket(ticket: Ticket, *, include_messages: bool = False) -> dict:
    data = {
        "id": str(ticket.id),
        "subject": ticket.subject,
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "created_at": ticket.created_at.isoformat(),
        "last_message_at": (ticket.last_message_at or ticket.created_at).isoformat(),
        "message_count": ticket.messages.count(),
        "has_staff_reply": ticket.has_staff_reply,
        "user": {"name": _display_name(ticket.user), "email": ticket.user.email},
    }
    if include_messages:
        data["messages"] = [
            serialize_message(message)
            for message in ticket.messages.select_related("author").order_by("created_at")
        ]
    return data


def _ticket_for(request, ticket_id) -> Ticket:
    """The ticket the requester is allowed to see, or a 404.

    Staff see everything; everybody else only sees their own thread.
    """
    queryset = Ticket.objects.select_related("user")
    if not is_staff_user(request.user):
        queryset = queryset.filter(user=request.user)
    return get_object_or_404(queryset, pk=ticket_id)


class TicketListCreateView(APIView):
    """The requester's tickets (staff: every one), and opening a new ticket.

    `POST` writes the first message in the same request, so a ticket can never
    exist without a body.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        if is_staff_user(request.user) and request.query_params.get("scope") != "mine":
            queryset = Ticket.objects.all()
        else:
            queryset = Ticket.objects.filter(user=request.user)

        wanted_status = request.query_params.get("status", "").strip()
        if wanted_status in TicketStatus.values:
            queryset = queryset.filter(status=wanted_status)

        tickets = [
            serialize_ticket(ticket) for ticket in queryset.select_related("user")[:LIST_LIMIT]
        ]
        return Response({"count": len(tickets), "results": tickets})

    def post(self, request) -> Response:
        subject = str(request.data.get("subject", "")).strip()
        body = str(request.data.get("body", "")).strip()
        if not subject or not body:
            return Response(
                {"error": "عنوان و متن پیام را وارد کنید."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(subject) > MAX_SUBJECT_LENGTH or len(body) > MAX_BODY_LENGTH:
            return Response(
                {
                    "error": (
                        f"عنوان حداکثر {MAX_SUBJECT_LENGTH} نویسه و متن حداکثر "
                        f"{MAX_BODY_LENGTH} نویسه باشد."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket = Ticket.objects.create(
            user=request.user, subject=subject, last_message_at=timezone.now()
        )
        TicketMessage.objects.create(ticket=ticket, author=request.user, body=body)
        return Response(
            serialize_ticket(ticket, include_messages=True),
            status=status.HTTP_201_CREATED,
        )


class TicketDetailView(APIView):
    """`GET` the thread; `PATCH` moves the status (staff only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id) -> Response:
        return Response(serialize_ticket(_ticket_for(request, ticket_id), include_messages=True))

    def patch(self, request, ticket_id) -> Response:
        if not is_staff_user(request.user):
            return Response(
                {"error": "تغییر وضعیت تیکت فقط در دسترس تیم پشتیبانی است."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ticket = _ticket_for(request, ticket_id)
        new_status = str(request.data.get("status", "")).strip()
        if new_status not in TicketStatus.values:
            return Response(
                {"error": "وضعیت نامعتبر است.", "allowed": list(TicketStatus.values)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket.status = new_status
        ticket.save(update_fields=["status", "updated_at"])
        return Response(serialize_ticket(ticket, include_messages=True))


class TicketMessageCreateView(APIView):
    """A follow-up message — from the thread's owner or from the staff."""

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id) -> Response:
        staff = is_staff_user(request.user)
        ticket = _ticket_for(request, ticket_id)
        body = str(request.data.get("body", "")).strip()
        if not body:
            return Response({"error": "متن پیام را وارد کنید."}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > MAX_BODY_LENGTH:
            return Response(
                {"error": f"متن پیام حداکثر {MAX_BODY_LENGTH} نویسه باشد."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not staff and ticket.status == TicketStatus.CLOSED:
            return Response(
                {"error": "این تیکت بسته شده است؛ برای پیگیری، تیکت تازهای باز کنید."},
                status=status.HTTP_409_CONFLICT,
            )

        message = TicketMessage.objects.create(
            ticket=ticket, author=request.user, body=body, from_staff=staff
        )
        ticket.last_message_at = message.created_at
        # A staff answer closes the loop; a customer follow-up opens it again.
        ticket.status = TicketStatus.ANSWERED if staff else TicketStatus.IN_PROGRESS
        ticket.save(update_fields=["last_message_at", "status", "updated_at"])
        return Response(
            serialize_ticket(ticket, include_messages=True),
            status=status.HTTP_201_CREATED,
        )
