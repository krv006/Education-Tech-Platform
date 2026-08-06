"""Bildirishnoma selector layer — kim nimani ko'radi."""
from django.db.models import QuerySet

from apps.accounts.models import User

from .models import Notification, NotificationRecipient


def inbox_for(user: User) -> QuerySet[NotificationRecipient]:
    """Foydalanuvchi qabul qilgan xabarlar — eng yangisi tepada."""
    return (
        NotificationRecipient.objects
        .filter(user=user)
        .select_related('notification', 'notification__sender')
    )


def sent_by(admin: User) -> QuerySet[Notification]:
    """Admin o'zi yuborgan xabarlar — o'qildi/jami hisoblash uchun recipients prefetch qilingan."""
    return (
        Notification.objects
        .filter(sender=admin)
        .prefetch_related('recipients')
    )


def unread_count(user: User) -> int:
    return NotificationRecipient.objects.filter(user=user, read_at__isnull=True).count()
