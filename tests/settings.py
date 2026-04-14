from pathlib import Path

from config.settings import *  # noqa: F403,F401


SECRET_KEY = SECRET_KEY or "test-secret-key"  # type: ignore[name-defined]
DEBUG = True

BASE_TEST_DIR = Path(BASE_DIR) / ".test_artifacts"  # type: ignore[name-defined]
BASE_TEST_DIR.mkdir(exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_TEST_DIR / "test_db.sqlite3"),
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_TEST_DIR / "media"
STATIC_ROOT = BASE_TEST_DIR / "staticfiles"
MEDIA_ROOT.mkdir(exist_ok=True)
STATIC_ROOT.mkdir(exist_ok=True)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

AI_API_KEY = ""
AI_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
