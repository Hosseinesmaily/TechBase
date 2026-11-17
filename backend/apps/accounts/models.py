from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel


class Cart(TimeStampedModel):
    """One persistent shopping cart per authenticated customer."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shopping_cart"
    )

    class Meta:
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"

    def __str__(self) -> str:
        return f"سبد خرید کاربر {self.user_id}"


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "قلم سبد خرید"
        verbose_name_plural = "اقلام سبد خرید"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_cart_product"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cart_qty_min_1"),
        ]

    def __str__(self) -> str:
        return f"{self.product.sku} × {self.quantity}"
