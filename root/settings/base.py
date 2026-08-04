"""Base settings — shared by every environment. Env-specific values live in dev.py/prod.py."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-only-key-change-me')

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'daphne',  # runserver'ni ASGI (WebSocket) qiladi — staticfiles'dan OLDIN turishi shart
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'channels',
    # local apps
    'apps.core',
    'apps.accounts',
    'apps.lessons',
    'apps.live',
    'apps.chat',
    'apps.board',
    'apps.homework',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'apps.core.middleware.RequestIDMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'root.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'root.wsgi.application'
ASGI_APPLICATION = 'root.asgi.application'

# Channel layer — chat WebSocket broadcast. Prod: Redis (REDIS_URL),
# dev/test: xotirada (bitta jarayon uchun yetarli).
if os.getenv('REDIS_URL'):
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [os.getenv('REDIS_URL')]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.DefaultPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '240/min',
        'auth': '30/min',   # login / register / OTP — bruteforce himoyasi
    },
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'UPDATE_LAST_LOGIN': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Fokus EdTech API',
    'DESCRIPTION': "Onlayn ta'lim platformasi — jonli darslar, davomat, ota-ona paneli",
    'VERSION': '0.2.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Redis cache (throttling, sessions-ready). REDIS_URL yo'q bo'lsa dev.py locmem beradi.
if os.getenv('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.getenv('REDIS_URL'),
        }
    }

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # frontend (Vercel):
    "https://edu-front-silk.vercel.app",
    # prod API domeni:
    "https://edu.thesofmebel.uz",
]

# Vercel preview buildlari (har deployda yangi subdomen) ham ishlasin
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://[\w.-]+\.vercel\.app$"]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://edu-front-silk.vercel.app",
    "https://edu.thesofmebel.uz",
]

# LiveKit (self-hosted)
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY', 'devkey')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', 'devsecret_change_me_32chars_min!')
LIVEKIT_URL = os.getenv('LIVEKIT_URL', 'ws://localhost:7880')

# Dars video yozuvlari (LiveKit Egress fayllari) — auth endpoint orqali beriladi
RECORDINGS_DIR = Path(os.getenv('RECORDINGS_DIR', BASE_DIR / 'recordings'))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
# Egress konteyneri fayl yozadigan yo'l (uning FS'ida) — compose'da /out
EGRESS_OUTPUT_PREFIX = os.getenv('EGRESS_OUTPUT_PREFIX', '/out')

# Uy vazifasi AI tekshiruvi (Gemini) — apps/homework
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash')
# Tekshiruv fonda (thread) yuradi; testlar False qilib sinxron ishlatadi
HOMEWORK_CHECK_ASYNC = True

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Tashkent')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Logging — konsol + FAYLLAR (logs/ papkasi, rotatsiya bilan) ───
#   logs/app.log     — barcha INFO+ (so'rovlar, servislar)
#   logs/errors.log  — faqat WARNING/ERROR (tez diagnostika uchun)
# Har fayl 5 MB gacha, 5 tadan zaxira (jami ~50 MB chegara).
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'app': {
            'format': '{asctime} {levelname} [{name}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'app'},
        'file_app': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'app.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'app',
            'level': 'INFO',
        },
        'file_errors': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'errors.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'app',
            'level': 'WARNING',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_app', 'file_errors'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['console', 'file_app', 'file_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file_app', 'file_errors'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
