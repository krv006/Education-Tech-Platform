"""Lessons service layer — kurs/dars/yozilish bo'yicha yozuvchi biznes-logika."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import selectors as account_selectors
from apps.accounts.models import User
from apps.core import audit

from .models import Attendance, Course, Enrollment, Lesson


@transaction.atomic
def create_course(*, teacher: User, request=None, **data) -> Course:
    course = Course.objects.create(teacher=teacher, **data)
    audit.record(action='course.create', actor=teacher, target=course, request=request)
    return course


@transaction.atomic
def schedule_lesson(*, teacher: User, course: Course, request=None, **data) -> Lesson:
    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs egasi dars qo'sha oladi.")
    lesson = Lesson.objects.create(course=course, **data)
    audit.record(action='lesson.schedule', actor=teacher, target=lesson, request=request)
    return lesson


@transaction.atomic
def enroll(*, course_id, by_user: User, student_id=None, request=None) -> tuple[Enrollment, bool]:
    """O'quvchi o'zini, ota-ona esa tasdiqlangan bolasini yozadi."""
    try:
        course = Course.objects.get(pk=course_id, is_active=True)
    except Course.DoesNotExist:
        raise NotFound('Kurs topilmadi.')

    if by_user.role == User.Role.STUDENT:
        student = by_user
    elif by_user.role == User.Role.PARENT:
        if not student_id or not account_selectors.is_linked(by_user, student_id):
            raise PermissionDenied("Bu o'quvchi sizga bog'lanmagan.")
        student = User.objects.get(pk=student_id)
    else:
        raise PermissionDenied("Faqat o'quvchi yoki ota-ona yozila oladi.")

    enrollment, created = Enrollment.objects.get_or_create(course=course, student=student)
    if created:
        audit.record(
            action='course.enroll', actor=by_user, target=course,
            meta={'student_id': str(student.id)}, request=request,
        )
    return enrollment, created


@transaction.atomic
def finish_lesson(*, teacher: User, lesson: Lesson, request=None) -> Lesson:
    """Darsni yakunlash — ochiq davomatlarga left_at bosiladi."""
    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat o'qituvchi darsni tugata oladi.")
    lesson.status = Lesson.Status.FINISHED
    lesson.save(update_fields=['status'])
    lesson.attendances.filter(left_at__isnull=True).update(left_at=timezone.now())
    audit.record(action='lesson.finish', actor=teacher, target=lesson, request=request)
    return lesson


@transaction.atomic
def mark_joined(*, lesson: Lesson, student: User) -> Attendance:
    attendance, _ = Attendance.objects.get_or_create(lesson=lesson, student=student)
    if attendance.joined_at is None:
        attendance.joined_at = timezone.now()
        attendance.save(update_fields=['joined_at'])
    return attendance


@transaction.atomic
def mark_left(*, lesson_id, student: User) -> bool:
    updated = Attendance.objects.filter(
        lesson_id=lesson_id, student=student, left_at__isnull=True
    ).update(left_at=timezone.now())
    return bool(updated)
