"""Production settings — hardened. Requires real env values, refuses insecure defaults."""
import os

from .base import *  # noqa: F401,F403

DEBUG = False

if os.getenv('SECRET_KEY', '').startswith('django-insecure') or not os.getenv('SECRET_KEY'):
    raise RuntimeError('PROD: haqiqiy SECRET_KEY .env da berilishi shart.')
if not os.getenv('POSTGRES_DB'):
    raise RuntimeError('PROD: Postgres majburiy (POSTGRES_DB va h.k.).')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}

# Security hardening
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'DENY'
