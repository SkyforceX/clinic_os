import os
from pathlib import Path
from datetime import date

import environ

BASE_DIR = Path(__file__).resolve().parent.parent   # /srv/clinic_os/app
ROOT_DIR = BASE_DIR.parent         		# /srv/clinic_os
env= environ.Env()                 
ENV_FILE = ROOT_DIR / "env" / ".env"

if ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))
else:
    raise FileNotFoundError(f"Không t́m th?y file env: {ENV_FILE}")
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
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-secret")
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = [
    x.strip()
    for x in env("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
    if x.strip()
]

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://khachhang.vietmediclinic.com"],
)
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==== HIS MSSQL CONNECTION SETTINGS ==== #
HIS_MSSQL = {
    "DRIVER": os.getenv("HIS_DB_DRIVER", "{ODBC Driver 18 for SQL Server}"),
    "SERVER": os.getenv("HIS_DB_HOST"),
    "PORT": os.getenv("HIS_DB_PORT", "1433"),
    "DATABASE": os.getenv("HIS_DB_NAME"),
    "UID": os.getenv("HIS_DB_USER"),
    "PWD": os.getenv("HIS_DB_PASSWORD"),
    "TRUST_SERVER_CERTIFICATE": os.getenv("HIS_DB_TRUST_CERT", "yes"),
    "TIMEOUT": int(os.getenv("HIS_DB_TIMEOUT", "5")),
}

# ==== HIS AUTOMATION ==== #
# HIS_AUTOMATION = {
#     "BASE_URL": env("HIS_BASE_URL", default="https://bvhcm.vncare.vn/vnpthis/main/manager.jsp"),
#     "USERNAME": env("HIS_USERNAME", default=""),
#     "PASSWORD": env("HIS_PASSWORD", default=""),
#     "FORM_FUNC": env("HIS_FORM_FUNC", default="../ksk/KSK01D004_KetQuaKham"),
#     "IFRAME_SELECTOR": env("HIS_IFRAME_SELECTOR", default="iframe#ifmain"),
#     "HEADLESS": env.bool("HIS_HEADLESS", True),
#     "SLOW_MO_MS": env.int("HIS_SLOW_MO_MS", 0),
# }

# local dev http sẽ đỡ bị kẹt cookie hơn
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "SAMEORIGIN"

RESULTS_ROOT = os.environ.get("RESULTS_ROOT", r"D:\data\results")
RESULTS_URL = "/data/results"

QUALITY_AUDIT_TEMPLATE = BASE_DIR / "templates" / "word" / "medical_record_audit_template.docx"
QUALITY_DOCX_TMP_DIR = Path(
    env("QUALITY_DOCX_TMP_DIR", default=str(ROOT_DIR / "tmp_docs"))
)
QUALITY_DOCX_TMP_DIR.mkdir(parents=True, exist_ok=True)

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
    "apps.dashboard",
    "apps.approvals",
    "apps.organizations",
    "apps.patients",
    "apps.contract",
    "apps.scheduling",
    "apps.reception",
    "apps.record_completion",
    "apps.clinical",
    "apps.catalogs",
    "apps.notifications",
    "apps.hrm",
    "apps.analytics",
    "apps.targets",
    "apps.retention",
    "apps.meeting",
    "apps.tasks",
    "apps.engagement",
    "apps.procedures",
    "apps.media_library",
    "apps.ai_assistant",
    "apps.helpdesk",

    # DRF
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "channels",

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
                "apps.ai_assistant.context_processors.ai_assistant",
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

STATIC_URL  = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", default=BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [
    Path(env("STATICFILES_DIRS", default=BASE_DIR / "static"))
]

MEDIA_URL  = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "authentication:patient_login"

CSRF_FAILURE_VIEW = "apps.core.views.custom_csrf_failure"

# ─── Cấu hình Ollama ───────────────────────────────────────────────
# URL tới Ollama server (dùng env variable để dễ đổi giữa môi trường)
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://127.0.0.1:11434")
OLLAMA_MODEL    = env("OLLAMA_MODEL",    default="qwen2.5:3b")
OLLAMA_TIMEOUT  = int(env("OLLAMA_TIMEOUT", default="120"))

OLLAMA_SYSTEM_PROMPT = (
    "Bạn là trợ lý nội bộ của hệ thống quản lý khám sức khỏe doanh nghiệp ClinicOS. "
    "Nhiệm vụ của bạn là hỗ trợ đội ngũ quản lý về các vấn đề: "
    "hợp đồng khám sức khỏe, báo giá dịch vụ, lên lịch khám, quản lý nhân sự phòng khám, "
    "và các quy trình vận hành nội bộ. "
    "Luôn trả lời bằng tiếng Việt, ngắn gọn, chính xác và thực tế."
)

# Nhóm được phép dùng AI assistant (ngoài superadmin)
# Tên group phải khớp đúng với Group.name trong database
AI_ASSISTANT_ALLOWED_GROUPS = ["Executives"]

AI_BASE_URL = env("AI_BASE_URL", default="http://127.0.0.1:11434")
AI_MODEL = env("AI_MODEL", default="Qwen/Qwen2.5-3B-Instruct")
AI_API_KEY = env("AI_API_KEY", default="")
AI_TIMEOUT = env.int("AI_TIMEOUT", default=120)

AI_SYSTEM_PROMPT = env(
    "AI_SYSTEM_PROMPT",
    default=(
        "Bạn là trợ lý nội bộ của phòng khám doanh nghiệp ClinicOS. "
        "Nhiệm vụ của bạn là hỗ trợ đội ngũ quản lý về nghiệp vụ khám sức khỏe doanh nghiệp, "
        "hợp đồng, báo giá, lên lịch, và các vấn đề vận hành. "
        "Luôn trả lời bằng tiếng Việt, ngắn gọn và chính xác."
    ),
)

# ==== PDF / DOCUMENT SETTINGS ==== #
LIBREOFFICE_PATH = env("LIBREOFFICE_PATH", default="/usr/bin/soffice")
PDF_ENGINE = env("PDF_ENGINE", default="auto")  # auto | weasy | libreoffice
PDF_PREFER_HTML = env.bool("PDF_PREFER_HTML", default=True)
PDF_CONVERT_TIMEOUT = env.int("PDF_CONVERT_TIMEOUT", default=180)
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="https://khachhang.vietmediclinic.com")


# thêm vào .env:
TESSERACT_BIN=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_BIN=r"C:\path\to\poppler\bin"


CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_BEAT_SCHEDULE = {
    "auto-terminate-contracts-daily": {
        "task": "booking.tasks.auto_terminate_contracts",
        "schedule": 86400,
    },
}
CELERY_TIMEZONE = "Asia/Ho_Chi_Minh"

# =====================================
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
CHANNEL_LAYERS = { "default": { "BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]} } }
# =====================================

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
    "loggers": {
        "apps.ai_assistant": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

PATIENT_SEARCH_START = date(2025, 1, 1)