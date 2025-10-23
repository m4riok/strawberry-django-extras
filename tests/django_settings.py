from datetime import timedelta

from django.db import models
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet

# Enable type hinting for Django models
for cls in [QuerySet, BaseManager, models.ForeignKey, models.ManyToManyField]:
    if not hasattr(cls, "__class_getitem__"):
        cls.__class_getitem__ = classmethod(
            lambda cls, *args, **kwargs: cls,
        )

DEBUG = True
SECRET_KEY = "test-secret-key-for-jwt-testing"
USE_TZ = True
TIME_ZONE = "UTC"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "strawberry_django_extras",
    "strawberry_django_extras.jwt.refresh_token",
    "tests",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "strawberry_django_extras.jwt.middleware.jwt_middleware",
]

AUTHENTICATION_BACKENDS = [
    "strawberry_django_extras.jwt.backend.JWTBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "tests.urls"

# JWT Settings
GRAPHQL_JWT = {
    "JWT_ALGORITHM": "HS256",
    "JWT_VERIFY_EXPIRATION": False,  # Default to False for most tests
    "JWT_EXPIRATION_DELTA": timedelta(minutes=5),
    "JWT_ALLOW_REFRESH": False,  # Default to False, individual tests can override
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    },
}
