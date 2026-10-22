import os

from django.core.asgi import get_asgi_application

# Default to dev so a local `uvicorn config.asgi:application` works out of the box.
# Production containers set DJANGO_SETTINGS_MODULE=config.settings.prod explicitly.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
