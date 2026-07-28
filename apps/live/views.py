"""Live views — yupqa qatlam: HTTP <-> live services."""
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import RequirePerm

from . import services


class RoomTokenView(APIView):
    permission_classes = [RequirePerm('room.token')]

    def post(self, request):
        payload = services.issue_room_token(
            user=request.user, lesson_id=request.data.get('lesson_id'), request=request,
        )
        return Response(payload)


class RoomLeaveView(APIView):
    permission_classes = [RequirePerm('room.leave')]

    def post(self, request):
        updated = services.leave_room(
            user=request.user, lesson_id=request.data.get('lesson_id'), request=request,
        )
        return Response({'updated': updated})


class AttentionView(APIView):
    """GET: hozir ko'rsatiladigan "Siz shu yerdamisiz?" tekshiruvi (polling).
    POST: javob berish."""

    permission_classes = [RequirePerm('room.token')]

    def get(self, request):
        check = services.pending_attention(
            user=request.user, lesson_id=request.query_params.get('lesson_id'),
        )
        if not check:
            return Response({'check': None})
        return Response({'check': {'id': str(check.id), 'due_at': check.due_at}})

    def post(self, request):
        check = services.answer_attention(user=request.user, check_id=request.data.get('check_id'))
        return Response({'answered_at': check.answered_at})


class FocusEventView(APIView):
    permission_classes = [RequirePerm('room.token')]

    def post(self, request):
        services.record_focus(
            user=request.user,
            lesson_id=request.data.get('lesson_id'),
            kind=request.data.get('kind'),
        )
        return Response({'ok': True})


class AllowShareView(APIView):
    permission_classes = [RequirePerm('room.moderate')]

    def post(self, request):
        services.grant_screen_share(
            teacher=request.user,
            lesson_id=request.data.get('lesson_id'),
            identity=request.data.get('identity'),
            request=request,
        )
        return Response({'ok': True})
