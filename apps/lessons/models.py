import uuid

from django.conf import settings
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    OneToOneField,
    PositiveIntegerField,
    TextChoices,
    TextField,
    UniqueConstraint,
)

from apps.core.models import SoftDeleteModel, TimeStampedUUIDModel


class Course(TimeStampedUUIDModel, SoftDeleteModel):
    teacher = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='courses')
    title = CharField(max_length=200)
    subject = CharField(max_length=100, blank=True)
    description = TextField(blank=True)
    is_active = BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.teacher.username}'


class Enrollment(TimeStampedUUIDModel):
    class Status(TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        DECLINED = 'declined', 'Rad etilgan'

    course = ForeignKey('lessons.Course', CASCADE, related_name='enrollments')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='enrollments')
    # O'quvchi/ota-ona so'rovi PENDING bo'lib turadi — kurs o'qituvchisi tasdiqlaganda APPROVED.
    # O'qituvchi o'zi biriktirsa darhol APPROVED (default mavjud yozuvlar uchun ham).
    status = CharField(max_length=10, choices=Status.choices, default=Status.APPROVED, db_index=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['course', 'student'], name='unique_course_student'),
        ]

    def __str__(self):
        return f'{self.student.username} @ {self.course.title} [{self.status}]'


class Lesson(TimeStampedUUIDModel, SoftDeleteModel):
    class Status(TextChoices):
        SCHEDULED = 'scheduled', 'Rejalashtirilgan'
        LIVE = 'live', 'Jonli'
        FINISHED = 'finished', 'Tugagan'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    course = ForeignKey('lessons.Course', CASCADE, related_name='lessons')
    title = CharField(max_length=200)
    starts_at = DateTimeField(db_index=True)
    duration_min = PositiveIntegerField(default=45)
    status = CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    # LiveKit room name — unique per lesson, generated once.
    room_name = CharField(max_length=64, unique=True, editable=False)

    class Meta:
        ordering = ['starts_at']

    def save(self, *args, **kwargs):
        if not self.room_name:
            self.room_name = f'lesson-{uuid.uuid4().hex[:12]}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.starts_at:%Y-%m-%d %H:%M})'


class AttentionCheck(TimeStampedUUIDModel):
    """"Siz shu yerdamisiz?" — dars davomida server belgilagan tasodifiy vaqtlarda.

    Jadval server tomonda yaratiladi (EduTech.docx: o'quvchi vaqtini oldindan
    bila olmasligi kerak). 15 soniya ichida javob bo'lmasa o'tkazib yuborilgan
    hisoblanadi.
    """

    lesson = ForeignKey('lessons.Lesson', CASCADE, related_name='attention_checks')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='attention_checks')
    due_at = DateTimeField(db_index=True)
    answered_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['due_at']

    def __str__(self):
        state = 'javob berildi' if self.answered_at else 'kutilmoqda'
        return f'{self.student.username} @ {self.due_at:%H:%M:%S} [{state}]'


class FocusEvent(TimeStampedUUIDModel):
    """Anti-cheat jurnali: o'quvchi dars oynasidan chiqib-kirishlari.

    Brauzer screenshot/screenrecord'ni taqiqlay olmaydi — lekin har bir
    chiqib-kirish shu yerga yoziladi va hisobotda ko'rinadi.
    """

    class Kind(TextChoices):
        EXIT = 'exit', 'Oynadan chiqdi'
        RETURN = 'return', 'Qaytib keldi'

    lesson = ForeignKey('lessons.Lesson', CASCADE, related_name='focus_events')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='focus_events')
    kind = CharField(max_length=8, choices=Kind.choices)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.student.username} · {self.kind} · {self.created_at:%H:%M:%S}'


class FocusAlert(TimeStampedUUIDModel):
    """O'quvchi darsdan FOCUS_PARENT_ALERT_THRESHOLD martadan ko'p chiqqanda bir
    marta yaratiladi — ota-ona paneliga ko'rinadigan signal (EPAM imtihon uslubi:
    1-2 marta ogohlantirish, uchinchisida ota-onaga xabar boradi).
    """

    lesson = ForeignKey('lessons.Lesson', CASCADE, related_name='focus_alerts')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='focus_alerts')
    exit_count = PositiveIntegerField()

    class Meta:
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(fields=['lesson', 'student'], name='unique_lesson_student_focus_alert'),
        ]

    def __str__(self):
        return f'{self.student.username} @ {self.lesson.title} · {self.exit_count} marta chiqdi'


class LessonRecording(TimeStampedUUIDModel):
    """Dars video yozuvi (EduTech.docx: "video zapis avtomatik saqlansin").

    LiveKit Egress dars LIVE bo'lganda yozishni boshlaydi, dars/xona
    tugaganda faylga yakunlaydi. Fayl `recordings` volume'ida turadi va
    FAQAT auth endpoint orqali beriladi. O'qituvchi guruhni (kursni)
    o'chirmaguncha saqlanadi.
    """

    class Status(TextChoices):
        PENDING = 'pending', 'Boshlanmoqda'       # so'rov yuborildi, egress hali tasdiqlamadi
        RECORDING = 'recording', 'Yozilmoqda'     # egress tasdiqladi (egress_id bor)
        COMPLETED = 'completed', 'Tayyor'
        FAILED = 'failed', 'Xatolik'

    lesson = OneToOneField('lessons.Lesson', CASCADE, related_name='recording')
    # O'qituvchi dars tugatishda beradigan nom — chatga shu nom bilan tushadi
    title = CharField(max_length=200, blank=True)
    egress_id = CharField(max_length=64, blank=True)
    file_name = CharField(max_length=255, blank=True)
    status = CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = TextField(blank=True)
    ended_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.lesson.title} [{self.status}]'


class Attendance(TimeStampedUUIDModel):
    """Auto attendance: stamped when a participant requests a room token / leaves."""

    lesson = ForeignKey('lessons.Lesson', CASCADE, related_name='attendances')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='attendances')
    joined_at = DateTimeField(null=True, blank=True)
    left_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            UniqueConstraint(fields=['lesson', 'student'], name='unique_lesson_student'),
        ]

    @property
    def minutes(self):
        if self.joined_at and self.left_at:
            return int((self.left_at - self.joined_at).total_seconds() // 60)
        return None

    def __str__(self):
        return f'{self.student.username} @ {self.lesson.title}'


class LessonRating(TimeStampedUUIDModel):
    """O'quvchi tugagan darsga baho beradi — o'qituvchi/kurs sifatini kuzatish uchun."""

    lesson = ForeignKey('lessons.Lesson', CASCADE, related_name='ratings')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='lesson_ratings')
    stars = PositiveIntegerField()
    description = TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(fields=['lesson', 'student'], name='unique_lesson_student_rating'),
        ]

    def __str__(self):
        return f'{self.student.username} @ {self.lesson.title} · {self.stars}★'
