from django.contrib import admin

from .models import Attendance, Course, Enrollment, Lesson


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'subject', 'is_active', 'created_at']
    list_filter = ['is_active', 'subject']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'starts_at', 'duration_min', 'status', 'room_name']
    list_filter = ['status']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'created_at']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'lesson', 'joined_at', 'left_at']
