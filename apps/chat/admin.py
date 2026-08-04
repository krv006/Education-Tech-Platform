from django.contrib import admin

from .models import ChatRoom, Message, RoomRead


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'kind', 'direct_status', 'updated_at']
    list_filter = ['kind', 'direct_status']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'room', 'text', 'created_at']
    search_fields = ['text', 'sender__username']
    date_hierarchy = 'created_at'


@admin.register(RoomRead)
class RoomReadAdmin(admin.ModelAdmin):
    """O'qilgan belgilar — kim qaysi xonani qachongacha o'qigan."""

    list_display = ['user', 'room', 'last_read_at']
    search_fields = ['user__username']
