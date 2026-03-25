import os
from pathlib import Path
from datetime import date

from dotenv import load_dotenv
import environ


def env_list(name, default=None):
    raw = os.getenv(name, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    if items:
        return items
    return default[:] if isinstance(default, list) else (default or [])


BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
load_dotenv(os.path.join(BASE_DIR, ".env"))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ==== HIS AUTOMATION ==== #
HIS_AUTOMATION = {
    "BASE_URL": env("HIS_BASE_URL", default="https://bvhcm.vncare.vn/vnpthis/main/manager.jsp"),
    "USERNAME": env("HIS_USERNAME", default=""),
    "PASSWORD": env("HIS_PASSWORD", default=""),
    "FORM_FUNC": env("HIS_FORM_FUNC", default="../ksk/KSK01D004_KetQuaKham"),
    "IFRAME_SELECTOR": env("HIS_IFRAME_SELECTOR", default="iframe#ifmain"),
    "HEADLESS": env.bool("HIS_HEADLESS", True),
    "SLOW_MO_MS": env.int("HIS_SLOW_MO_MS", 0),
}

# ==== SETTINGS ==== #
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["khachhang.vietmediclinic.com", "localhost", "127.0.0.1"],
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://khachhang.vietmediclinic.com",
    ],
)

USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# local dev http sẽ đỡ bị kẹt cookie hơn
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "SAMEORIGIN"

RESULTS_ROOT = os.environ.get("RESULTS_ROOT", r"D:\data\results")
RESULTS_URL = "/data/results"

QUALITY_AUDIT_TEMPLATE = BASE_DIR / "templates" / "word" / "medical_record_audit_template.docx"
QUALITY_DOCX_TMP_DIR = BASE_DIR / "tmp_docs"
QUALITY_DOCX_TMP_DIR.mkdir(exist_ok=True)

LIBREOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "background_task",

    # legacy / transitional
    "apps.core",
    "apps.authentication",
    "apps.account",
    "apps.booking",
    "apps.sum_report",
    "apps.quality",

    # refactor apps
    "apps.organizations",
    "apps.patients",
    "apps.contract",
    "apps.scheduling",
    "apps.clinical",

    # DRF
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",

    # API app
    "apps.api_his",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

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
        "DIRS": [BASE_DIR / "templates"],
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

ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DJANGO_DB_NAME"),
        "USER": os.getenv("DJANGO_DB_USER"),
        "PASSWORD": os.getenv("DJANGO_DB_PASSWORD"),
        "HOST": os.getenv("DJANGO_DB_HOST"),
        "PORT": os.getenv("DJANGO_DB_PORT"),
        "OPTIONS": {
            "sslmode": "disable",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "vi-vn"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "authentication:patient_login"

CSRF_FAILURE_VIEW = "apps.core.views.custom_csrf_failure"

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_BEAT_SCHEDULE = {
    "auto-terminate-contracts-daily": {
        "task": "booking.tasks.auto_terminate_contracts",
        "schedule": 86400,
    },
}
CELERY_TIMEZONE = "Asia/Ho_Chi_Minh"

# Zalo API settings - đưa sang env
ZALO_ACCESS_TOKEN = env("ZALO_ACCESS_TOKEN", default="")
ZALO_TEMPLATE_ID = env("ZALO_TEMPLATE_ID", default="")
ZALO_APP_SECRET = env("ZALO_APP_SECRET", default="")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "api.log"),
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG",
    },
}

PATIENT_SEARCH_START = date(2025, 1, 1)