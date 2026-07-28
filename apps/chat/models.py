"""Chat modellari — Telegram uslubi (FRD: EduTech.docx).

Qoidalar:
  - Har kurs = bitta guruh chat. Guruhni faqat o'qituvchi (kurs yaratish orqali) ochadi.
  - Direct chat FAQAT o'qituvchi ↔ o'quvchi. O'quvchilar orasida direct yo'q.
  - O'quvchi o'qituvchiga 1 martalik so'rov yuboradi; qabul qilingach chat ochiladi.
    O'qituvchi block qilsa, o'quvchi qayta so'rov yuborishi kerak.
"""
from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    OneToOneField,
    Q,
    TextChoices,
    TextField,
    UniqueConstraint,
)

from apps.core.models import TimeStampedUUIDModel


class ChatRoom(TimeStampedUUIDModel):
    class Kind(TextChoices):
        COURSE = 'course', 'Kurs guruhi'
        DIRECT = 'direct', 'Shaxsiy'

    class DirectStatus(TextChoices):
        PENDING = 'pending', "So'rov kutilmoqda"
        ACTIVE = 'active', 'Ochiq'
        BLOCKED = 'blocked', 'Bloklangan'

    kind = CharField(max_length=8, choices=Kind.choices, db_index=True)
    # kind=COURSE bo'lsa:
    course = OneToOneField(
        'lessons.Course', CASCADE, null=True, blank=True, related_name='chat_room',
    )
    # kind=DIRECT bo'lsa:
    teacher = ForeignKey(
        'accounts.User', CASCADE, null=True, blank=True, related_name='direct_chats_teacher',
    )
    student = ForeignKey(
        'accounts.User', CASCADE, null=True, blank=True, related_name='direct_chats_student',
    )
    direct_status = CharField(
        max_length=8, choices=DirectStatus.choices, default=DirectStatus.ACTIVE, db_index=True,
    )

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            UniqueConstraint(
                fields=['teacher', 'student'],
                condition=Q(kind='direct'),
                name='unique_direct_teacher_student',
            ),
        ]

    def title_for(self, user) -> str:
        if self.kind == self.Kind.COURSE:
            return self.course.title
        other = self.teacher if user.id == self.student_id else self.student
        return (other.get_full_name() or other.username) if other else 'Chat'

    def __str__(self):
        if self.kind == self.Kind.COURSE:
            return f'guruh: {self.course.title}'
        return f'direct: {self.teacher} ↔ {self.student} [{self.direct_status}]'


class Message(TimeStampedUUIDModel):
    room = ForeignKey('chat.ChatRoom', CASCADE, related_name='messages')
    sender = ForeignKey('accounts.User', CASCADE, related_name='chat_messages')
    text = TextField()

    class Meta:
        ordering = ['created_at']
        indexes = [Index(fields=['room', 'created_at'])]

    def __str__(self):
        return f'{self.sender.username}: {self.text[:40]}'


class RoomRead(TimeStampedUUIDModel):
    """Har foydalanuvchining xonada oxirgi o'qigan vaqti — unread hisoblash uchun."""

    room = ForeignKey('chat.ChatRoom', CASCADE, related_name='reads')
    user = ForeignKey('accounts.User', CASCADE, related_name='chat_reads')
    last_read_at = DateTimeField()

    class Meta:
        constraints = [
            UniqueConstraint(fields=['room', 'user'], name='unique_room_user_read'),
        ]
