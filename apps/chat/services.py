"""Chat service layer — yozuvchi biznes-logika."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core import audit
from apps.lessons.models import Course, Enrollment

from . import selectors
from .models import ChatRoom, Message, RoomRead


def ensure_course_room(course: Course) -> ChatRoom:
    """Kurs uchun guruh chat — yo'q bo'lsa yaratadi (kurs yaratilganda chaqiriladi)."""
    room, _ = ChatRoom.objects.get_or_create(
        kind=ChatRoom.Kind.COURSE, course=course,
    )
    return room


def _get_room(room_id) -> ChatRoom:
    try:
        return ChatRoom.objects.select_related('course', 'teacher', 'student').get(pk=room_id)
    except (ChatRoom.DoesNotExist, ValueError, TypeError):
        raise NotFound('Chat topilmadi.')


@transaction.atomic
def send_message(*, user: User, room_id, text: str) -> Message:
    room = _get_room(room_id)
    if not selectors.can_write(user, room):
        if room.kind == ChatRoom.Kind.DIRECT and room.direct_status != ChatRoom.DirectStatus.ACTIVE:
            raise PermissionDenied("Chat hali ochiq emas (so'rov qabul qilinmagan yoki bloklangan).")
        raise PermissionDenied("Bu chatga yozish huquqingiz yo'q.")
    text = (text or '').strip()
    if not text:
        raise ValidationError({'text': "Xabar bo'sh bo'lishi mumkin emas."})
    if len(text) > 4000:
        raise ValidationError({'text': 'Xabar juda uzun (maks. 4000 belgi).'})
    message = Message.objects.create(room=room, sender=user, text=text)
    # xona ro'yxatda tepaga chiqsin
    room.save(update_fields=['updated_at'])
    return message


def mark_read(*, user: User, room: ChatRoom):
    RoomRead.objects.update_or_create(
        room=room, user=user, defaults={'last_read_at': timezone.now()},
    )


@transaction.atomic
def request_direct(*, student: User, teacher_ref: str, request=None) -> ChatRoom:
    """O'quvchi o'z o'qituvchisiga direct so'rov yuboradi (1 martalik).

    Faqat o'zi o'qiydigan kurs o'qituvchisiga. Blocklangan bo'lsa qayta so'rov
    yuborsa yana PENDING bo'ladi (o'qituvchi yana ko'rib chiqadi).
    """
    if student.role != User.Role.STUDENT:
        raise PermissionDenied("Faqat o'quvchi so'rov yuboradi.")
    teacher = User.objects.filter(role=User.Role.TEACHER)\
        .filter(pk=teacher_ref if _is_uuid(teacher_ref) else None).first() \
        or User.objects.filter(role=User.Role.TEACHER, username=teacher_ref).first()
    if teacher is None:
        raise NotFound("O'qituvchi topilmadi.")
    is_my_teacher = Enrollment.objects.filter(
        student=student, status=Enrollment.Status.APPROVED, course__teacher=teacher,
    ).exists()
    if not is_my_teacher:
        raise PermissionDenied("Faqat o'z o'qituvchingizga yozish so'rovi yuborishingiz mumkin.")

    room, created = ChatRoom.objects.get_or_create(
        kind=ChatRoom.Kind.DIRECT, teacher=teacher, student=student,
        defaults={'direct_status': ChatRoom.DirectStatus.PENDING},
    )
    if not created and room.direct_status == ChatRoom.DirectStatus.BLOCKED:
        room.direct_status = ChatRoom.DirectStatus.PENDING
        room.save(update_fields=['direct_status', 'updated_at'])
    audit.record(action='chat.direct_request', actor=student, target=room, request=request)
    return room


def _is_uuid(value) -> bool:
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


@transaction.atomic
def respond_direct(*, teacher: User, room_id, action: str, request=None) -> ChatRoom:
    """O'qituvchi so'rovga javob beradi: accept -> ACTIVE, block -> BLOCKED.

    Ochiq chatni ham istalgan payt block qila oladi.
    """
    room = _get_room(room_id)
    if room.kind != ChatRoom.Kind.DIRECT or room.teacher_id != teacher.id:
        raise PermissionDenied("Bu so'rov sizga tegishli emas.")
    if action == 'accept':
        room.direct_status = ChatRoom.DirectStatus.ACTIVE
    elif action == 'block':
        room.direct_status = ChatRoom.DirectStatus.BLOCKED
    else:
        raise ValidationError({'action': "accept yoki block bo'lishi kerak."})
    room.save(update_fields=['direct_status', 'updated_at'])
    audit.record(action=f'chat.direct_{action}', actor=teacher, target=room, request=request)
    return room
