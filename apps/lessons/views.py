"""Lessons views — yupqa qatlam: HTTP <-> service/selector."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import RequirePerm

from . import selectors, services
from .models import Course, Enrollment
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
        if self.action in ('enroll', 'unenroll', 'catalog'):
            return [RequirePerm('course.enroll')()]
        if self.action in ('requests', 'respond_request'):
            return [RequirePerm('course.edit')()]  # faqat o'qituvchi (o'z kurslari service'da tekshiriladi)
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.action == 'catalog':
            return Course.objects.filter(is_active=True).select_related('teacher').order_by('title')
        return selectors.courses_for(self.request.user)

    @action(detail=False)
    def catalog(self, request):
        """Yozilish uchun ochiq kurslar — o'quvchi/ota-ona ko'radi (courses_for faqat yozilganlarni beradi)."""
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def perform_create(self, serializer):
        serializer.instance = services.create_course(
            teacher=self.request.user, request=self.request, **serializer.validated_data,
        )

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        enrollment, created = services.enroll(
            course_id=pk, by_user=request.user,
            student_id=request.data.get('student_id'),
            student_ref=request.data.get('student'),
            request=request,
        )
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def unenroll(self, request, pk=None):
        removed = services.unenroll(
            course_id=pk, by_user=request.user,
            student_id=request.data.get('student_id'), request=request,
        )
        return Response({'removed': removed})

    @action(detail=False)
    def requests(self, request):
        """O'qituvchi kurslariga kelgan kutilayotgan yozilish so'rovlari — panel xabarnomasi."""
        qs = (
            Enrollment.objects
            .filter(course__teacher=request.user, status=Enrollment.Status.PENDING)
            .select_related('student', 'course')
            .order_by('created_at')
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(EnrollmentSerializer(page, many=True).data)

    @action(detail=False, methods=['post'], url_path='requests/respond')
    def respond_request(self, request):
        enrollment = services.respond_enrollment(
            teacher=request.user,
            enrollment_id=request.data.get('enrollment_id'),
            action=request.data.get('action'),
            request=request,
        )
        return Response(EnrollmentSerializer(enrollment).data)

    @action(detail=True)
    def students(self, request, pk=None):
        """Kursga yozilgan o'quvchilar — faqat kurs o'qituvchisi (va admin) ko'radi."""
        course = self.get_object()
        if course.teacher_id != request.user.id and request.user.role not in ('admin', 'super_admin'):
            self.permission_denied(request, message="Faqat kurs o'qituvchisi o'quvchilar ro'yxatini ko'radi.")
        qs = course.enrollments.select_related('student').order_by('student__first_name')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(EnrollmentSerializer(page, many=True).data)


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
