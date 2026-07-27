"""Lessons selector layer — "kim nimani ko'radi" qoidalari bitta joyda.

Ota-ona faqat TASDIQLANGAN bog'lanishdagi bolasining ma'lumotini ko'radi —
bu rozilik modelining texnik kafolati.
"""
from django.db.models import QuerySet

from apps.accounts.models import ParentChildLink, User

from .models import Attendance, Course, Lesson

_APPROVED = ParentChildLink.Status.APPROVED


def courses_for(user: User) -> QuerySet[Course]:
    if user.role == User.Role.TEACHER:
        return Course.objects.filter(teacher=user)
    if user.role == User.Role.STUDENT:
        return Course.objects.filter(enrollments__student=user)
    if user.role == User.Role.PARENT:
        return Course.objects.filter(
            enrollments__student__parent_links__parent=user,
            enrollments__student__parent_links__status=_APPROVED,
        ).distinct()
    return Course.objects.all()


def lessons_for(user: User) -> QuerySet[Lesson]:
    qs = Lesson.objects.select_related('course')
    if user.role == User.Role.TEACHER:
        return qs.filter(course__teacher=user)
    if user.role == User.Role.STUDENT:
        return qs.filter(course__enrollments__student=user)
    if user.role == User.Role.PARENT:
        return qs.filter(
            course__enrollments__student__parent_links__parent=user,
            course__enrollments__student__parent_links__status=_APPROVED,
        ).distinct()
    return qs


def attendance_for(user: User) -> QuerySet[Attendance]:
    qs = Attendance.objects.select_related('lesson', 'student')
    if user.role == User.Role.TEACHER:
        return qs.filter(lesson__course__teacher=user)
    if user.role == User.Role.STUDENT:
        return qs.filter(student=user)
    if user.role == User.Role.PARENT:
        return qs.filter(
            student__parent_links__parent=user,
            student__parent_links__status=_APPROVED,
        )
    return qs
