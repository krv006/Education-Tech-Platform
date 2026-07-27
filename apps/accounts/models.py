import secrets
import string

from django.contrib.auth.models import AbstractUser
from django.db import models


def generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return 'FK-' + ''.join(secrets.choice(alphabet) for _ in range(4))


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', "O'qituvchi"
        STUDENT = 'student', "O'quvchi"
        PARENT = 'parent', 'Ota-ona'

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # Student's invite code — parent enters it to request a link (consent flow).
    invite_code = models.CharField(max_length=12, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.role == self.Role.STUDENT and not self.invite_code:
            code = generate_invite_code()
            while User.objects.filter(invite_code=code).exists():
                code = generate_invite_code()
            self.invite_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'


class ParentChildLink(models.Model):
    """Parent ↔ student connection. Analytics open to the parent only while APPROVED.

    Two ways a link is created:
      - parent creates the child account themselves -> APPROVED immediately
      - parent enters the student's invite code -> PENDING until the student approves
    The student can revoke (decline) an approved link at any time.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        DECLINED = 'declined', 'Rad etilgan'

    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='child_links')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parent_links')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['parent', 'student'], name='unique_parent_student'),
        ]

    def __str__(self):
        return f'{self.parent.username} -> {self.student.username} [{self.status}]'


class Consent(models.Model):
    """Per-child consent flags managed by the linked parent (FRD: privacy.consent_collect)."""

    class Kind(models.TextChoices):
        RECORDING = 'recording', 'Dars yozib olish'
        CAMERA = 'camera', 'Kamera'
        ANALYTICS = 'analytics', 'Tahlil (davomat/faollik)'

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents')
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_consents')
    kind = models.CharField(max_length=16, choices=Kind.choices)
    granted = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'kind'], name='unique_student_consent_kind'),
        ]

    def __str__(self):
        return f'{self.student.username} · {self.kind} = {self.granted}'
