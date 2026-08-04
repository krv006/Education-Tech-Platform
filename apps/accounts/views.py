"""Accounts views — yupqa qatlam: HTTP <-> service/selector.

Biznes-logika services.py da, ko'rish huquqi selectors.py da, ruxsatlar
apps.core.permissions registry'sida.
"""
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.permissions import RequirePerm

from . import selectors, services
from .serializers import (
    ChildCreateSerializer,
    ConsentSerializer,
    LinkRequestSerializer,
    LinkRespondSerializer,
    LinkSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(request=request, **serializer.validated_data)
        return Response(RegisterSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Muvaffaqiyatli login — IP/qurilma jurnaliga yoziladi (auth.login)
        if response.status_code == 200:
            from .models import User

            user = User.objects.filter(username=request.data.get('username', '')).first()
            if user is not None:
                services.record_login(user=user, request=request)
        return response


class LoginHistoryView(APIView):
    """Login tarixi: o'ziniki; ota-ona `?student=<id>` bilan bolasiniki.

    Har yozuvda: vaqt, IP, qurilma (User-Agent) va o'zgarish bayroqlari
    (new_ip / new_device) — "boshqa joydan kirildi" darhol ko'rinadi.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.login_history(
            viewer=request.user, student_id=request.query_params.get('student'),
        ))


class RefreshView(TokenRefreshView):
    throttle_scope = 'auth'


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChildCreateView(APIView):
    permission_classes = [RequirePerm('child.create')]

    def post(self, request):
        serializer = ChildCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = services.create_child(parent=request.user, request=request, **serializer.validated_data)
        return Response(ChildCreateSerializer(child).data, status=status.HTTP_201_CREATED)


class LinkListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LinkSerializer

    def get_queryset(self):
        return selectors.links_for_user(self.request.user)


class LinkRequestView(APIView):
    permission_classes = [RequirePerm('link.request')]

    def post(self, request):
        serializer = LinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link, created = services.request_link(
            parent=request.user, invite_code=serializer.validated_data['invite_code'], request=request,
        )
        return Response(
            LinkSerializer(link).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LinkRespondView(APIView):
    permission_classes = [RequirePerm('link.respond')]

    def post(self, request, pk):
        serializer = LinkRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = services.respond_link(
            student=request.user, link_id=pk, action=serializer.validated_data['action'], request=request,
        )
        return Response(LinkSerializer(link).data)


class ConsentListCreateView(generics.ListCreateAPIView):
    permission_classes = [RequirePerm('consent.manage')]
    serializer_class = ConsentSerializer

    def get_queryset(self):
        return selectors.consents_for_parent(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = services.set_consent(
            parent=request.user,
            student=serializer.validated_data['student'],
            kind=serializer.validated_data['kind'],
            granted=serializer.validated_data['granted'],
            request=request,
        )
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)
