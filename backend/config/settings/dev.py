from .base import *  # noqa: F403
from .base import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

# Dev conveniences — never imported by prod settings.
SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_INCLUDE_SCHEMA": True}  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
