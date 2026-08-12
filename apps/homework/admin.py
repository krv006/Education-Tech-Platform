from django.contrib import admin

from .models import Assignment, Submission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'lesson', 'skill_key', 'due_at', 'created_at')
    search_fields = ('title', 'course__title')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'overall_score', 'grade', 'checked_at')
    list_filter = ('status',)
    search_fields = ('student__username', 'assignment__title')
