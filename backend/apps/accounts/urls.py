from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.core.csrf import protect_csrf

from . import api

app_name = "accounts"


urlpatterns = [
    path("csrf/", ensure_csrf_cookie(api.CsrfTokenView.as_view()), name="csrf"),
    path("me/", api.CurrentUserView.as_view(), name="me"),
    path("register/", protect_csrf(api.RegisterView.as_view()), name="register"),
    path("login/", protect_csrf(api.LoginView.as_view()), name="login"),
    path("logout/", protect_csrf(api.LogoutView.as_view()), name="logout"),
    path("cart/", api.CartView.as_view(), name="cart"),
    path("cart/items/", api.CartItemView.as_view(), name="cart-items"),
]
