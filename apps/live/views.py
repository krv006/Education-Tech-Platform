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
