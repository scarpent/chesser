import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from django.utils import timezone


def get_local_ip():
    """Returns the LAN IP address, e.g., 192.168.x.x"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Doesn't send any data
        s.connect(("8.8.8.8", 80))  # Connect to any public IP (doesn't send packets)
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Could not determine local IP: {e}")
        return None


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "fallback-secret-key")

# --------------------------------------------------------------------
# Environment inputs (only raw env reads here)
# --------------------------------------------------------------------

CHESSER_ENV = os.getenv("CHESSER_ENV", "development").lower()
IS_HOSTED = os.getenv("CHESSER_HOSTED", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

CHESSER_URL = os.getenv("CHESSER_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL")

# --------------------------------------------------------------------
# Derived flags (no side effects / no guards)
# --------------------------------------------------------------------

IS_DEVELOPMENT = CHESSER_ENV == "development"
IS_PRODUCTION = CHESSER_ENV == "production"
IS_DEMO = CHESSER_ENV == "demo"

# --------------------------------------------------------------------
# Computed values (pure derivations)
# --------------------------------------------------------------------

parsed = urlparse(CHESSER_URL)
CHESSER_HOST = parsed.hostname  # hostname only, no scheme/port

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if CHESSER_HOST and CHESSER_HOST not in ("localhost", "127.0.0.1"):
    ALLOWED_HOSTS.append(CHESSER_HOST)

INTERNAL_IPS = ["localhost", "127.0.0.1"]

if IS_DEVELOPMENT and not IS_HOSTED:
    # In local dev/demo, allow LAN IP for phone testing, etc.
    if local_ip := get_local_ip():
        print(f"Local LAN access enabled: http://{local_ip}:8000")
        ALLOWED_HOSTS.append(local_ip)

# --------------------------------------------------------------------
# Database
# --------------------------------------------------------------------

if IS_PRODUCTION:
    DATABASES = {"default": dj_database_url.config(default=DATABASE_URL)}
else:
    sqlite_name = "chesser_demo.sqlite3" if IS_DEMO else "chesser.sqlite3"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "data" / sqlite_name,
        }
    }

# --------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------

VALID_ENVS = {"development", "demo", "production"}
if CHESSER_ENV not in VALID_ENVS:
    raise ValueError(
        f"Invalid CHESSER_ENV={CHESSER_ENV!r}; must be one of {sorted(VALID_ENVS)}"
    )

# If hosted, require CHESSER_URL be a real URL with a scheme
if IS_HOSTED and "://" not in CHESSER_URL:
    raise ValueError(
        "CHESSER_URL must include scheme when hosted, e.g. https://example.com"
    )

if IS_PRODUCTION and not DATABASE_URL:
    raise ValueError("DATABASE_URL is required when CHESSER_ENV=production")

# If production, prevent accidental localhost deployment.
if IS_PRODUCTION and CHESSER_HOST in ("localhost", "127.0.0.1"):
    raise ValueError("Refusing production mode with localhost CHESSER_URL/host")

if IS_HOSTED and CHESSER_HOST in ("localhost", "127.0.0.1", None):
    raise ValueError("CHESSER_URL must be set to the public hostname when hosted")

# --------------------------------------------------------------------

INSTALLED_APPS = [
    "chesser",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "whitenoise.runserver_nostatic",  # serves static files in dev & prod
    "django_extensions",
    "djangoql",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "chesser.middleware.SecurityHeadersMiddleware",
    # WhiteNoise should come immediately after SecurityMiddleware
    # to ensure security headers are applied before serving static files
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "chesser.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "chesser.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "chesser.context_processors.template_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "chesser.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
# Global static directory
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
# Ensure this line is present to collect static files from apps
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 365  # One year in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Keep dev easy: no forced HTTPS, no HSTS.
# Make prod strict: HSTS + secure cookies + redirect.

# Defaults (non-hosted)
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = None  # or omit entirely

# Hosted overrides
if IS_HOSTED:
    # Redirect HTTP -> HTTPS at Django level
    SECURE_SSL_REDIRECT = True

    # Ensure Django correctly detects HTTPS requests (e.g. via proxy)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # SecurityMiddleware uses these; they're harmless and good practice.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"


# --- Security headers added via custom middleware ---
# CSP: starter policy that won't break Alpine or inline scripts/styles.

# script-src includes 'unsafe-eval' for Alpine.js expression evaluation,
# and 'unsafe-inline' for current inline scripts/styles used by the app.
# (e.g. buttons don't work without 'unsafe-inline')

CHESSER_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "form-action 'self'",
    ]
)

# Disable browser features Chesser doesn't need.
CHESSER_PERMISSIONS_POLICY = ", ".join(
    [
        "camera=()",
        "microphone=()",
        "geolocation=()",
        "usb=()",
        "payment=()",
    ]
)


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Set the maximum size for uploaded files (in bytes)
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

BUILD_STARTED_AT = timezone.now()
BUILD_TIMESTAMP = str(int(time.time()))

# Increase the limit for number of fields in forms (fixes chapter saving issue)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

REPETITION_INTERVALS = {  # Level value is hours
    1: 7,
    2: 1 * 24,
    3: 3 * 24,
    4: 7 * 24,
    5: 14 * 24,
    6: 30 * 24,
    7: 60 * 24,
    8: 120 * 24,
    9: 180 * 24,
}
# Chessable intervals:
# Was it this at one time?
#   4h, 19h, 2d23h, 6d23h, 13d23h, 29d23h, 89d23h, 179d23h
# Custom schedule now starts with this:
#   4 hr, 10 hr, 1 day, 2.5 days, 1 week, 2.5 weeks, 1.5 months, 4 months

STATS_START_DATE = (2025, 9, 26)

# Scheduler hours can be fractional, e.g., 0.5 for 30 minutes
HEARTBEAT_INTERVAL_HOURS = 1
BACKUP_INTERVAL_HOURS = 24
# First run happens N minutes after start
HEARTBEAT_STARTUP_DELAY_MINUTES = 1
BACKUP_STARTUP_DELAY_MINUTES = 30


try:
    from .local_settings import *  # noqa: F401, F403
except ImportError:
    pass
