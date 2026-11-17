"""What the login form relies on: the server's own `is_staff`, and the wall between
a customer session and the management endpoints.

The frontend redirects on these values, so the values themselves are pinned here.
The redirect is convenience; the 403 from the API is the actual control, and both
are checked.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

PASSWORD = "Test-Password-8291!"


def make_user(email: str, *, staff: bool = False, username: str | None = None):
    return get_user_model().objects.create_user(
        username=username or email, email=email, password=PASSWORD, is_staff=staff
    )


def csrf_headers(client: APIClient) -> dict[str, str]:
    response = client.get(reverse("accounts:csrf"))
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.data["csrf_token"]}


def login(client: APIClient, identifier: str, password: str = PASSWORD):
    return client.post(
        reverse("accounts:login"),
        {"email": identifier, "password": password},
        format="json",
        **csrf_headers(client),
    )


class TestLoginTellsTheFrontendWhoSignedIn:
    def test_a_staff_login_reports_is_staff(self):
        make_user("manager@example.com", staff=True)
        client = APIClient(enforce_csrf_checks=True)

        response = login(client, "manager@example.com")

        assert response.status_code == 200
        assert response.data["user"]["is_staff"] is True
        # The redirect decision reads the session endpoint, so it must agree.
        assert client.get(reverse("accounts:me")).data["user"]["is_staff"] is True

    def test_a_customer_login_reports_no_staff_rights(self):
        make_user("customer@example.com")
        client = APIClient(enforce_csrf_checks=True)

        response = login(client, "customer@example.com")

        assert response.status_code == 200
        assert response.data["user"]["is_staff"] is False

    def test_an_account_without_an_email_can_sign_in_with_its_username(self):
        # The project's own manager account was created without an email; the
        # endpoint falls back to the username, and the form accepts both.
        make_user("", staff=True, username="office-manager")
        client = APIClient(enforce_csrf_checks=True)

        response = login(client, "office-manager")

        assert response.status_code == 200
        assert response.data["user"]["is_staff"] is True

    def test_a_wrong_password_is_a_readable_error(self):
        make_user("customer@example.com")
        client = APIClient(enforce_csrf_checks=True)

        response = login(client, "customer@example.com", "wrong-password")

        assert response.status_code == 400
        assert "درست نیست" in response.data["error"]
        assert client.get(reverse("accounts:me")).data["authenticated"] is False


class TestTheManagementWall:
    ADMIN_LINKS = "/api/v1/wiki/admin-links/"
    TICKETS = "/api/v1/support/tickets/"

    def test_an_anonymous_visitor_is_refused(self):
        client = APIClient()

        assert client.get(self.ADMIN_LINKS).status_code == 403
        assert client.get(self.TICKETS).status_code == 403

    def test_a_customer_session_is_refused_the_staff_links(self):
        customer = make_user("customer@example.com")
        client = APIClient()
        client.force_login(customer)

        # Typing /admin-panel is not the control: the API refuses the request.
        assert client.get(self.ADMIN_LINKS).status_code == 403

    def test_a_customer_sees_only_their_own_tickets_and_cannot_widen_it(self):
        from apps.support.models import Ticket

        customer = make_user("customer@example.com")
        other = make_user("other@example.com")
        Ticket.objects.create(user=other, subject="تیکت کاربر دیگر")

        client = APIClient()
        client.force_login(customer)

        listing = client.get(self.TICKETS)
        assert listing.status_code == 200
        # The endpoint is shared, but the queryset is scoped to the requester, so a
        # customer sees only their own (here: none).
        assert listing.data["count"] == 0

        # The staff scope cannot be borrowed by asking for it.
        widened = client.get(self.TICKETS, {"scope": "all"})
        assert widened.status_code == 200
        assert widened.data["count"] == 0
        for row in widened.data["results"]:
            assert row["user"]["email"] != "other@example.com"

    def test_a_staff_session_reaches_the_management_apis(self):
        manager = make_user("manager@example.com", staff=True)
        client = APIClient()
        client.force_login(manager)

        assert client.get(self.ADMIN_LINKS).status_code == 200
        assert client.get(self.TICKETS).status_code == 200
