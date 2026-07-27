"""Live service layer — LiveKit token berish va davomat bosish."""
from datetime import timedelta

from django.conf import settings
from livekit.api import AccessToken, VideoGrants
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core import audit
from apps.lessons import services as lesson_services
from apps.lessons.models import Enrollment, Lesson


def issue_room_token(*, user: User, lesson_id, request=None) -> dict:
    """Dars xonasiga kirish tokeni.

    Faqat kurs o'qituvchisi yoki yozilgan o'quvchi. O'quvchiga davomat bosiladi
    (FRD: attendance.auto_mark), o'qituvchi kirsa dars LIVE bo'ladi.
    """
    try:
        lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')

    is_teacher = lesson.course.teacher_id == user.id
    is_enrolled = lesson.course.enrollments.filter(
        student=user, status=Enrollment.Status.APPROVED,
    ).exists()
    if not (is_teacher or is_enrolled):
        raise PermissionDenied("Bu darsga kirish huquqingiz yo'q.")
    if lesson.status in (Lesson.Status.FINISHED, Lesson.Status.CANCELLED):
        raise ValidationError('Dars tugagan yoki bekor qilingan.')

    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(f'user-{user.id}')
        .with_name(user.get_full_name() or user.username)
        .with_ttl(timedelta(hours=2))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=lesson.room_name,
                room_admin=is_teacher,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    if is_teacher and lesson.status == Lesson.Status.SCHEDULED:
        lesson.status = Lesson.Status.LIVE
        lesson.save(update_fields=['status'])
    if user.role == User.Role.STUDENT:
        lesson_services.mark_joined(lesson=lesson, student=user)

    audit.record(action='room.join', actor=user, target=lesson, request=request)
    return {
        'token': token.to_jwt(),
        'url': settings.LIVEKIT_URL,
        'room': lesson.room_name,
        'is_teacher': is_teacher,
    }


def leave_room(*, user: User, lesson_id, request=None) -> bool:
    updated = lesson_services.mark_left(lesson_id=lesson_id, student=user)
    if updated:
        audit.record(action='room.leave', actor=user, meta={'lesson_id': str(lesson_id)}, request=request)
    return updated
