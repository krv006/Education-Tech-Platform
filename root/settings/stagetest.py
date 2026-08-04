"""Lokal diagnostika: prod'dagi kabi DEBUG=False + WhiteNoise manifest static.
Faqat 500 xatolarni lokalda qayta tiklash uchun — deploy'da ishlatilmaydi."""
from .dev import *  # noqa: F401,F403
from .dev import MIDDLEWARE

DEBUG = False

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'whitenoise.middleware.WhiteNoiseMiddleware',
)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'apps.core.staticfiles.ForgivingManifestStaticFilesStorage'},
}
