"""Access-control tests for the admin entry points.

`/adminpanel` (Nuxt) only redirects; the real gate is the Django/Wagtail admin.
These tests pin that gate, because "the link is not obvious" is not a security
control: anonymous visitors and signed-in non-staff accounts must both be sent to
the login page, and only staff may reach the admin index.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db


def _user(**kwargs):
    model = get_user_model()
    user = model.objects.create_user(
        username=kwargs.pop("username"), password="test-password-8123", **kwargs
    )
    return user


class TestDjangoAdminAccess:
    def test_anonymous_is_redirected_to_the_login(self):
        response = Client().get("/admin/")
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_signed_in_non_staff_is_refused(self):
        client = Client()
        client.force_login(_user(username="plain-customer", is_staff=False, is_active=True))
        response = client.get("/admin/")
        # Django's admin refuses a non-staff session and sends it back to login.
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_inactive_staff_is_refused(self):
        client = Client()
        client.force_login(_user(username="inactive-staff", is_staff=True, is_active=False))
        response = client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_staff_reaches_the_index(self):
        client = Client()
        client.force_login(_user(username="editor", is_staff=True, is_active=True))
        response = client.get("/admin/")
        assert response.status_code == 200

    def test_the_login_page_itself_is_public(self):
        response = Client().get("/admin/login/")
        assert response.status_code == 200

    def test_a_protected_admin_view_is_not_publicly_readable(self):
        """/api/v1/ai/logs/ is staff-only on the API side too."""
        assert Client().get("/api/v1/ai/logs/").status_code == 403


class TestWagtailAdminAccess:
    def test_anonymous_is_redirected_to_the_login(self):
        response = Client().get("/cms/")
        assert response.status_code == 302
        assert "/cms/login/" in response["Location"]

    def test_staff_without_a_wagtail_permission_is_refused(self):
        """Django's `is_staff` is not enough: Wagtail's admin needs its own access."""
        client = Client()
        client.force_login(_user(username="wagtail-staff-only", is_staff=True, is_active=True))
        response = client.get("/cms/")
        assert response.status_code == 302
        assert "/cms/login/" in response["Location"]

    def test_superuser_reaches_the_cms(self):
        client = Client()
        client.force_login(
            _user(
                username="wagtail-owner",
                is_staff=True,
                is_active=True,
                is_superuser=True,
            )
        )
        response = client.get("/cms/")
        assert response.status_code == 200
