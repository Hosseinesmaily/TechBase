import os

from celery import Celery

# Respect an explicit DJANGO_SETTINGS_MODULE (production containers set it);
# fall back to dev for local runs.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("techbase")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
