"""Chat views — yupqa qatlam: HTTP <-> chat services/selectors."""
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import RequirePerm

from . import selectors, services
from .models import ChatRoom, Message, RoomRead
from .serializers import ChatRoomSerializer, MessageSerializer


class ChatRoomViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChatRoomSerializer

    def get_permissions(self):
        return [RequirePerm('chat.use')()]

    def get_queryset(self):
        user = self.request.user
        return selectors.rooms_for(user).prefetch_related(
            Prefetch(
                'messages',
                queryset=Message.objects.select_related('sender').order_by('-created_at')[:1],
                to_attr='last_message_list',
            ),
            Prefetch('reads', queryset=RoomRead.objects.filter(user=user), to_attr='my_reads'),
        )

    @action(detail=True)
    def messages(self, request, pk=None):
        """Xabarlar (polling: ?after=<ISO vaqt> — faqat yangilari). O'qilgan deb belgilaydi."""
        room = self.get_object()
        if not selectors.can_read(request.user, room):
            self.permission_denied(request)
        qs = room.messages.select_related('sender')
        after = request.query_params.get('after')
        if after:
            qs = qs.filter(created_at__gt=after)
        else:
            qs = qs.order_by('-created_at')[:100]
            qs = sorted(qs, key=lambda m: m.created_at)
        services.mark_read(user=request.user, room=room)
        return Response(MessageSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        message = services.send_message(
            user=request.user, room_id=pk, text=request.data.get('text'),
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='direct/request')
    def direct_request(self, request):
        """O'quvchi -> o'qituvchi: direct chat so'rovi (teacher = id yoki username)."""
        room = services.request_direct(
            student=request.user, teacher_ref=request.data.get('teacher'), request=request,
        )
        return Response(
            ChatRoomSerializer(room, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='direct/respond')
    def direct_respond(self, request):
        """O'qituvchi: accept yoki block."""
        room = services.respond_direct(
            teacher=request.user,
            room_id=request.data.get('room_id'),
            action=request.data.get('action'),
            request=request,
        )
        return Response(ChatRoomSerializer(room, context={'request': request}).data)

    @action(detail=False)
    def teachers(self, request):
        """O'quvchining o'qituvchilari — yangi direct so'rov yuborish ro'yxati uchun."""
        from apps.accounts.models import User
        from apps.accounts.serializers import UserSerializer
        from apps.lessons.models import Enrollment

        teacher_ids = Enrollment.objects.filter(
            student=request.user, status=Enrollment.Status.APPROVED,
        ).values('course__teacher_id')
        teachers = User.objects.filter(pk__in=teacher_ids)
        existing = {
            r.teacher_id: r for r in
            ChatRoom.objects.filter(kind=ChatRoom.Kind.DIRECT, student=request.user)
        }
        data = []
        for t in teachers:
            room = existing.get(t.id)
            data.append({
                **UserSerializer(t).data,
                'direct_status': room.direct_status if room else None,
                'room_id': str(room.id) if room else None,
            })
        return Response(data)
