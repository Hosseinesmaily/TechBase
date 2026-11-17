from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Cart, CartItem
from apps.catalog.models import Entity, EntityStatus, EntityType, Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    entity = Entity.objects.create(
        type=EntityType.GPU,
        slug="test-gpu",
        title="Test GPU",
        title_fa="کارت گرافیک آزمایشی",
        status=EntityStatus.PUBLISHED,
    )
    return Product.objects.create(
        sku="test-gpu-sku",
        entity=entity,
        title="Test GPU",
        title_fa="کارت گرافیک آزمایشی",
        price="12000000",
        currency="IRT",
        stock=3,
        is_active=True,
    )


def csrf_headers(client: APIClient) -> dict[str, str]:
    response = client.get(reverse("accounts:csrf"))
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.data["csrf_token"]}


class TestRegistration:
    def test_registration_requires_csrf_and_creates_a_unique_user(self):
        client = APIClient(enforce_csrf_checks=True)
        data = {
            "email": "customer@example.com",
            "name": "کاربر آزمایشی",
            "password": "Test-Password-8291!",
        }

        denied = client.post(reverse("accounts:register"), data, format="json")
        assert denied.status_code == 403

        created = client.post(
            reverse("accounts:register"), data, format="json", **csrf_headers(client)
        )
        assert created.status_code == 201
        assert created.data["user"]["email"] == "customer@example.com"
        assert client.get(reverse("accounts:me")).data["authenticated"] is True

        duplicate = client.post(
            reverse("accounts:register"),
            {**data, "email": "CUSTOMER@example.com"},
            format="json",
            **csrf_headers(client),
        )
        assert duplicate.status_code == 409
        assert get_user_model().objects.filter(email="customer@example.com").count() == 1

    def test_login_and_logout_use_the_session(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password="Test-Password-8291!",
        )
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            reverse("accounts:login"),
            {"email": "login@example.com", "password": "Test-Password-8291!"},
            format="json",
            **csrf_headers(client),
        )
        assert response.status_code == 200
        assert client.get(reverse("accounts:me")).data["authenticated"] is True

        logout_response = client.post(
            reverse("accounts:logout"), {}, format="json", **csrf_headers(client)
        )
        assert logout_response.status_code == 200
        assert client.get(reverse("accounts:me")).data["authenticated"] is False


class TestShoppingCart:
    def test_cart_is_private_to_each_user_and_checks_stock(self, product):
        user_model = get_user_model()
        first_user = user_model.objects.create_user(username="first@example.com")
        second_user = user_model.objects.create_user(username="second@example.com")
        first_client = APIClient()
        first_client.force_authenticate(first_user)
        second_client = APIClient()
        second_client.force_authenticate(second_user)

        added = first_client.post(
            reverse("accounts:cart-items"),
            {"sku": product.sku, "quantity": 2},
            format="json",
        )
        assert added.status_code == 201
        assert added.data["item_count"] == 2
        assert added.data["total"] == "24000000.00"

        too_many = first_client.post(
            reverse("accounts:cart-items"),
            {"sku": product.sku, "quantity": 2},
            format="json",
        )
        assert too_many.status_code == 409

        second_cart = second_client.get(reverse("accounts:cart"))
        assert second_cart.status_code == 200
        assert second_cart.data["items"] == []
        assert Cart.objects.count() == 2
        assert CartItem.objects.filter(cart__user=first_user).count() == 1
        assert CartItem.objects.filter(cart__user=second_user).count() == 0
