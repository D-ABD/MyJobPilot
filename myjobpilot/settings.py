"""Configuration Django, pilotée par les variables d'environnement."""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("La variable SECRET_KEY doit être définie dans .env ou dans l'environnement.")

DEBUG = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

# CSRF : origines de confiance (Django 4+)
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")
]

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}

# Quotas documents
DOCUMENT_MAX_SIZE_BYTES = 5 * 1024 * 1024
DOCUMENT_QUOTA_BYTES = 20 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 Mo par requête
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5 Mo par fichier en mémoire

# Rétention RGPD
RETENTION_COMPTE_DESACTIVE_JOURS = 1095
RETENTION_COMPTE_NON_VALIDE_JOURS = 180
RETENTION_JOURNAL_JOURS = 1095

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core.apps.CoreConfig",
    "comptes.apps.ComptesConfig",
    "entreprises.apps.EntreprisesConfig",
    "staff.apps.StaffConfig",
    "documents.apps.DocumentsConfig",
    "rgpd.apps.RgpdConfig",
    "admin_dashboard.apps.AdminDashboardConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "comptes.middleware.ValidationCompteMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myjobpilot.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myjobpilot.wsgi.application"
ASGI_APPLICATION = "myjobpilot.asgi.application"
AUTH_USER_MODEL = "comptes.Utilisateur"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "comptes:connexion"
LOGIN_REDIRECT_URL = "comptes:redirection_apres_login"
LOGOUT_REDIRECT_URL = "comptes:connexion"

# Configuration de production (si DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REFERRER_POLICY = "same-origin"

# Logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMATTERS = {
    "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
}
_LOG_HANDLERS = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "standard",
    },
}
_LOG_HANDLERS["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOG_DIR / "app.log"),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 3,
        "formatter": "standard",
        "encoding": "utf-8",
    }

_ACTIVE_HANDLERS = ["console", "file"] if DEBUG else ["console"]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": _LOG_FORMATTERS,
    "handlers": _LOG_HANDLERS,
    "loggers": {
        "django.request": {
            "handlers": _ACTIVE_HANDLERS,
            "level": "ERROR",
            "propagate": False,
        },
        "comptes": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Emails transactionnels (Brevo SMTP)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "noreply@myjobpilot.adserv.fr"
)

# Alertes email en cas d'erreur 500
ADMINS = [("ABD", "adserv.fr@gmail.com")]
MANAGERS = ADMINS

# Durée de session (7 jours)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
