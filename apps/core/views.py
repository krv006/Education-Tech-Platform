from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """GET /api/health/ — LB/monitoring uchun: DB va cache holati."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        db_ok = cache_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            db_ok = False
        try:
            cache.set('health', '1', 5)
            cache_ok = cache.get('health') == '1'
        except Exception:
            cache_ok = False
        status_code = 200 if (db_ok and cache_ok) else 503
        return Response(
            {'status': 'ok' if status_code == 200 else 'degraded', 'db': db_ok, 'cache': cache_ok},
            status=status_code,
        )
