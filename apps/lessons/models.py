import uuid

from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedUUIDModel


class Course(TimeStampedUUIDModel, SoftDeleteModel):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.teacher.username}'


class Enrollment(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        DECLINED = 'declined', 'Rad etilgan'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    # O'quvchi/ota-ona so'rovi PENDING bo'lib turadi — kurs o'qituvchisi tasdiqlaganda APPROVED.
    # O'qituvchi o'zi biriktirsa darhol APPROVED (default mavjud yozuvlar uchun ham).
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course', 'student'], name='unique_course_student'),
        ]

    def __str__(self):
        return f'{self.student.username} @ {self.course.title} [{self.status}]'


class Lesson(TimeStampedUUIDModel, SoftDeleteModel):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Rejalashtirilgan'
        LIVE = 'live', 'Jonli'
        FINISHED = 'finished', 'Tugagan'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField(db_index=True)
    duration_min = models.PositiveIntegerField(default=45)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    # LiveKit room name — unique per lesson, generated once.
    room_name = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        ordering = ['starts_at']

    def save(self, *args, **kwargs):
        if not self.room_name:
            self.room_name = f'lesson-{uuid.uuid4().hex[:12]}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.starts_at:%Y-%m-%d %H:%M})'


class Attendance(TimeStampedUUIDModel):
    """Auto attendance: stamped when a participant requests a room token / leaves."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendances')
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            models.UniqueConstraint(fields=['lesson', 'student'], name='unique_lesson_student'),
        ]

    @property
    def minutes(self):
        if self.joined_at and self.left_at:
            return int((self.left_at - self.joined_at).total_seconds() // 60)
        return None

    def __str__(self):
        return f'{self.student.username} @ {self.lesson.title}'
