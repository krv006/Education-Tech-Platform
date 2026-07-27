from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Attendance, Course, Enrollment, Lesson


class CourseSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    student_count = serializers.IntegerField(source='enrollments.count', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'teacher', 'title', 'subject', 'description', 'is_active', 'student_count', 'created_at']
        read_only_fields = ['is_active']


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
        fields = ['id', 'course', 'course_title', 'student', 'created_at']


class AttendanceSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'lesson', 'lesson_title', 'student', 'joined_at', 'left_at', 'minutes']
