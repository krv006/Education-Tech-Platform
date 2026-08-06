"""Bildirishnoma real-time push — chat/realtime.py bilan bir xil naqsh.

Yuborilgan zahoti har qabul qiluvchining shaxsiy WS guruhiga tarqatiladi
(badge/toast uchun). Channel layer sozlanmagan bo'lsa (testlarda) jimgina
o'tkazib yuboriladi.
"""
import json

from asgiref.sync import async_to_sync
from rest_framework.renderers import JSONRenderer


def group_name(user_id) -> str:
    return f'notifications_{user_id}'


def broadcast_notification(notification, recipients) -> None:
    from channels.layers import get_channel_layer

    from .serializers import NotificationSerializer

    layer = get_channel_layer()
    if layer is None:
        return
    payload = json.loads(JSONRenderer().render(NotificationSerializer(notification).data))
    for user in recipients:
        async_to_sync(layer.group_send)(group_name(user.id), {
            'type': 'notification.new',
            'notification': payload,
        })
