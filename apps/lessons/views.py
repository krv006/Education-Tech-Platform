"""Lessons views — yupqa qatlam: HTTP <-> service/selector."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import RequirePerm

from . import selectors, services
from .serializers import (
    AttendanceSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    LessonSerializer,
)


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    search_fields = ['title', 'subject']
    ordering_fields = ['created_at', 'title']

    def get_permissions(self):
        if self.action == 'create':
            return [RequirePerm('course.create')()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [RequirePerm('course.edit')()]
        if self.action == 'enroll':
            return [RequirePerm('course.enroll')()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return selectors.courses_for(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = services.create_course(
            teacher=self.request.user, request=self.request, **serializer.validated_data,
        )

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        enrollment, created = services.enroll(
            course_id=pk, by_user=request.user,
            student_id=request.data.get('student_id'), request=request,
        )
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    filterset_fields = ['course', 'status']
    ordering_fields = ['starts_at']

    def get_permissions(self):
        if self.action == 'create':
            return [RequirePerm('lesson.schedule')()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [RequirePerm('lesson.edit')()]
        if self.action == 'finish':
            return [RequirePerm('lesson.finish')()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return selectors.lessons_for(self.request.user)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        course = data.pop('course')
        serializer.instance = services.schedule_lesson(
            teacher=self.request.user, course=course, request=self.request, **data,
        )

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        lesson = self.get_object()
        lesson = services.finish_lesson(teacher=request.user, lesson=lesson, request=request)
        return Response(LessonSerializer(lesson).data)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """Davomat hisoboti: o'qituvchi -> o'z darslari, o'quvchi -> o'zi, ota-ona -> tasdiqlangan bolalari."""

    serializer_class = AttendanceSerializer
    filterset_fields = ['lesson', 'student']

    def get_permissions(self):
        return [RequirePerm('attendance.view')()]

    def get_queryset(self):
        return selectors.attendance_for(self.request.user)
