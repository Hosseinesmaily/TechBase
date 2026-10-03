"""pytest settings.

Defaults to in-memory SQLite so tests run without Docker.
Set TEST_DB_ENGINE=postgres to run against PostgreSQL + pgvector
(used for tests marked `pgvector`).
"""

import os

from .dev import *  # noqa: F403

TEST_DB_ENGINE = os.getenv("TEST_DB_ENGINE", "sqlite").lower()

if TEST_DB_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "techbase_test"),
            "USER": os.getenv("DB_USER", "techbase"),
            "PASSWORD": os.getenv("DB_PASSWORD", "techbase"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
