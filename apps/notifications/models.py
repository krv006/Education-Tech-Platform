"""Bildirishnoma modellari — admin bitta userga yoki hammaga xabar yuboradi.

Har yuborishda Notification (matn + nishon turi) yaratiladi, va har qabul
qiluvchi uchun alohida NotificationRecipient qatori (o'qildi/o'qilmadi holati
shu yerda, chat.RoomRead'dan farqli — bu yerda "kim aniq o'qidi" ro'yxati
kerak, shuning uchun umumiy last_read_at emas, har kishiga alohida yozuv).
"""
from django.conf import settings
from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    TextChoices,
    TextField,
    UniqueConstraint,
)

from apps.core.models import TimeStampedUUIDModel


class Notification(TimeStampedUUIDModel):
    class Target(TextChoices):
        USER = 'user', 'Bitta foydalanuvchi'
        ALL = 'all', 'Hammaga'

    sender = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='sent_notifications')
    # Admin CKEditor'da yozgan matn — server tomonda tozalangan (sanitize) HTML
    description = TextField()
    target_type = CharField(max_length=8, choices=Target.choices)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender.username} · {self.get_target_type_display()} · {self.created_at:%Y-%m-%d %H:%M}'


class NotificationRecipient(TimeStampedUUIDModel):
    """Yuborish paytida har qabul qiluvchi uchun bitta qator — o'qildi holati shu yerda."""

    notification = ForeignKey('notifications.Notification', CASCADE, related_name='recipients')
    user = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='received_notifications')
    read_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(fields=['notification', 'user'], name='unique_notification_recipient'),
        ]

    def __str__(self):
        state = "o'qildi" if self.read_at else "o'qilmadi"
        return f'{self.user.username} · {state}'
