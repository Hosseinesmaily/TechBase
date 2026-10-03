import os

from .base import *  # noqa: F403

DEBUG = False

if not os.getenv("DJANGO_SECRET_KEY") or os.getenv("DJANGO_SECRET_KEY") == "change-me-in-prod":
    raise RuntimeError("DJANGO_SECRET_KEY must be set to a real value in production")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# CORS is handled by the Nuxt proxy in v1; keep origins explicit if opened later.
ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]  # noqa: F405

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_PERMISSIONS": []}  # noqa: F405
