"""Base settings — 12-factor, all values from environment with safe dev defaults."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent

load_dotenv(REPO_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # third-party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    # project apps
    "apps.core",
    "apps.catalog",
    "apps.search",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database: postgres (default) or sqlite (host-only / tests) ---
DB_ENGINE = os.getenv("DB_ENGINE", "postgres").lower()
if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("SQLITE_PATH", "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "techbase"),
            "USER": os.getenv("DB_USER", "techbase"),
            "PASSWORD": os.getenv("DB_PASSWORD", "techbase"),
            "HOST": os.getenv("DB_HOST", "db"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF / schema ---
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Rate limiting is enabled in Phase 6 with explicit DEFAULT_THROTTLE_RATES.
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min", "chat": "20/min"},
}
SPECTACULAR_SETTINGS = {
    "TITLE": "TechBase API",
    "DESCRIPTION": "Knowledge base + catalog + RAG endpoints (Persian-first).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Celery / Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TIME_LIMIT = 120
CELERY_BEAT_SCHEDULE_FILE = os.getenv("CELERY_BEAT_SCHEDULE_FILE", "/tmp/celerybeat-schedule")
CELERY_BEAT_SCHEDULE: dict[str, dict] = {}

# --- Meilisearch ---
MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "")

# --- LLM / embeddings (consumed in Phase 4+) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "claude-sonnet-4-5")
LLM_UNDERSTAND_MODEL = os.getenv("LLM_UNDERSTAND_MODEL", "claude-haiku-4-5")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "bge-m3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "console")  # console | json
LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
        "json": {"()": "pythonjsonlogger.jsonlogger.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "console",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
