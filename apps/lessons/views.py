from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ParentChildLink, User

from .models import Attendance, Course, Enrollment, Lesson
from .serializers import (
    AttendanceSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    LessonSerializer,
)


class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CourseSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.TEACHER:
            return Course.objects.filter(teacher=user)
        if user.role == User.Role.STUDENT:
            return Course.objects.filter(enrollments__student=user)
        if user.role == User.Role.PARENT:
            return Course.objects.filter(
                enrollments__student__parent_links__parent=user,
                enrollments__student__parent_links__status=ParentChildLink.Status.APPROVED,
            ).distinct()
        return Course.objects.all()

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.TEACHER:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Faqat o'qituvchi kurs yarata oladi.")
        serializer.save(teacher=self.request.user)

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Student enrolls self; parent enrolls an approved-linked child (student_id in body).

        Fetched directly (not via get_queryset) — enrolling into a course you are
        not yet part of is exactly the point here.
        """
        try:
            course = Course.objects.get(pk=pk, is_active=True)
        except Course.DoesNotExist:
            return Response({'detail': 'Kurs topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if request.user.role == User.Role.STUDENT:
            student = request.user
        elif request.user.role == User.Role.PARENT:
            student_id = request.data.get('student_id')
            link_exists = ParentChildLink.objects.filter(
                parent=request.user, student_id=student_id, status=ParentChildLink.Status.APPROVED
            ).exists()
            if not link_exists:
                return Response({'detail': "Bu o'quvchi sizga bog'lanmagan."}, status=status.HTTP_403_FORBIDDEN)
            student = User.objects.get(pk=student_id)
        else:
            return Response({'detail': 'Faqat o‘quvchi yoki ota-ona yozila oladi.'}, status=status.HTTP_403_FORBIDDEN)
        enrollment, created = Enrollment.objects.get_or_create(course=course, student=student)
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LessonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LessonSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Lesson.objects.select_related('course')
        if user.role == User.Role.TEACHER:
            return qs.filter(course__teacher=user)
        if user.role == User.Role.STUDENT:
            return qs.filter(course__enrollments__student=user)
        if user.role == User.Role.PARENT:
            return qs.filter(
                course__enrollments__student__parent_links__parent=user,
                course__enrollments__student__parent_links__status=ParentChildLink.Status.APPROVED,
            ).distinct()
        return qs

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        if course.teacher != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Faqat kurs egasi dars qo'sha oladi.")
        serializer.save()

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        """Teacher ends the lesson; open attendances get left_at stamped."""
        lesson = self.get_object()
        if lesson.course.teacher != request.user:
            return Response({'detail': 'Faqat o‘qituvchi darsni tugata oladi.'}, status=status.HTTP_403_FORBIDDEN)
        lesson.status = Lesson.Status.FINISHED
        lesson.save(update_fields=['status'])
        lesson.attendances.filter(left_at__isnull=True).update(left_at=timezone.now())
        return Response(LessonSerializer(lesson).data)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """Attendance reports: teacher -> own lessons, student -> self, parent -> approved children."""

    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related('lesson', 'student')
        if user.role == User.Role.TEACHER:
            return qs.filter(lesson__course__teacher=user)
        if user.role == User.Role.STUDENT:
            return qs.filter(student=user)
        if user.role == User.Role.PARENT:
            return qs.filter(
                student__parent_links__parent=user,
                student__parent_links__status=ParentChildLink.Status.APPROVED,
            )
        return qs
