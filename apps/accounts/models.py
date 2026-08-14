import secrets
import string
import uuid

from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    ImageField,
    TextChoices,
    UniqueConstraint,
    UUIDField,
)

from apps.core.models import TimeStampedUUIDModel


def generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return 'FK-' + ''.join(secrets.choice(alphabet) for _ in range(4))


class User(AbstractUser):
    class Role(TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', "O'qituvchi"
        STUDENT = 'student', "O'quvchi"
        PARENT = 'parent', 'Ota-ona'

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = CharField(max_length=16, choices=Role.choices, default=Role.STUDENT, db_index=True)
    phone = CharField(max_length=20, unique=True, null=True, blank=True)
    # Student's invite code — parent enters it to request a link (consent flow).
    invite_code = CharField(max_length=12, unique=True, null=True, blank=True)
    avatar = ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.role == self.Role.STUDENT and not self.invite_code:
            code = generate_invite_code()
            while User.objects.filter(invite_code=code).exists():
                code = generate_invite_code()
            self.invite_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'


class ParentChildLink(TimeStampedUUIDModel):
    """Parent ↔ student connection. Analytics open to the parent only while APPROVED.

    Two ways a link is created:
      - parent creates the child account themselves -> APPROVED immediately
      - parent enters the student's invite code -> PENDING until the student approves
    The student can revoke (decline) an approved link at any time.
    """

    class Status(TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        DECLINED = 'declined', 'Rad etilgan'

    parent = ForeignKey('accounts.User', CASCADE, related_name='child_links')
    student = ForeignKey('accounts.User', CASCADE, related_name='parent_links')
    status = CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    responded_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(fields=['parent', 'student'], name='unique_parent_student'),
        ]

    def __str__(self):
        return f'{self.parent.username} -> {self.student.username} [{self.status}]'


class Consent(TimeStampedUUIDModel):
    """Per-child consent flags managed by the linked parent (FRD: privacy.consent_collect)."""

    class Kind(TextChoices):
        RECORDING = 'recording', 'Dars yozib olish'
        CAMERA = 'camera', 'Kamera'
        ANALYTICS = 'analytics', 'Tahlil (davomat/faollik)'

    student = ForeignKey('accounts.User', CASCADE, related_name='consents')
    granted_by = ForeignKey('accounts.User', CASCADE, related_name='granted_consents')
    kind = CharField(max_length=16, choices=Kind.choices)
    granted = BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['student', 'kind'], name='unique_student_consent_kind'),
        ]

    def __str__(self):
        return f'{self.student.username} · {self.kind} = {self.granted}'
