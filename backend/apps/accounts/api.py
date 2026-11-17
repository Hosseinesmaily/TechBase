from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product

from .models import Cart, CartItem

MAX_ITEM_QUANTITY = 99


def _user_data(user) -> dict:
    return {
        "id": user.pk,
        "email": user.email,
        "name": user.get_full_name() or user.email,
        "is_staff": user.is_staff,
    }


def _csrf_token(request) -> str:
    return get_token(request._request)


class CsrfTokenView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request) -> Response:
        return Response({"csrf_token": _csrf_token(request)})


class CurrentUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request) -> Response:
        if not request.user.is_authenticated:
            return Response({"authenticated": False, "user": None})
        return Response({"authenticated": True, "user": _user_data(request.user)})


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request) -> Response:
        email = str(request.data.get("email", "")).strip().casefold()
        name = str(request.data.get("name", "")).strip()[:150]
        password = str(request.data.get("password", ""))
        if not email or not password:
            return Response(
                {"error": "ایمیل و گذرواژه را وارد کنید."}, status=status.HTTP_400_BAD_REQUEST
            )

        user_model = get_user_model()
        try:
            user_model._meta.get_field("email").clean(email, None)
        except ValidationError:
            return Response({"error": "ایمیل معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
        if (
            user_model.objects.filter(email__iexact=email).exists()
            or user_model.objects.filter(username__iexact=email).exists()
        ):
            return Response(
                {"error": "با این ایمیل قبلاً حساب ساخته شده است."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            validate_password(password)
        except ValidationError as exc:
            return Response({"error": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user = user_model.objects.create_user(
            username=email,
            email=email,
            first_name=name,
            password=password,
        )
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(
            {"user": _user_data(user), "csrf_token": _csrf_token(request)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request) -> Response:
        email = str(request.data.get("email", "")).strip().casefold()
        password = str(request.data.get("password", ""))
        user_model = get_user_model()
        account = user_model.objects.filter(email__iexact=email).first()
        username = account.username if account is not None else email
        user = authenticate(request=request._request, username=username, password=password)
        if user is None:
            return Response(
                {"error": "ایمیل یا گذرواژه درست نیست."}, status=status.HTTP_400_BAD_REQUEST
            )
        login(request._request, user)
        return Response({"user": _user_data(user), "csrf_token": _csrf_token(request)})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        logout(request._request)
        return Response({"authenticated": False})


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(_serialize_cart(cart))


class CartItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request) -> Response:
        sku = str(request.data.get("sku", "")).strip()
        try:
            quantity = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            return Response({"error": "تعداد معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quantity <= MAX_ITEM_QUANTITY:
            return Response(
                {"error": f"تعداد باید بین ۱ تا {MAX_ITEM_QUANTITY} باشد."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(
            Product.objects.select_for_update().select_related("entity"), sku=sku, is_active=True
        )
        if product.stock < 1:
            return Response({"error": "این محصول در حال حاضر موجود نیست."}, status=409)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )
        if not created:
            quantity += item.quantity
        if quantity > min(product.stock, MAX_ITEM_QUANTITY):
            if created:
                item.delete()
            return Response(
                {"error": f"حداکثر تعداد قابل افزودن از موجودی فعلی {product.stock} عدد است."},
                status=409,
            )
        if not created:
            item.quantity = quantity
            item.save(update_fields=["quantity", "updated_at"])
        return Response(_serialize_cart(cart), status=status.HTTP_201_CREATED if created else 200)

    def patch(self, request) -> Response:
        sku = str(request.data.get("sku", "")).strip()
        try:
            quantity = int(request.data.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        if not 1 <= quantity <= MAX_ITEM_QUANTITY:
            return Response({"error": "تعداد باید بین ۱ تا ۹۹ باشد."}, status=400)

        cart = get_object_or_404(Cart, user=request.user)
        item = get_object_or_404(
            CartItem.objects.select_related("product__entity"), cart=cart, product__sku=sku
        )
        if quantity > item.product.stock:
            return Response({"error": f"موجودی فعلی فقط {item.product.stock} عدد است."}, status=409)
        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])
        return Response(_serialize_cart(cart))

    def delete(self, request) -> Response:
        sku = str(request.query_params.get("sku", "")).strip()
        cart = get_object_or_404(Cart, user=request.user)
        CartItem.objects.filter(cart=cart, product__sku=sku).delete()
        return Response(_serialize_cart(cart))


def _serialize_cart(cart: Cart) -> dict:
    items = list(cart.items.select_related("product__entity").order_by("created_at"))
    total = sum((item.product.price * item.quantity for item in items), Decimal("0"))
    return {
        "items": [
            {
                "sku": item.product.sku,
                "title": item.product.display_title,
                "entity_slug": item.product.entity.slug,
                "quantity": item.quantity,
                "price": str(item.product.price),
                "currency": item.product.currency,
                "stock": item.product.stock,
                "in_stock": item.product.in_stock,
                "subtotal": str(item.product.price * item.quantity),
                "price_updated_at": item.product.price_updated_at.isoformat()
                if item.product.price_updated_at
                else None,
            }
            for item in items
        ],
        "item_count": sum(item.quantity for item in items),
        "total": str(total),
        "currency": "IRT",
    }
