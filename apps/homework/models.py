"""Uy vazifasi modellari (AI-home-checker integratsiyasi).

Oqim:
  - O'qituvchi kursga vazifa (Assignment) beradi.
  - O'quvchi faylini yuklaydi (PDF/rasm/DOCX yoki Speaking uchun audio).
  - Gemini savolma-savol tekshiradi (apps/homework/ai.py) va JSON natija
    Submission.result ga yoziladi — bola, o'qituvchi va ota-ona ko'radi.
"""
from django.conf import settings
from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    FileField,
    FloatField,
    ForeignKey,
    JSONField,
    TextChoices,
    TextField,
)

from apps.core.models import TimeStampedUUIDModel


class Assignment(TimeStampedUUIDModel):
    """O'qituvchi bergan uy vazifasi. Fan kursdan olinadi (course.subject)."""

    course = ForeignKey('lessons.Course', CASCADE, related_name='assignments')
    title = CharField(max_length=200)
    description = TextField(blank=True)
    # O'qituvchi rich editor'da yozgan vazifa matni — server tomonda
    # tozalangan (sanitize) HTML saqlanadi
    body = TextField(blank=True)
    # Vazifa fayli (Word/PDF/rasm) — o'qituvchi tayyorini yuklaydi,
    # o'quvchilar yuklab oladi
    attachment = FileField(upload_to='homework/tasks/%Y/%m/', null=True, blank=True)
    attachment_name = CharField(max_length=255, blank=True)
    due_at = DateTimeField(null=True, blank=True, db_index=True)
    # Til fanlari uchun ko'nikma: writing / reading / listening / speaking.
    # Bo'sh bo'lsa — oddiy fan sifatida tekshiriladi.
    skill_key = CharField(max_length=20, blank=True)
    # O'qituvchining AI'ga qo'shimcha ko'rsatmasi ("7-sinf darajasida", "qat'iy bo'l")
    extra_instructions = TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} @ {self.course.title}'


class Submission(TimeStampedUUIDModel):
    """O'quvchining topshirig'i + AI tekshiruv natijasi."""

    class Status(TextChoices):
        CHECKING = 'checking', 'Tekshirilmoqda'
        DONE = 'done', 'Tekshirildi'
        ERROR = 'error', 'Xatolik'

    assignment = ForeignKey('homework.Assignment', CASCADE, related_name='submissions')
    student = ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name='homework_submissions')
    file = FileField(upload_to='homework/%Y/%m/')
    original_name = CharField(max_length=255)
    status = CharField(max_length=10, choices=Status.choices, default=Status.CHECKING, db_index=True)
    # AI javobi — AI-home-checker JSON sxemasi:
    # {overall_score, grade, questions: [...], summary: {...}}
    result = JSONField(null=True, blank=True)
    overall_score = FloatField(null=True, blank=True)
    grade = CharField(max_length=40, blank=True)
    error = TextField(blank=True)
    checked_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.username} → {self.assignment.title} [{self.status}]'
