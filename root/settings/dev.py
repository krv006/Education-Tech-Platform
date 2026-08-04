"""Development settings — sqlite fallback, permissive CORS, verbose errors."""
import os
import sys

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, REST_FRAMEWORK

# Test rejimida throttle xalaqit bermasin va video yozuv avto-start
# (fon thread + tarmoq) o'chib turadi
if 'test' in sys.argv:
    REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_CLASSES': []}
    RECORDINGS_AUTO_START = False

DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'

if os.getenv('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB'),
            'USER': os.getenv('POSTGRES_USER', 'edtech'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

if not os.getenv('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'edtech-dev',
        }
    }
