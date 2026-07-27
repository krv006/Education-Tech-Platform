"""Accounts service layer — barcha yozuvchi biznes-logika shu yerda.

Qoida: view'lar faqat HTTP bilan ishlaydi (parse/serialize), qaror va yozuv —
service'da. Har bir muhim harakat audit'ga tushadi.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core import audit

from .models import Consent, ParentChildLink, User


@transaction.atomic
def register_user(*, username: str, password: str, role: str, request=None, **extra) -> User:
    if role not in (User.Role.TEACHER, User.Role.PARENT):
        raise ValidationError({'role': "Faqat o'qituvchi yoki ota-ona ro'yxatdan o'ta oladi."})
    user = User(username=username, role=role, **extra)
    user.set_password(password)
    user.save()
    audit.record(action='auth.register', actor=user, target=user, meta={'role': role}, request=request)
    return user


@transaction.atomic
def create_child(*, parent: User, username: str, password: str, request=None, **extra) -> User:
    """Ota-ona bola hisobini yaratadi — bog'lanish darhol APPROVED (FRD: auth.child_create)."""
    child = User(username=username, role=User.Role.STUDENT, **extra)
    child.set_password(password)
    child.save()
    ParentChildLink.objects.create(
        parent=parent, student=child, status=ParentChildLink.Status.APPROVED,
        responded_at=timezone.now(),
    )
    audit.record(action='child.create', actor=parent, target=child, request=request)
    return child


@transaction.atomic
def request_link(*, parent: User, invite_code: str, request=None) -> tuple[ParentChildLink, bool]:
    """Taklif-kod orqali so'rov — o'quvchi tasdig'igacha PENDING (rozilik oqimi)."""
    try:
        student = User.objects.get(invite_code=invite_code.strip().upper(), role=User.Role.STUDENT)
    except User.DoesNotExist:
        raise NotFound('Bunday taklif kodi topilmadi.')

    link, created = ParentChildLink.objects.get_or_create(
        parent=parent, student=student,
        defaults={'status': ParentChildLink.Status.PENDING},
    )
    if not created and link.status == ParentChildLink.Status.DECLINED:
        link.status = ParentChildLink.Status.PENDING
        link.responded_at = None
        link.save(update_fields=['status', 'responded_at'])
    audit.record(action='link.request', actor=parent, target=link, request=request)
    return link, created


@transaction.atomic
def respond_link(*, student: User, link_id, action: str, request=None) -> ParentChildLink:
    """O'quvchi so'rovni tasdiqlaydi/rad etadi. Tasdiqlanganini keyin bekor qilishi ham mumkin."""
    try:
        link = ParentChildLink.objects.get(pk=link_id, student=student)
    except ParentChildLink.DoesNotExist:
        raise NotFound("So'rov topilmadi.")
    link.status = (
        ParentChildLink.Status.APPROVED if action == 'approve' else ParentChildLink.Status.DECLINED
    )
    link.responded_at = timezone.now()
    link.save(update_fields=['status', 'responded_at'])
    audit.record(action=f'link.{action}', actor=student, target=link, request=request)
    return link


@transaction.atomic
def set_consent(*, parent: User, student: User, kind: str, granted: bool, request=None) -> Consent:
    """Rozilik bayrog'i — faqat tasdiqlangan bog'lanishdagi ota-ona o'zgartira oladi."""
    is_linked = ParentChildLink.objects.filter(
        parent=parent, student=student, status=ParentChildLink.Status.APPROVED
    ).exists()
    if not is_linked:
        raise PermissionDenied("Bu o'quvchi sizga bog'lanmagan.")
    consent, _ = Consent.objects.update_or_create(
        student=student, kind=kind,
        defaults={'granted': granted, 'granted_by': parent},
    )
    audit.record(
        action='consent.set', actor=parent, target=consent,
        meta={'kind': kind, 'granted': granted}, request=request,
    )
    return consent
