from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Attendance, Course, Enrollment, Lesson


class CourseSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    student_count = serializers.SerializerMethodField()
    my_status = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'teacher', 'title', 'subject', 'description', 'is_active',
            'student_count', 'my_status', 'created_at',
        ]
        read_only_fields = ['is_active']

    def get_student_count(self, obj) -> int:
        return obj.enrollments.filter(status=Enrollment.Status.APPROVED).count()

    def get_my_status(self, obj) -> str | None:
        """So'rov yuborgan foydalanuvchining shu kursdagi yozilish holati (katalog uchun)."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        enrollment = obj.enrollments.filter(student=request.user).first()
        return enrollment.status if enrollment else None


class LessonSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'course', 'course_title', 'title', 'starts_at',
            'duration_min', 'status', 'room_name', 'created_at',
        ]
        read_only_fields = ['room_name', 'status']


class EnrollmentSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course', 'course_title', 'student', 'status', 'created_at']


class AttendanceSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    minutes = serializers.IntegerField(read_only=True)
    attention_total = serializers.SerializerMethodField()
    attention_answered = serializers.SerializerMethodField()
    focus_exits = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id', 'lesson', 'lesson_title', 'student', 'joined_at', 'left_at', 'minutes',
            'attention_total', 'attention_answered', 'focus_exits',
        ]

    def get_attention_total(self, obj) -> int:
        return obj.lesson.attention_checks.filter(student=obj.student).count()

    def get_attention_answered(self, obj) -> int:
        return obj.lesson.attention_checks.filter(
            student=obj.student, answered_at__isnull=False,
        ).count()

    def get_focus_exits(self, obj) -> int:
        """O'quvchi dars davomida necha marta oynadan chiqib ketgani (anti-cheat)."""
        return obj.lesson.focus_events.filter(student=obj.student, kind='exit').count()
