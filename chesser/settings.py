import os
import socket
import time
from pathlib import Path

import dj_database_url


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

IS_PRODUCTION = (
    os.getenv("RAILWAY_ENVIRONMENT_NAME") is not None
    or os.getenv("DATABASE_URL") is not None
)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "fallback-secret-key")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "chesser-production.up.railway.app",
]
INTERNAL_IPS = ["localhost", "127.0.0.1"]

if not IS_PRODUCTION and os.environ.get("RUN_MAIN") == "true":
    if local_ip := get_local_ip():
        print(f"Local IP: {local_ip}")
        ALLOWED_HOSTS.append(local_ip)  # Allow LAN IP for local development

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
                "chesser.context_processors.build_info",
            ],
        },
    },
]

WSGI_APPLICATION = "chesser.wsgi.application"

if IS_PRODUCTION:
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set along with IS_PRODUCTION.")
    # Parse the DATABASE_URL environment variable (contains password, etc)
    DATABASES = {"default": dj_database_url.config(default=DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "data" / "chesser.sqlite3",
        }
    }

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
SESSION_COOKIE_SECURE = IS_PRODUCTION  # Send session cookie only over HTTPS
SECURE_SSL_REDIRECT = IS_PRODUCTION  # Redirect HTTP to HTTPS in production
CSRF_COOKIE_SECURE = IS_PRODUCTION  # Send CSRF cookie only over HTTPS

# If behind a proxy like Railway/Heroku,
if IS_PRODUCTION:  # ensure Django correctly detects HTTPS requests
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Set the maximum size for uploaded files (in bytes)
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = "chesser"
AWS_S3_REGION_NAME = "us-east-1"

BUILD_TIMESTAMP = str(int(time.time()))

# Enables demo data if database is empty. Intended for first-time
# preview/experimentation. Set to False once initialized to avoid
# automatic demo injection on db reset.
DEMO_DATA_IMPORT = False

CHESSER_URL = (
    "https://chesser-production.up.railway.app"
    if IS_PRODUCTION
    else "http://localhost:8000"
)
