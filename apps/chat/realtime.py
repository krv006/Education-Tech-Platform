"""Chat real-time broadcast — service qatlamidan channel layer'ga.

send_message (REST yoki WS orqali) har safar shu yerdan o'tadi: xabar
saqlangach xonaning WebSocket guruhiga tarqatiladi. Channel layer
sozlanmagan bo'lsa (masalan, ba'zi testlar) jimgina o'tkazib yuboriladi.
"""
import json

from asgiref.sync import async_to_sync
from rest_framework.renderers import JSONRenderer


def broadcast_message(message) -> None:
    from channels.layers import get_channel_layer

    from .consumers import group_name
    from .serializers import MessageSerializer

    layer = get_channel_layer()
    if layer is None:
        return
    # UUID/datetime kabi qiymatlarni toza JSON'ga aylantiramiz —
    # channel layer payload'i serializable bo'lishi shart.
    # Chaqiruvchi doim sync kontekstda (view yoki database_sync_to_async
    # worker thread'i) — async_to_sync xavfsiz.
    payload = json.loads(JSONRenderer().render(MessageSerializer(message).data))
    async_to_sync(layer.group_send)(group_name(message.room_id), {
        'type': 'chat.message',
        'message': payload,
    })
