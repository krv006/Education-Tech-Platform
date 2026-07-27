from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Consent, ParentChildLink, User
from .permissions import IsParent, IsStudent
from .serializers import (
    ChildCreateSerializer,
    ConsentSerializer,
    LinkRequestSerializer,
    LinkRespondSerializer,
    LinkSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChildCreateView(generics.CreateAPIView):
    permission_classes = [IsParent]
    serializer_class = ChildCreateSerializer


class LinkListView(generics.ListAPIView):
    """Both sides see their own links: parent -> children, student -> parents."""

    permission_classes = [IsAuthenticated]
    serializer_class = LinkSerializer

    def get_queryset(self):
        return ParentChildLink.objects.filter(
            Q(parent=self.request.user) | Q(student=self.request.user)
        ).select_related('parent', 'student')


class LinkRequestView(APIView):
    """Parent enters the student's invite code -> a PENDING link awaiting student approval."""

    permission_classes = [IsParent]

    def post(self, request):
        serializer = LinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.student
        link, created = ParentChildLink.objects.get_or_create(
            parent=request.user,
            student=student,
            defaults={'status': ParentChildLink.Status.PENDING},
        )
        if not created and link.status == ParentChildLink.Status.DECLINED:
            link.status = ParentChildLink.Status.PENDING
            link.responded_at = None
            link.save(update_fields=['status', 'responded_at'])
        return Response(LinkSerializer(link).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class LinkRespondView(APIView):
    """Student approves/declines a link. An approved link can be revoked later the same way."""

    permission_classes = [IsStudent]

    def post(self, request, pk):
        try:
            link = ParentChildLink.objects.get(pk=pk, student=request.user)
        except ParentChildLink.DoesNotExist:
            return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        serializer = LinkRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        link.status = (
            ParentChildLink.Status.APPROVED if action == 'approve' else ParentChildLink.Status.DECLINED
        )
        link.responded_at = timezone.now()
        link.save(update_fields=['status', 'responded_at'])
        return Response(LinkSerializer(link).data)


class ConsentListCreateView(generics.ListCreateAPIView):
    """Parent manages consent flags for an approved-linked child."""

    permission_classes = [IsParent]
    serializer_class = ConsentSerializer

    def get_queryset(self):
        return Consent.objects.filter(
            student__parent_links__parent=self.request.user,
            student__parent_links__status=ParentChildLink.Status.APPROVED,
        )

    def perform_create(self, serializer):
        student = serializer.validated_data['student']
        if not ParentChildLink.objects.filter(
            parent=self.request.user, student=student, status=ParentChildLink.Status.APPROVED
        ).exists():
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Bu o'quvchi sizga bog'lanmagan.")
        Consent.objects.update_or_create(
            student=student,
            kind=serializer.validated_data['kind'],
            defaults={
                'granted': serializer.validated_data['granted'],
                'granted_by': self.request.user,
            },
        )
