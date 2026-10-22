import os

from .base import *  # noqa: F403

DEBUG = False

# Both the documented placeholder AND the built-in dev fallback are rejected —
# otherwise an unset DJANGO_SECRET_KEY would silently boot production with a
# publicly known key (base.py's default).
_FORBIDDEN_SECRET_KEYS = {"", "change-me-in-prod", "insecure-dev-key", "dev-only-not-a-secret"}
_secret = os.getenv("DJANGO_SECRET_KEY", "")
if _secret.strip().lower() in _FORBIDDEN_SECRET_KEYS:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a real, unique value in production "
        "(the dev default is refused)."
    )
SECRET_KEY = _secret

ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]  # noqa: F405
# The container's own hostname must always be accepted (compose service name).
if "backend" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("backend")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS is handled by the Nuxt proxy in v1; keep origins explicit if opened later.
SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_PERMISSIONS": []}  # noqa: F405
