"""Doska real-time broadcast — polling o'rniga WebSocket.

Service qatlami (add_stroke / erase_strokes / add_sheet) har o'zgarishni
`board_<lesson_id>` guruhiga tarqatadi — REST orqali kelganmi, WS orqalimi,
farqi yo'q: hamma ulangan ishtirokchi bir zumda ko'radi.
"""
from asgiref.sync import async_to_sync


def group_name(lesson_id) -> str:
    return f'board_{lesson_id}'


def _send(lesson_id, event: dict) -> None:
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group_name(lesson_id), {
        'type': 'board.event',
        'event': event,
    })


def broadcast_stroke(lesson_id, sheet_index: int, stroke: dict) -> None:
    _send(lesson_id, {'type': 'stroke', 'sheet': sheet_index, 'stroke': stroke})


def broadcast_erase(lesson_id, sheet_index: int, stroke_ids: list, by: str, reason: str) -> None:
    _send(lesson_id, {
        'type': 'erase', 'sheet': sheet_index,
        'stroke_ids': stroke_ids, 'by': by, 'reason': reason,
    })


def broadcast_sheet(lesson_id, index: int) -> None:
    _send(lesson_id, {'type': 'sheet', 'index': index})
