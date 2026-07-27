"""Audit service — muhim harakatlarni yozib borish (FRD: security.audit)."""
from __future__ import annotations

import logging

logger = logging.getLogger('apps.audit')


def record(*, action: str, actor=None, target=None, meta: dict | None = None, request=None) -> None:
    """Audit yozuvi qo'shadi. Xato bo'lsa asosiy oqimni buzmaydi (log qiladi xolos)."""
    from .models import AuditLog

    try:
        ip = None
        if request is not None:
            xff = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
        AuditLog.objects.create(
            actor=actor if (actor is not None and actor.is_authenticated) else None,
            action=action,
            target_type=target.__class__.__name__ if target is not None else '',
            target_id=str(getattr(target, 'pk', '')) if target is not None else '',
            meta=meta or {},
            ip_address=ip,
        )
    except Exception:  # pragma: no cover — audit hech qachon requestni yiqitmasin
        logger.exception('Audit yozuvida xato: %s', action)
