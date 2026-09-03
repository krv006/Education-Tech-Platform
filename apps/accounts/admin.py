from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Consent, ParentChildLink, TeacherCertificate, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'role', 'phone', 'invite_code', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('EdTech', {'fields': ('role', 'phone', 'invite_code')}),
    )


@admin.register(ParentChildLink)
class ParentChildLinkAdmin(admin.ModelAdmin):
    list_display = ['parent', 'student', 'status', 'created_at', 'responded_at']
    list_filter = ['status']


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ['student', 'kind', 'granted', 'granted_by', 'updated_at']
    list_filter = ['kind', 'granted']


@admin.register(TeacherCertificate)
class TeacherCertificateAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'title', 'created_at']
    search_fields = ['teacher__username', 'title']
