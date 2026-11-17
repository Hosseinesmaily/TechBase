"""Ticket API tests: the customer's side, the staff's side, and the wall between them.

The important property is the last one: a customer's ticket is invisible to any
other customer, and only the staff may answer or move the status.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.support.models import Ticket, TicketMessage, TicketStatus

pytestmark = pytest.mark.django_db

PASSWORD = "Test-Password-8291!"


def make_user(email: str, *, staff: bool = False):
    return get_user_model().objects.create_user(
        username=email, email=email, password=PASSWORD, is_staff=staff
    )


@pytest.fixture
def customer():
    return make_user("customer@example.com")


@pytest.fixture
def other_customer():
    return make_user("other@example.com")


@pytest.fixture
def staff_user():
    return make_user("support@example.com", staff=True)


@pytest.fixture
def customer_client(customer):
    client = APIClient()
    client.force_login(customer)
    return client


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_login(staff_user)
    return client


def open_ticket(
    client, subject: str = "سؤال دربارهٔ گارانتی", body: str = "سلام، شرایط گارانتی چیست؟"
):
    response = client.post(
        reverse("support:ticket-list"), {"subject": subject, "body": body}, format="json"
    )
    assert response.status_code == 201
    return response


class TestTicketCreation:
    def test_anonymous_requests_are_refused(self):
        client = APIClient()
        assert client.get(reverse("support:ticket-list")).status_code == 403
        assert (
            client.post(
                reverse("support:ticket-list"), {"subject": "x", "body": "y"}, format="json"
            ).status_code
            == 403
        )

    def test_opening_a_ticket_writes_its_first_message(self):
        customer = make_user("first@example.com")
        client = APIClient()
        client.force_login(customer)

        response = open_ticket(client)

        assert response.data["status"] == TicketStatus.OPEN
        assert response.data["status_label"] == "باز"
        assert response.data["message_count"] == 1
        assert response.data["has_staff_reply"] is False
        assert [message["from_staff"] for message in response.data["messages"]] == [False]
        assert response.data["user"]["email"] == "first@example.com"
        ticket = Ticket.objects.get(pk=response.data["id"])
        assert ticket.user == customer
        assert TicketMessage.objects.filter(ticket=ticket).count() == 1

    def test_missing_or_oversized_input_is_rejected(self):
        customer = make_user("validation@example.com")
        client = APIClient()
        client.force_login(customer)
        url = reverse("support:ticket-list")

        assert client.post(url, {"subject": "", "body": "متن"}, format="json").status_code == 400
        assert (
            client.post(url, {"subject": "عنوان", "body": "   "}, format="json").status_code == 400
        )
        huge = client.post(url, {"subject": "عنوان", "body": "ا" * 4001}, format="json")
        assert huge.status_code == 400
        assert "4000" in huge.data["error"]
        assert Ticket.objects.count() == 0


class TestTicketPrivacy:
    def test_a_customer_only_sees_their_own_tickets(self, customer_client, other_customer):
        mine = open_ticket(customer_client)
        foreign = Ticket.objects.create(user=other_customer, subject="تیکت کاربر دیگر")

        listing = customer_client.get(reverse("support:ticket-list"))
        assert listing.status_code == 200
        assert listing.data["count"] == 1
        assert listing.data["results"][0]["id"] == mine.data["id"]

        foreign_detail = reverse("support:ticket-detail", args=[foreign.id])
        foreign_messages = reverse("support:ticket-messages", args=[foreign.id])
        # A guessed id is a 404 — never somebody else's conversation.
        assert customer_client.get(foreign_detail).status_code == 404
        assert (
            customer_client.post(foreign_messages, {"body": "سلام"}, format="json").status_code
            == 404
        )


class TestStaffDesk:
    def test_staff_sees_every_ticket_and_can_answer_it(
        self, customer_client, staff_client, staff_user
    ):
        ticket_id = open_ticket(customer_client).data["id"]

        listing = staff_client.get(reverse("support:ticket-list"))
        assert listing.status_code == 200
        assert listing.data["count"] == 1
        assert listing.data["results"][0]["user"]["email"] == "customer@example.com"

        # The staff member owns no ticket, so "mine" is empty for them.
        mine = staff_client.get(reverse("support:ticket-list"), {"scope": "mine"})
        assert mine.data["count"] == 0

        replied = staff_client.post(
            reverse("support:ticket-messages", args=[ticket_id]),
            {"body": "سلام، گارانتی این محصول ۱۸ ماه است."},
            format="json",
        )
        assert replied.status_code == 201
        assert replied.data["status"] == TicketStatus.ANSWERED
        assert replied.data["has_staff_reply"] is True
        assert [message["from_staff"] for message in replied.data["messages"]] == [False, True]
        assert replied.data["messages"][1]["author"] == "support@example.com"

        # The customer reads the answer on their own thread.
        seen = customer_client.get(reverse("support:ticket-detail", args=[ticket_id]))
        assert seen.status_code == 200
        assert seen.data["status"] == TicketStatus.ANSWERED
        assert len(seen.data["messages"]) == 2

    def test_a_customer_follow_up_reopens_the_thread(self, customer_client, staff_client):
        ticket_id = open_ticket(customer_client).data["id"]
        staff_client.post(
            reverse("support:ticket-messages", args=[ticket_id]),
            {"body": "پاسخ تیم پشتیبانی"},
            format="json",
        )

        again = customer_client.post(
            reverse("support:ticket-messages", args=[ticket_id]),
            {"body": "ممنون؛ یک پرسش دیگر هم دارم."},
            format="json",
        )
        assert again.status_code == 201
        assert again.data["status"] == TicketStatus.IN_PROGRESS
        assert again.data["messages"][-1]["from_staff"] is False

    def test_only_staff_may_move_the_status(self, customer_client, staff_client):
        ticket_id = open_ticket(customer_client).data["id"]
        url = reverse("support:ticket-detail", args=[ticket_id])

        denied = customer_client.patch(url, {"status": TicketStatus.CLOSED}, format="json")
        assert denied.status_code == 403
        assert Ticket.objects.get(pk=ticket_id).status == TicketStatus.OPEN

        moved = staff_client.patch(url, {"status": TicketStatus.CLOSED}, format="json")
        assert moved.status_code == 200
        assert moved.data["status"] == TicketStatus.CLOSED

        invalid = staff_client.patch(url, {"status": "nonsense"}, format="json")
        assert invalid.status_code == 400
        assert TicketStatus.CLOSED in invalid.data["allowed"]

    def test_opening_a_ticket_never_changes_its_status(self, customer_client, staff_client):
        """The panel toggles the conversation locally; even the read endpoint is a
        plain GET. Opening (or re-opening, or listing) a ticket must be inert."""
        ticket_id = open_ticket(customer_client).data["id"]
        detail = reverse("support:ticket-detail", args=[ticket_id])

        for _ in range(3):
            assert customer_client.get(detail).status_code == 200
            assert staff_client.get(detail).status_code == 200
            assert staff_client.get(reverse("support:ticket-list")).status_code == 200

        assert Ticket.objects.get(pk=ticket_id).status == TicketStatus.OPEN
        assert Ticket.objects.get(pk=ticket_id).messages.count() == 1

    def test_a_closed_ticket_refuses_customer_messages_but_not_staff_notes(
        self, customer_client, staff_client
    ):
        ticket_id = open_ticket(customer_client).data["id"]
        staff_client.patch(
            reverse("support:ticket-detail", args=[ticket_id]),
            {"status": TicketStatus.CLOSED},
            format="json",
        )

        refused = customer_client.post(
            reverse("support:ticket-messages", args=[ticket_id]),
            {"body": "پیگیری"},
            format="json",
        )
        assert refused.status_code == 409
        assert TicketMessage.objects.filter(ticket_id=ticket_id).count() == 1

        assert (
            staff_client.post(
                reverse("support:ticket-messages", args=[ticket_id]),
                {"body": "یادداشت تیم پشتیبانی"},
                format="json",
            ).status_code
            == 201
        )

    def test_the_list_filters_by_status(self, customer_client, staff_client):
        first = open_ticket(customer_client, subject="تیکت اول", body="متن اول").data["id"]
        open_ticket(customer_client, subject="تیکت دوم", body="متن دوم")
        staff_client.patch(
            reverse("support:ticket-detail", args=[first]),
            {"status": TicketStatus.CLOSED},
            format="json",
        )

        closed = staff_client.get(reverse("support:ticket-list"), {"status": TicketStatus.CLOSED})
        assert closed.data["count"] == 1
        assert closed.data["results"][0]["subject"] == "تیکت اول"

        everything = staff_client.get(reverse("support:ticket-list"))
        assert everything.data["count"] == 2
