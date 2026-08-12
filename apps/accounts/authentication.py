"""Bitta akkaunt = bitta faol qurilma — har bir so'rovda tekshiriladi.

Access token'dagi `session_jti` claim joriy faol DeviceSession bilan solishtiriladi
(Redis keshi orqali, DB'ga har safar bormaslik uchun). Mos kelmasa — demak shu
qurilma boshqa login orqali chiqarib yuborilgan, 401 qaytadi.
"""
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .services import session_cache_key


class SingleSessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        session_jti = validated_token.get('session_jti')
        if session_jti is None:
            # Eski (claim'siz) token yoki tizim darajasidagi chaqiruv — o'tkazamiz
            return user

        current = cache.get(session_cache_key(user.id))
        if current is None:
            from .models import DeviceSession

            current = (
                DeviceSession.objects.filter(user=user)
                .values_list('session_jti', flat=True)
                .first()
            ) or ''
            cache.set(session_cache_key(user.id), current, 60 * 60 * 24 * 7)

        if current != session_jti:
            raise AuthenticationFailed(
                'Sessiya boshqa qurilmadan kirilgani uchun tugatildi.',
                code='session_revoked',
            )
        return user
