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
def create_child(*, creator: User, username: str, password: str, request=None, **extra) -> User:
    """O'quvchi hisobini yaratadi — ota-ona yoki o'qituvchi.

    Ota-ona yaratsa — ParentChildLink darhol APPROVED (FRD: auth.child_create).
    O'qituvchi yaratsa — bog'lanish yaratilmaydi (o'qituvchi ota-ona emas);
    o'quvchiga invite_code beriladi, haqiqiy ota-ona keyin shu kod orqali
    bog'lanishi mumkin. O'qituvchi bolani alohida enroll/ orqali kursiga
    biriktiradi.
    """
    child = User(username=username, role=User.Role.STUDENT, **extra)
    child.set_password(password)
    child.save()
    if creator.role == User.Role.PARENT:
        ParentChildLink.objects.create(
            parent=creator, student=child, status=ParentChildLink.Status.APPROVED,
            responded_at=timezone.now(),
        )
    audit.record(action='child.create', actor=creator, target=child, request=request)
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


# ── Login jurnali: IP/qurilma o'zgarishini aniqlash (EduTech nazorat) ───────

def record_login(*, user: User, request) -> dict:
    """Har muvaffaqiyatli logindan keyin chaqiriladi (LoginView).

    Oxirgi login bilan solishtiradi: IP yoki qurilma (User-Agent) o'zgargan
    bo'lsa meta'da belgilanadi — ota-ona/admin "boshqa joydan kirildi"ni
    darhol ko'radi. Yozuv AuditLog'da (action='auth.login').
    """
    from apps.core.models import AuditLog

    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')

    last = (
        AuditLog.objects
        .filter(actor=user, action='auth.login')
        .order_by('-created_at')
        .first()
    )
    meta = {
        'user_agent': user_agent,
        'first_login': last is None,
        'new_ip': bool(last and str(last.ip_address or '') != str(ip or '')),
        'new_device': bool(last and (last.meta or {}).get('user_agent', '') != user_agent),
    }
    audit.record(action='auth.login', actor=user, meta=meta, request=request)
    return meta


def login_history(*, viewer: User, student_id=None, limit: int = 50) -> list:
    """Login tarixi: o'zi uchun; ota-ona TASDIQLANGAN bolasi uchun ham."""
    from apps.core.models import AuditLog

    target = viewer
    if student_id:
        allowed = ParentChildLink.objects.filter(
            parent=viewer, student_id=student_id,
            status=ParentChildLink.Status.APPROVED,
        ).exists()
        if not allowed:
            raise PermissionDenied("Bu foydalanuvchi login tarixini ko'rish huquqingiz yo'q.")
        try:
            target = User.objects.get(pk=student_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise NotFound('Foydalanuvchi topilmadi.')

    rows = (
        AuditLog.objects
        .filter(actor=target, action='auth.login')
        .order_by('-created_at')[:limit]
    )
    return [{
        'at': r.created_at,
        'ip': r.ip_address,
        'user_agent': (r.meta or {}).get('user_agent', ''),
        'new_ip': (r.meta or {}).get('new_ip', False),
        'new_device': (r.meta or {}).get('new_device', False),
    } for r in rows]


def logout(*, user: User, refresh_token: str | None = None, request=None) -> None:
    """Chiqish — berilgan refresh token bekor qilinadi (blacklist), qayta
    ishlatib bo'lmaydi. Access token o'z muddati tugaguncha amal qiladi
    (JWT'ning odatiy xatti-harakati); boshqa qurilmalardagi sessiyalarga
    ta'sir qilmaydi."""
    if refresh_token:
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            RefreshToken(refresh_token).blacklist()
        except Exception:  # noqa: BLE001 — token allaqachon yaroqsiz/eskirgan bo'lishi mumkin
            pass

    audit.record(action='auth.logout', actor=user, target=user, request=request)
