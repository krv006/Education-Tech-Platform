from django.contrib import admin

from .models import ChatRoom, Message


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'kind', 'direct_status', 'updated_at']
    list_filter = ['kind', 'direct_status']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'room', 'text', 'created_at']
    search_fields = ['text', 'sender__username']
