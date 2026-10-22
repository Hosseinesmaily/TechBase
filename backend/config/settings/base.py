"""Base settings — 12-factor, all values from environment with safe dev defaults."""

from __future__ import annotations

import os
from pathlib import Path

from apps.core.log_filters import ScrubFilter
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
    "wagtail",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "modelcluster",
    "taggit",
    # project apps
    "apps.core",
    "apps.catalog",
    "apps.compat",
    "apps.benchmarks",
    "apps.integrations",
    "apps.search",
    "apps.content",
    "apps.linking",
    "apps.ai",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # The rate limiter sits last, so it counts the real request.
    "apps.core.middleware.RateLimitMiddleware",
    # The trace id: one per request, echoed in the X-Trace-Id header.
    "apps.core.observability.trace_middleware",
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
# Only the locales we actually support. Without this, Django's admin offers
# ~90 languages and the UI language follows the browser instead of our product
# language (Persian first, English secondary).
LANGUAGES = [("fa", "فارسی"), ("en", "English")]
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

#: The repository root, used to find `evals/` and other repo-level files.
REPO_DIR = BASE_DIR.parent
#: The RAG golden set (30 Persian + 10 English questions).
GOLDEN_SET_PATH = REPO_DIR / "evals" / "golden_set.jsonl"

# --- Wagtail (CMS for the editorial wiki) ---
WAGTAIL_SITE_NAME = "تک‌بیس"
WAGTAILADMIN_BASE_URL = os.getenv("WAGTAILADMIN_BASE_URL", "http://localhost:8000")
# The editor works in Persian; the admin chrome is translated via LocaleMiddleware.
WAGTAIL_I18N_ENABLED = True
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}
# Editorial workflow: draft → review → published (DECISIONS A1).
WAGTAIL_WORKFLOW_ENABLED = True
WAGTAILIMAGES_IMAGE_MODEL = "wagtailimages.Image"
WAGTAILDOCS_DOCUMENT_MODEL = "wagtaildocs.Document"

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
    # The rate limiting is done by apps.core.middleware.RateLimitMiddleware, so
    # DRF's own throttles stay off — two limiters would fight each other.
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("RATE_LIMIT_ANON", "120/min"),
        "chat": os.getenv("RATE_LIMIT_CHAT", "20/min"),
    },
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
CELERY_BEAT_SCHEDULE: dict[str, dict] = {
    # Nightly inventory/price refresh (mock adapter in v1).
    "sync-inventory-nightly": {
        "task": "integrations.sync_inventory",
        "schedule": 60 * 60 * 3,  # every 3 hours
        "kwargs": {"adapter": "mock"},
    },
    # Nightly link-integrity audit: red links + orphan pages (the editorial
    # backlog) and the repair of the auto-link flags.
    "link-integrity-nightly": {
        "task": "linking.check_integrity",
        "schedule": 60 * 60 * 24,
    },
    # Nightly search reindex, so the lexical index never drifts from the DB.
    "search-reindex-nightly": {
        "task": "search.reindex",
        "schedule": 60 * 60 * 24,
    },
}

# --- Meilisearch ---
MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "")

# --- LLM / embeddings (consumed in Phase 4+) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
# anthropic | openai | fake — empty means "detect from the keys, else fake".
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")
LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "claude-sonnet-4-5")
LLM_UNDERSTAND_MODEL = os.getenv("LLM_UNDERSTAND_MODEL", "claude-haiku-4-5")
# bge-m3 | e5 | hash — "hash" is the dependency-free local fallback.
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# --- Tracing (optional) ---
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "")

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "console")  # console | json
# Personal data (emails, phone numbers, national IDs) is removed from the log
# lines. The raw query stays in the database, where the editorial team can see
# it, but it never reaches a log file.
SCRUB_LOGS = env_bool("SCRUB_LOGS", True)
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
            # Personal data never reaches a log file. The filter is given as a
            # factory, because `dictConfig` calls the callable to build it.
            "filters": [ScrubFilter()],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
