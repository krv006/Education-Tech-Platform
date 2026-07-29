from django.contrib import admin

from .models import BoardErase, BoardGrant, BoardSheet


@admin.register(BoardSheet)
class BoardSheetAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'index', 'updated_at']


@admin.register(BoardGrant)
class BoardGrantAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'student', 'created_at']


@admin.register(BoardErase)
class BoardEraseAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'user', 'sheet_index', 'reason', 'created_at']
