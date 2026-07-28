from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import ChatRoom, Message


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'room', 'sender', 'text', 'created_at']
        read_only_fields = ['room', 'sender']


class ChatRoomSerializer(serializers.ModelSerializer):
    """Chat ro'yxati qatori — Telegram uslubidagi list uchun hamma narsa bitta joyda."""

    title = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'kind', 'course', 'direct_status',
            'title', 'last_message', 'unread', 'other_user', 'updated_at',
        ]

    def get_title(self, obj) -> str:
        return obj.title_for(self.context['request'].user)

    def get_other_user(self, obj):
        if obj.kind != ChatRoom.Kind.DIRECT:
            return None
        user = self.context['request'].user
        other = obj.teacher if user.id == obj.student_id else obj.student
        return UserSerializer(other).data if other else None

    def get_last_message(self, obj):
        # view'da prefetch qilingan bo'lsa ro'yxatdan olamiz (N+1 oldini olish)
        cached = getattr(obj, 'last_message_list', None)
        msg = cached[0] if cached else obj.messages.order_by('-created_at').first()
        if not msg:
            return None
        return {
            'text': msg.text[:80],
            'sender': msg.sender.first_name or msg.sender.username,
            'created_at': msg.created_at,
        }

    def get_unread(self, obj) -> int:
        user = self.context['request'].user
        read = next((r for r in getattr(obj, 'my_reads', [])), None)
        qs = obj.messages.exclude(sender=user)
        if read:
            qs = qs.filter(created_at__gt=read.last_read_at)
        return qs.count()
