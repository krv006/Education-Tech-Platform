"""Environment-aware settings loader.

DJANGO_ENV=dev (default) -> root.settings.dev
DJANGO_ENV=prod          -> root.settings.prod
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

_ENV = os.getenv('DJANGO_ENV', 'dev').lower()

if _ENV == 'prod':
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
