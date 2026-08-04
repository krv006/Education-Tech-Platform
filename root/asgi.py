"""ASGI — HTTP (Django) + WebSocket (Channels, chat).

Prod: gunicorn root.asgi:application -k uvicorn.workers.UvicornWorker
Dev:  python manage.py runserver (daphne INSTALLED_APPS'da — o'zi ASGI beradi)
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'root.settings')

# MUHIM: Django app registry WebSocket importlaridan OLDIN yuklanishi kerak
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.board.routing import websocket_urlpatterns as board_ws  # noqa: E402
from apps.chat.routing import websocket_urlpatterns as chat_ws  # noqa: E402
from apps.chat.ws_auth import JWTAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(URLRouter([*chat_ws, *board_ws])),
})
