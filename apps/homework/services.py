"""Uy vazifasi service layer — vazifa berish, topshirish, AI tekshiruv.

Tekshiruv fonda (thread) yuradi: o'quvchi faylni yuklagach darhol javob oladi
(status=checking), frontend polling bilan natijani kutadi. Testlarda
settings.HOMEWORK_CHECK_ASYNC=False qilib sinxron ishlatiladi.
"""
import re
import threading
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import ParentChildLink, User
from apps.lessons.models import Course, Enrollment, Lesson

from . import ai
from .models import Assignment, Submission

# Vazifa fayli (o'qituvchi biriktiradi) — AI'ga bormaydi, faqat yuklab olinadi
ATTACHMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.webp'}

# Rich editor HTML'iga ruxsat etilgan teglar — XSS'dan himoya
_ALLOWED_TAGS = {
    'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'strike',
    'h2', 'h3', 'ul', 'ol', 'li', 'blockquote', 'div', 'span', 'sub', 'sup',
}


def sanitize_html(html: str) -> str:
    """O'qituvchi yozgan HTML'ni tozalaydi. nh3 (Rust ammonia) bo'lsa u bilan,
    bo'lmasa konservativ regex fallback (skript/atributlar olib tashlanadi)."""
    html = (html or '').strip()
    if not html:
        return ''
    try:
        import nh3
        return nh3.clean(html, tags=_ALLOWED_TAGS, attributes={})
    except ImportError:
        # Fallback: teg atributlarini butunlay olib tashlaymiz va faqat
        # ruxsat etilgan teglarni qoldiramiz
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S | re.I)

        def _tag(m):
            closing, name = m.group(1), m.group(2).lower()
            if name in _ALLOWED_TAGS:
                return f'<{closing}{name}>'
            return ''
        return re.sub(r'<\s*(/?)\s*([a-zA-Z0-9]+)[^>]*>', _tag, html)


# ── yordamchilar ────────────────────────────────────────────────────────────
def _get_course(course_id) -> Course:
    try:
        return Course.objects.get(pk=course_id)
    except (Course.DoesNotExist, ValueError, TypeError):
        raise NotFound('Kurs topilmadi.')


def _get_assignment(assignment_id) -> Assignment:
    try:
        return Assignment.objects.select_related('course', 'lesson').get(pk=assignment_id)
    except (Assignment.DoesNotExist, ValueError, TypeError):
        raise NotFound('Vazifa topilmadi.')


def _get_submission(submission_id) -> Submission:
    try:
        return Submission.objects.select_related(
            'assignment__course', 'student',
        ).get(pk=submission_id)
    except (Submission.DoesNotExist, ValueError, TypeError):
        raise NotFound('Topshiriq topilmadi.')


def _is_enrolled(user: User, course: Course) -> bool:
    return Enrollment.objects.filter(
        course=course, student=user, status=Enrollment.Status.APPROVED,
    ).exists()


def _is_parent_of(parent: User, student: User) -> bool:
    return ParentChildLink.objects.filter(
        parent=parent, student=student, status=ParentChildLink.Status.APPROVED,
    ).exists()


def _can_view_course(user: User, course: Course) -> bool:
    if course.teacher_id == user.id or _is_enrolled(user, course):
        return True
    # Ota-ona: bolasi shu kursga yozilgan bo'lsa ko'radi
    child_ids = ParentChildLink.objects.filter(
        parent=user, status=ParentChildLink.Status.APPROVED,
    ).values_list('student_id', flat=True)
    return Enrollment.objects.filter(
        course=course, student_id__in=child_ids, status=Enrollment.Status.APPROVED,
    ).exists()


def _assignment_dict(a: Assignment) -> dict:
    return {
        'id': str(a.id),
        'course_id': str(a.course_id),
        'course_title': a.course.title,
        'subject': a.course.subject,
        'title': a.title,
        'description': a.description,
        'body': a.body,
        'attachment_name': a.attachment_name,
        'has_attachment': bool(a.attachment),
        'due_at': a.due_at,
        'skill_key': a.skill_key,
        'lesson_id': str(a.lesson_id) if a.lesson_id else None,
        'lesson_title': a.lesson.title if a.lesson_id else None,
        'created_at': a.created_at,
    }


def _submission_dict(s: Submission, include_result: bool = True) -> dict:
    due = s.assignment.due_at
    data = {
        'id': str(s.id),
        'assignment_id': str(s.assignment_id),
        'student_id': str(s.student_id),
        'student_name': f'{s.student.first_name} {s.student.last_name}'.strip() or s.student.username,
        'file_name': s.original_name,
        'status': s.status,
        'overall_score': s.overall_score,
        'grade': s.grade,
        'error': s.error,
        'is_late': bool(due and s.created_at and s.created_at > due),
        'created_at': s.created_at,
        'checked_at': s.checked_at,
    }
    if include_result:
        data['result'] = s.result
    return data


# ── vazifa (Assignment) ─────────────────────────────────────────────────────
def _parse_due(due_at):
    """datetime-local ('2026-08-05T14:30') yoki ISO satrni aware datetime'ga."""
    if not due_at:
        return None
    if isinstance(due_at, str):
        parsed = parse_datetime(due_at)
        if parsed is None:
            raise ValidationError({'due_at': "Muddat formati noto'g'ri."})
        due_at = parsed
    if timezone.is_naive(due_at):
        due_at = timezone.make_aware(due_at)
    return due_at


def _resolve_lesson(*, course: Course, lesson_id) -> Lesson | None:
    """Vazifa bog'lanadigan dars — faqat shu kursning TUGAGAN darsi bo'lishi kerak."""
    if not lesson_id:
        return None
    try:
        lesson = Lesson.objects.get(pk=lesson_id, course=course)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')
    if lesson.status != Lesson.Status.FINISHED:
        raise ValidationError({'lesson_id': "Faqat tugagan darsga vazifa bog'lash mumkin."})
    return lesson


def create_assignment(*, teacher: User, course_id, title: str, description: str = '',
                      body: str = '', due_at=None, skill_key: str = '', lesson_id=None,
                      extra_instructions: str = '', attachment=None) -> dict:
    course = _get_course(course_id)
    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi vazifa bera oladi.")
    if not (title or '').strip():
        raise ValidationError({'title': 'Vazifa nomi majburiy.'})
    skill_key = (skill_key or '').strip().lower()
    if skill_key and skill_key not in ai.SKILLS:
        raise ValidationError({'skill_key': f"Noto'g'ri ko'nikma: {sorted(ai.SKILLS)}"})
    lesson = _resolve_lesson(course=course, lesson_id=lesson_id)

    attachment_name = ''
    if attachment is not None:
        ext = Path(attachment.name or '').suffix.lower()
        if ext not in ATTACHMENT_EXTENSIONS:
            raise ValidationError({'attachment': (
                f"'{ext}' qo'llab-quvvatlanmaydi. Mumkin: {', '.join(sorted(ATTACHMENT_EXTENSIONS))}"
            )})
        if attachment.size > ai.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValidationError({'attachment': f'Fayl {ai.MAX_FILE_SIZE_MB} MB dan katta.'})
        attachment_name = (attachment.name or 'vazifa')[:255]

    assignment = Assignment.objects.create(
        course=course,
        lesson=lesson,
        title=title.strip(),
        description=(description or '').strip(),
        body=sanitize_html(body),
        attachment=attachment,
        attachment_name=attachment_name,
        due_at=_parse_due(due_at),
        skill_key=skill_key,
        extra_instructions=(extra_instructions or '').strip(),
    )
    return _assignment_dict(assignment)


def delete_assignment(*, teacher: User, assignment_id) -> None:
    a = _get_assignment(assignment_id)
    if a.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi vazifani o'chira oladi.")
    a.delete()


def assignment_file(*, user: User, assignment_id) -> tuple:
    a = _get_assignment(assignment_id)
    if not _can_view_course(user, a.course):
        raise PermissionDenied("Bu faylni ko'rish huquqingiz yo'q.")
    if not a.attachment:
        raise NotFound("Bu vazifada biriktirilgan fayl yo'q.")
    return a.attachment.path, a.attachment_name or 'vazifa'


def list_assignments(*, user: User, course_id) -> list:
    course = _get_course(course_id)
    if not _can_view_course(user, course):
        raise PermissionDenied("Bu kurs vazifalarini ko'rish huquqingiz yo'q.")
    result = []
    for a in course.assignments.select_related('lesson').all():
        item = _assignment_dict(a)
        if course.teacher_id == user.id:
            item['submissions_count'] = a.submissions.count()
        else:
            # O'quvchi (yoki ota-ona — bolasining) oxirgi topshirig'i holati
            student_ids = [user.id]
            if user.role == 'parent':
                student_ids = list(ParentChildLink.objects.filter(
                    parent=user, status=ParentChildLink.Status.APPROVED,
                ).values_list('student_id', flat=True))
            last = a.submissions.filter(student_id__in=student_ids).first()
            item['my_submission'] = _submission_dict(last, include_result=False) if last else None
        result.append(item)
    return result


def get_assignment(*, user: User, assignment_id) -> dict:
    a = _get_assignment(assignment_id)
    if not _can_view_course(user, a.course):
        raise PermissionDenied("Bu vazifani ko'rish huquqingiz yo'q.")
    data = _assignment_dict(a)
    if a.course.teacher_id == user.id:
        subs = list(a.submissions.select_related('student', 'assignment'))
        data['submissions'] = [_submission_dict(s, include_result=False) for s in subs]
        # Statistika: nechta o'quvchidan nechtasi topshirdi, o'rtacha ball
        scores = [s.overall_score for s in subs if s.overall_score is not None]
        data['stats'] = {
            'students_count': Enrollment.objects.filter(
                course=a.course, status=Enrollment.Status.APPROVED,
            ).count(),
            'submitted_count': len({s.student_id for s in subs}),
            'avg_score': round(sum(scores) / len(scores), 1) if scores else None,
        }
    else:
        student_ids = [user.id]
        if user.role == 'parent':
            student_ids = list(ParentChildLink.objects.filter(
                parent=user, status=ParentChildLink.Status.APPROVED,
            ).values_list('student_id', flat=True))
        data['submissions'] = [
            _submission_dict(s, include_result=False)
            for s in a.submissions.filter(student_id__in=student_ids).select_related('student')
        ]
    return data


# ── topshirish va AI tekshiruv ──────────────────────────────────────────────
def submit(*, student: User, assignment_id, upload) -> dict:
    a = _get_assignment(assignment_id)
    if not _is_enrolled(student, a.course):
        raise PermissionDenied("Bu kursga yozilmagansiz — vazifa topshira olmaysiz.")
    if upload is None:
        raise ValidationError({'file': 'Fayl majburiy.'})

    ext = Path(upload.name or '').suffix.lower()
    if ext not in ai.ALLOWED_EXTENSIONS:
        raise ValidationError({'file': (
            f"'{ext}' qo'llab-quvvatlanmaydi. Mumkin: {', '.join(sorted(ai.ALLOWED_EXTENSIONS))}"
        )})
    if ext in ai.AUDIO_EXTENSIONS and a.skill_key != 'speaking':
        raise ValidationError({'file': "Audio faqat Speaking vazifalari uchun."})
    if upload.size > ai.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError({'file': (
            f'Fayl {upload.size / 1024 / 1024:.1f} MB; chegara {ai.MAX_FILE_SIZE_MB} MB.'
        )})

    submission = Submission.objects.create(
        assignment=a,
        student=student,
        file=upload,
        original_name=(upload.name or 'homework')[:255],
        status=Submission.Status.CHECKING,
    )
    _dispatch_check(submission)
    submission.refresh_from_db()
    return _submission_dict(submission)


def run_check(submission_id) -> None:
    """AI tekshiruvni bajaradi va natijani saqlaydi (thread ichida chaqiriladi)."""
    submission = Submission.objects.select_related('assignment__course').get(pk=submission_id)
    a = submission.assignment
    try:
        result = ai.grade_file(
            submission.file.path,
            subject_text=a.course.subject,
            skill_key=a.skill_key,
            extra_instructions=a.extra_instructions,
        )
        score = result.get('overall_score')
        submission.result = result
        submission.overall_score = float(score) if score is not None else None
        # grade yorlig'ini har doim ball shkalasidan olamiz — model gohida
        # boshqacha yozishi mumkin
        submission.grade = ai.grade_label(score) or str(result.get('grade') or '')
        submission.status = Submission.Status.DONE
        submission.error = ''
    except Exception as exc:  # AI/tarmoq xatosi — foydalanuvchiga ko'rsatiladi
        submission.status = Submission.Status.ERROR
        submission.error = str(exc)[:2000]
    submission.checked_at = timezone.now()
    submission.save()


def _dispatch_check(submission: Submission) -> None:
    if not getattr(settings, 'HOMEWORK_CHECK_ASYNC', True):
        run_check(submission.id)
        return

    def _target(sub_id):
        try:
            run_check(sub_id)
        finally:
            close_old_connections()

    threading.Thread(target=_target, args=(submission.id,), daemon=True).start()


def get_submission(*, user: User, submission_id) -> dict:
    s = _get_submission(submission_id)
    allowed = (
        s.student_id == user.id
        or s.assignment.course.teacher_id == user.id
        or _is_parent_of(user, s.student)
    )
    if not allowed:
        raise PermissionDenied("Bu topshiriqni ko'rish huquqingiz yo'q.")
    return _submission_dict(s)


def submission_file(*, user: User, submission_id) -> tuple:
    s = _get_submission(submission_id)
    allowed = (
        s.student_id == user.id
        or s.assignment.course.teacher_id == user.id
        or _is_parent_of(user, s.student)
    )
    if not allowed:
        raise PermissionDenied("Bu faylni ko'rish huquqingiz yo'q.")
    return s.file.path, s.original_name


def recheck(*, user: User, submission_id) -> dict:
    s = _get_submission(submission_id)
    if s.assignment.course.teacher_id != user.id:
        raise PermissionDenied("Qayta tekshirishni faqat kurs o'qituvchisi boshlaydi.")
    s.status = Submission.Status.CHECKING
    s.error = ''
    s.save(update_fields=['status', 'error', 'updated_at'])
    _dispatch_check(s)
    s.refresh_from_db()
    return _submission_dict(s)
