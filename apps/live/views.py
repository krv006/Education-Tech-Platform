from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from livekit.api import AccessToken, VideoGrants
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.lessons.models import Attendance, Lesson


class RoomTokenView(APIView):
    """POST {lesson_id} -> LiveKit access token for that lesson's room.

    Teacher of the course or an enrolled student only. Joining stamps
    attendance.joined_at (FRD: attendance.auto_mark) and flips the lesson to LIVE
    when the teacher connects.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        lesson_id = request.data.get('lesson_id')
        try:
            lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
        except (Lesson.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Dars topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_teacher = lesson.course.teacher_id == user.id
        is_enrolled = lesson.course.enrollments.filter(student=user).exists()
        if not (is_teacher or is_enrolled):
            return Response({'detail': 'Bu darsga kirish huquqingiz yo‘q.'}, status=status.HTTP_403_FORBIDDEN)
        if lesson.status in (Lesson.Status.FINISHED, Lesson.Status.CANCELLED):
            return Response({'detail': 'Dars tugagan yoki bekor qilingan.'}, status=status.HTTP_400_BAD_REQUEST)

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
            attendance, _ = Attendance.objects.get_or_create(lesson=lesson, student=user)
            if attendance.joined_at is None:
                attendance.joined_at = timezone.now()
                attendance.save(update_fields=['joined_at'])

        return Response({
            'token': token.to_jwt(),
            'url': settings.LIVEKIT_URL,
            'room': lesson.room_name,
            'is_teacher': is_teacher,
        })


class RoomLeaveView(APIView):
    """POST {lesson_id} -> stamp attendance.left_at for the student."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        lesson_id = request.data.get('lesson_id')
        updated = Attendance.objects.filter(
            lesson_id=lesson_id, student=request.user, left_at__isnull=True
        ).update(left_at=timezone.now())
        return Response({'updated': bool(updated)})
