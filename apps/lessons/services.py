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
    # Har kurs = bitta guruh chat (EduTech.docx) — kurs bilan birga ochiladi
    from apps.chat import services as chat_services
    chat_services.ensure_course_room(course)
    audit.record(action='course.create', actor=teacher, target=course, request=request)
    return course


@transaction.atomic
def schedule_lesson(*, teacher: User, course: Course, request=None, **data) -> Lesson:
    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs egasi dars qo'sha oladi.")
    lesson = Lesson.objects.create(course=course, **data)
    audit.record(action='lesson.schedule', actor=teacher, target=lesson, request=request)
    return lesson


def _get_course(course_id) -> Course:
    try:
        return Course.objects.get(pk=course_id, is_active=True)
    except (Course.DoesNotExist, ValueError):
        raise NotFound('Kurs topilmadi.')


def _resolve_student_ref(student_ref: str) -> User:
    """O'quvchini login yoki taklif kodi bo'yicha topadi (o'qituvchi biriktirishi uchun)."""
    student = User.objects.filter(role=User.Role.STUDENT, username=student_ref).first()
    if student is None:
        student = User.objects.filter(role=User.Role.STUDENT, invite_code=student_ref.upper()).first()
    if student is None:
        raise NotFound("Bunday login yoki taklif kodli o'quvchi topilmadi.")
    return student


def _resolve_enroll_target(*, course: Course, by_user: User, student_id=None, student_ref=None) -> User:
    """Kimni yozish/chiqarish mumkinligini aniqlaydi — enroll va unenroll uchun bitta qoida."""
    if by_user.role == User.Role.STUDENT:
        return by_user
    if by_user.role == User.Role.PARENT:
        if not student_id or not account_selectors.is_linked(by_user, student_id):
            raise PermissionDenied("Bu o'quvchi sizga bog'lanmagan.")
        return User.objects.get(pk=student_id)
    if by_user.role == User.Role.TEACHER:
        if course.teacher_id != by_user.id:
            raise PermissionDenied("Faqat o'z kursingizga o'quvchi biriktira olasiz.")
        if student_id:
            try:
                return User.objects.get(pk=student_id, role=User.Role.STUDENT)
            except (User.DoesNotExist, ValueError):
                raise NotFound("O'quvchi topilmadi.")
        if not student_ref:
            raise NotFound("O'quvchi login yoki taklif kodini kiriting.")
        return _resolve_student_ref(student_ref)
    raise PermissionDenied("Faqat o'quvchi, ota-ona yoki kurs o'qituvchisi yoza oladi.")


@transaction.atomic
def enroll(*, course_id, by_user: User, student_id=None, student_ref=None, request=None) -> tuple[Enrollment, bool]:
    """O'quvchi/ota-ona yozilish SO'ROVI yuboradi (pending), o'qituvchi o'z kursiga
    biriktirsa darhol tasdiqlanadi. O'quvchi darsga faqat APPROVED bo'lgach kiradi."""
    course = _get_course(course_id)
    student = _resolve_enroll_target(
        course=course, by_user=by_user, student_id=student_id, student_ref=student_ref,
    )
    target_status = (
        Enrollment.Status.APPROVED if by_user.role == User.Role.TEACHER
        else Enrollment.Status.PENDING
    )
    enrollment, created = Enrollment.objects.get_or_create(
        course=course, student=student, defaults={'status': target_status},
    )
    if not created and enrollment.status != Enrollment.Status.APPROVED and enrollment.status != target_status:
        # rad etilgan so'rov qayta yuborilsa yana pending; o'qituvchi biriktirsa approved
        enrollment.status = target_status
        enrollment.save(update_fields=['status'])
    if created:
        audit.record(
            action='course.enroll', actor=by_user, target=course,
            meta={'student_id': str(student.id), 'status': enrollment.status}, request=request,
        )
    return enrollment, created


@transaction.atomic
def respond_enrollment(*, teacher: User, enrollment_id, action: str, request=None) -> Enrollment:
    """O'qituvchi yozilish so'rovini tasdiqlaydi yoki rad etadi."""
    try:
        enrollment = Enrollment.objects.select_related('course').get(pk=enrollment_id)
    except (Enrollment.DoesNotExist, ValueError):
        raise NotFound("So'rov topilmadi.")
    if enrollment.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi so'rovga javob beradi.")
    if action not in ('approve', 'decline'):
        raise NotFound("Amal noto'g'ri: approve yoki decline.")
    enrollment.status = (
        Enrollment.Status.APPROVED if action == 'approve' else Enrollment.Status.DECLINED
    )
    enrollment.save(update_fields=['status'])
    audit.record(
        action=f'course.enroll_{action}', actor=teacher, target=enrollment.course,
        meta={'student_id': str(enrollment.student_id)}, request=request,
    )
    return enrollment


@transaction.atomic
def unenroll(*, course_id, by_user: User, student_id=None, request=None) -> bool:
    """Yozuvni bekor qilish — o'quvchi o'zini, ota-ona bolasini, o'qituvchi o'z kursidan chiqaradi."""
    course = _get_course(course_id)
    student = _resolve_enroll_target(course=course, by_user=by_user, student_id=student_id)
    deleted, _ = Enrollment.objects.filter(course=course, student=student).delete()
    if deleted:
        audit.record(
            action='course.unenroll', actor=by_user, target=course,
            meta={'student_id': str(student.id)}, request=request,
        )
    return bool(deleted)


@transaction.atomic
def finish_lesson(*, teacher: User, lesson: Lesson, request=None) -> Lesson:
    """Darsni yakunlash — ochiq davomatlarga left_at bosiladi, doska PDF chatga tushadi."""
    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat o'qituvchi darsni tugata oladi.")
    lesson.status = Lesson.Status.FINISHED
    lesson.save(update_fields=['status'])
    lesson.attendances.filter(left_at__isnull=True).update(left_at=timezone.now())
    # Doska lentasi -> PDF -> guruh chat (EduTech.docx). Xato yakunlashni to'xtatmaydi.
    try:
        from apps.board import services as board_services
        board_services.publish_board_pdf(lesson)
    except Exception:  # noqa: BLE001 — PDF muammosi dars yakunidan muhimroq emas
        import logging
        logging.getLogger('apps').exception('board pdf publish failed')
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
