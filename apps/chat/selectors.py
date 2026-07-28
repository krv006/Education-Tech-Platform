"""Chat selectors — o'qish yo'li: kim qaysi xonani ko'radi."""
from django.db.models import Q

from apps.accounts.models import User
from apps.lessons.models import Enrollment

from .models import ChatRoom


def rooms_for(user: User):
    """Foydalanuvchi a'zo bo'lgan xonalar.

    - Kurs guruhi: o'qituvchi (kurs egasi) yoki tasdiqlangan o'quvchi.
    - Direct: taraflardan biri (pending/blocked ham ro'yxatda ko'rinadi —
      holatini ko'rsatish uchun; yozish esa faqat ACTIVE'da).
    """
    approved_courses = Enrollment.objects.filter(
        student=user, status=Enrollment.Status.APPROVED,
    ).values('course_id')
    return (
        ChatRoom.objects
        .filter(
            Q(kind=ChatRoom.Kind.COURSE)
            & (Q(course__teacher=user) | Q(course_id__in=approved_courses))
            | Q(kind=ChatRoom.Kind.DIRECT) & (Q(teacher=user) | Q(student=user))
        )
        .select_related('course', 'course__teacher', 'teacher', 'student')
        .distinct()
    )


def can_read(user: User, room: ChatRoom) -> bool:
    if room.kind == ChatRoom.Kind.DIRECT:
        return user.id in (room.teacher_id, room.student_id)
    if room.course.teacher_id == user.id:
        return True
    return Enrollment.objects.filter(
        course=room.course, student=user, status=Enrollment.Status.APPROVED,
    ).exists()


def can_write(user: User, room: ChatRoom) -> bool:
    if not can_read(user, room):
        return False
    if room.kind == ChatRoom.Kind.DIRECT:
        return room.direct_status == ChatRoom.DirectStatus.ACTIVE
    return True
