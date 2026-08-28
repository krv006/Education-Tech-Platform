"""Live service layer — LiveKit token berish, davomat, diqqat tekshiruvi, share ruxsati."""
import asyncio
import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from livekit.api import AccessToken, LiveKitAPI, UpdateParticipantRequest, VideoGrants
from livekit.protocol.models import ParticipantPermission, TrackSource
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core import audit
from apps.lessons import services as lesson_services
from apps.lessons.models import AttentionCheck, Enrollment, FocusAlert, FocusEvent, Lesson, LessonBan

ATTENTION_WINDOW_SEC = 15  # popup ekranda turadigan vaqt (EduTech.docx)
ATTENTION_GRACE_SEC = 8    # tarmoq kechikishi uchun qo'shimcha imkon


def issue_room_token(*, user: User, lesson_id, request=None) -> dict:
    """Dars xonasiga kirish tokeni.

    Faqat kurs o'qituvchisi yoki yozilgan o'quvchi. O'quvchiga davomat bosiladi
    (FRD: attendance.auto_mark), o'qituvchi kirsa dars LIVE bo'ladi.
    """
    try:
        lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')

    is_teacher = lesson.course.teacher_id == user.id
    is_enrolled = lesson.course.enrollments.filter(
        student=user, status=Enrollment.Status.APPROVED,
    ).exists()
    if not (is_teacher or is_enrolled):
        raise PermissionDenied("Bu darsga kirish huquqingiz yo'q.")
    if not is_teacher and LessonBan.objects.filter(lesson=lesson, student=user).exists():
        raise PermissionDenied("Siz bu darsdan chetlashtirilgansiz.")
    if lesson.status in (Lesson.Status.FINISHED, Lesson.Status.CANCELLED):
        raise ValidationError('Dars tugagan yoki bekor qilingan.')

    # O'quvchi default mikrofon va ekran share qila olmaydi — o'qituvchi
    # ruxsat berganda grant_mic()/grant_screen_share() orqali jonli ochiladi
    # (kamera esa erkin — faqat ovoz cheklanadi, tartib buzilmasin uchun).
    publish_sources = None if is_teacher else ['camera']
    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(f'user-{user.id}')
        .with_name(user.get_full_name() or user.username)
        .with_ttl(timedelta(hours=2))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=lesson.room_name,
                room_admin=is_teacher,
                can_publish=True,
                can_subscribe=True,
                can_publish_sources=publish_sources,
            )
        )
    )

    if is_teacher and lesson.status == Lesson.Status.SCHEDULED:
        lesson.status = Lesson.Status.LIVE
        lesson.save(update_fields=['status'])
        # Guruh chatga "jonli dars boshlandi" signali (Telegram uslubidagi
        # guruh video chat chizig'i). Xato bo'lsa ham darsga kirish to'xtamasin.
        try:
            from apps.chat import realtime as chat_realtime
            chat_realtime.broadcast_lesson_live(lesson)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger('apps').exception('lesson_live broadcast failed')
    if is_teacher and lesson.status == Lesson.Status.LIVE:
        # Video yozuv KAFOLATLANADI (EduTech.docx) — har kirishda: birinchi
        # kirishda boshlaydi, qayta kirsa/backend restart bo'lsa aktiv
        # egress'ni topib oladi yoki qaytadan boshlaydi. Fonda, xatosi
        # darsga xalaqit bermaydi.
        start_recording(lesson=lesson)
    if user.role == User.Role.STUDENT:
        lesson_services.mark_joined(lesson=lesson, student=user)
        _ensure_attention_schedule(lesson=lesson, student=user)

    audit.record(action='room.join', actor=user, target=lesson, request=request)
    return {
        'token': token.to_jwt(),
        'url': settings.LIVEKIT_URL,
        'room': lesson.room_name,
        'is_teacher': is_teacher,
    }


def leave_room(*, user: User, lesson_id, request=None) -> bool:
    updated = lesson_services.mark_left(lesson_id=lesson_id, student=user)
    if updated:
        audit.record(action='room.leave', actor=user, meta={'lesson_id': str(lesson_id)}, request=request)
    return updated


# ── "Siz shu yerdamisiz?" — diqqat tekshiruvi ──────────────────────────────

def _ensure_attention_schedule(*, lesson: Lesson, student: User):
    """Dars oynasi ichida 3-5 ta tasodifiy tekshiruv vaqti yaratadi (server tomonda —
    o'quvchi jadvalni oldindan ko'ra olmaydi)."""
    if AttentionCheck.objects.filter(lesson=lesson, student=student).exists():
        return
    now = timezone.now()
    end = lesson.starts_at + timedelta(minutes=lesson.duration_min)
    start = max(now + timedelta(minutes=1), lesson.starts_at)
    window = (end - start).total_seconds()
    if window < 120:  # dars deyarli tugagan — tekshiruv qo'yilmaydi
        return
    count = random.randint(3, 5)
    offsets = sorted(random.sample(range(30, int(window) - 30), k=count))
    AttentionCheck.objects.bulk_create([
        AttentionCheck(lesson=lesson, student=student, due_at=start + timedelta(seconds=o))
        for o in offsets
    ])


def pending_attention(*, user: User, lesson_id) -> AttentionCheck | None:
    """Hozir ko'rsatilishi kerak bo'lgan tekshiruv (15s oynasi ichida, javobsiz)."""
    now = timezone.now()
    return AttentionCheck.objects.filter(
        lesson_id=lesson_id, student=user, answered_at__isnull=True,
        due_at__lte=now, due_at__gt=now - timedelta(seconds=ATTENTION_WINDOW_SEC),
    ).first()


def answer_attention(*, user: User, check_id) -> AttentionCheck:
    try:
        check = AttentionCheck.objects.get(pk=check_id, student=user)
    except (AttentionCheck.DoesNotExist, ValueError, TypeError):
        raise NotFound('Tekshiruv topilmadi.')
    now = timezone.now()
    deadline = check.due_at + timedelta(seconds=ATTENTION_WINDOW_SEC + ATTENTION_GRACE_SEC)
    if check.answered_at is not None:
        return check
    if now > deadline:
        raise ValidationError('Vaqt tugadi — bu tekshiruv o\'tkazib yuborilgan.')
    check.answered_at = now
    check.save(update_fields=['answered_at'])
    return check


# ── Anti-cheat: fokus jurnali ──────────────────────────────────────────────

def record_focus(*, user: User, lesson_id, kind: str) -> dict:
    """Chiqib-kirishni yozadi. 'exit' bo'lsa shu darsdagi jami chiqishlar soni va
    ogohlantirish darajasini qaytaradi: threshold'gacha — o'quvchining o'ziga
    ogohlantirish, threshold'da (bir marta) — ota-onaga FocusAlert yaratiladi.
    """
    if kind not in FocusEvent.Kind.values:
        raise ValidationError({'kind': 'exit yoki return.'})
    try:
        lesson = Lesson.objects.get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')
    event = FocusEvent.objects.create(lesson=lesson, student=user, kind=kind)

    # O'qituvchiga darhol ko'rinishi kerak (burchakda "diqqat qilmayapti"
    # belgisi) — doska WebSocket kanali orqali (dars davomida hamma shunga
    # ulangan, yangi ulanish ochish shart emas). Xato broadcast qilmasin.
    try:
        from apps.board import realtime as board_realtime
        board_realtime.broadcast_focus(
            lesson_id, student_id=str(user.id),
            name=user.first_name or user.username, kind=kind,
        )
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger('apps').exception('focus broadcast failed')

    if kind != FocusEvent.Kind.EXIT:
        return {'kind': kind, 'exit_count': None, 'threshold': None, 'parent_notified': False}

    exit_count = FocusEvent.objects.filter(
        lesson=lesson, student=user, kind=FocusEvent.Kind.EXIT,
    ).count()
    threshold = settings.FOCUS_PARENT_ALERT_THRESHOLD
    parent_notified = exit_count >= threshold
    if parent_notified:
        # Faqat birinchi chegaradan oshgan safar yaratiladi — spam bo'lmasin
        FocusAlert.objects.get_or_create(
            lesson=lesson, student=user, defaults={'exit_count': exit_count},
        )
    return {
        'kind': event.kind, 'exit_count': exit_count,
        'threshold': threshold, 'parent_notified': parent_notified,
    }


def away_students(lesson: Lesson) -> list[dict]:
    """Hozir darsdan "chiqib ketgan" (oynadan chiqib, hali qaytmagan)
    o'quvchilar — o'qituvchi doskani (qayta) ochganda darhol ko'rishi uchun
    (WebSocket ulanishidan oldingi holatni ham qamrab oladi)."""
    events = (
        FocusEvent.objects.filter(lesson=lesson)
        .select_related('student')
        .order_by('created_at')
    )
    last_kind = {}
    names = {}
    for e in events:
        last_kind[e.student_id] = e.kind
        names[e.student_id] = e.student.first_name or e.student.username
    return [
        {'student_id': str(sid), 'name': names[sid]}
        for sid, kind in last_kind.items() if kind == FocusEvent.Kind.EXIT
    ]


def request_mic(*, user: User, lesson_id, request=None) -> None:
    """O'quvchi mikrofon so'raydi ("qo'l ko'tarish").

    Bazaga ham yoziladi (MicRequest, idempotent — qayta so'rasa dublikat
    yaratilmaydi), NA FAQAT WebSocket orqali yuboriladi — shu sabab
    o'qituvchi so'rovdan keyin kirsa yoki sahifani yangilasa ham,
    `pending_mic_requests()` orqali joriy holat qayta tiklanadi.
    """
    try:
        lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')
    is_enrolled = lesson.course.enrollments.filter(
        student=user, status=Enrollment.Status.APPROVED,
    ).exists()
    if not is_enrolled:
        raise PermissionDenied("Bu darsga kirish huquqingiz yo'q.")

    from apps.lessons.models import MicRequest
    MicRequest.objects.get_or_create(lesson=lesson, student=user)

    try:
        from apps.board import realtime as board_realtime
        board_realtime.broadcast_mic_request(
            lesson_id, student_id=str(user.id),
            name=user.first_name or user.username,
        )
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger('apps').exception('mic_request broadcast failed')

    audit.record(action='room.mic_request', actor=user, target=lesson, request=request)


def pending_mic_requests(lesson: Lesson) -> list[dict]:
    """Hozir javob kutilayotgan mikrofon so'rovlari — o'qituvchi doskani
    (qayta) ochganda darhol ko'rishi uchun (WebSocket ulanishidan oldingi
    yoki undan keyingi holatni ham qamrab oladi)."""
    from apps.lessons.models import MicRequest

    requests = MicRequest.objects.filter(lesson=lesson).select_related('student')
    return [
        {'student_id': str(r.student_id), 'name': r.student.first_name or r.student.username}
        for r in requests
    ]


# ── Ekran share ruxsati (o'qituvchi beradi) ────────────────────────────────

def _livekit_http_url() -> str:
    """Server-server API chaqiriqlari uchun LiveKit manzili.

    LIVEKIT_API_URL berilgan bo'lsa — o'sha (prod: docker tarmog'i ichidan
    http://livekit:7880 — Caddy/TLS orqali aylanib yurmaydi). Bo'lmasa
    LIVEKIT_URL'dan hosil qilinadi (dev).
    """
    api_url = getattr(settings, 'LIVEKIT_API_URL', '')
    if api_url:
        return api_url
    return settings.LIVEKIT_URL.replace('wss://', 'https://').replace('ws://', 'http://')


def grant_screen_share(*, teacher: User, lesson_id, identity: str, request=None) -> bool:
    """O'qituvchi o'quvchiga ekran ulashish ruxsatini jonli ochadi (LiveKit server API)."""
    try:
        lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')
    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi ruxsat beradi.")

    async def _update():
        client = LiveKitAPI(
            url=_livekit_http_url(),
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        try:
            await client.room.update_participant(UpdateParticipantRequest(
                room=lesson.room_name,
                identity=identity,
                permission=ParticipantPermission(
                    can_subscribe=True,
                    can_publish=True,
                    can_publish_data=True,
                    can_publish_sources=[
                        TrackSource.CAMERA,
                        TrackSource.MICROPHONE,
                        TrackSource.SCREEN_SHARE,
                        TrackSource.SCREEN_SHARE_AUDIO,
                    ],
                ),
            ))
        finally:
            await client.aclose()

    asyncio.run(_update())
    audit.record(
        action='room.allow_share', actor=teacher, target=lesson,
        meta={'identity': identity}, request=request,
    )
    return True


def grant_mic(*, teacher: User, lesson_id, student_id, request=None) -> bool:
    """O'qituvchi o'quvchiga mikrofon ruxsatini jonli ochadi (LiveKit server
    API) — kamera va (agar oldin berilgan bo'lsa) ekran ulashish ruxsatini
    saqlab qolib, ustiga mikrofonni qo'shadi."""
    lesson = _get_owned_lesson(teacher=teacher, lesson_id=lesson_id)
    try:
        student = User.objects.get(pk=student_id, role=User.Role.STUDENT)
    except (User.DoesNotExist, ValueError, TypeError):
        raise NotFound("O'quvchi topilmadi.")

    identity = f'user-{student.id}'

    async def _update():
        from livekit.protocol.room import RoomParticipantIdentity

        client = LiveKitAPI(
            url=_livekit_http_url(),
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        try:
            # Joriy ruxsatlarni o'qib, ustiga mikrofonni QO'SHAMIZ — agar
            # oldin ekran ulashish berilgan bo'lsa, uni tasodifan olib
            # tashlab qo'ymaslik uchun (update_participant butun ro'yxatni
            # ALMASHTIRADI, qo'shmaydi).
            info = await client.room.get_participant(RoomParticipantIdentity(
                room=lesson.room_name, identity=identity,
            ))
            sources = set(info.permission.can_publish_sources) | {TrackSource.CAMERA, TrackSource.MICROPHONE}
            await client.room.update_participant(UpdateParticipantRequest(
                room=lesson.room_name,
                identity=identity,
                permission=ParticipantPermission(
                    can_subscribe=True,
                    can_publish=True,
                    can_publish_data=True,
                    can_publish_sources=list(sources),
                ),
            ))
        finally:
            await client.aclose()

    asyncio.run(_update())

    from apps.lessons.models import MicRequest
    MicRequest.objects.filter(lesson=lesson, student=student).delete()

    try:
        from apps.board import realtime as board_realtime
        board_realtime.broadcast_mic_granted(lesson_id, student_id=str(student.id))
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger('apps').exception('mic_granted broadcast failed')

    audit.record(
        action='room.grant_mic', actor=teacher, target=lesson,
        meta={'student_id': str(student.id)}, request=request,
    )
    return True


def deny_mic(*, teacher: User, lesson_id, student_id, request=None) -> bool:
    """O'qituvchi mikrofon so'rovini rad etadi — LiveKit ruxsati BERILMAYDI,
    faqat navbatdagi so'rov o'chiriladi. So'rov hal bo'lgani uchun (o'chirilgani
    uchun) o'quvchi keyin yana so'ray oladi."""
    lesson = _get_owned_lesson(teacher=teacher, lesson_id=lesson_id)
    try:
        student = User.objects.get(pk=student_id, role=User.Role.STUDENT)
    except (User.DoesNotExist, ValueError, TypeError):
        raise NotFound("O'quvchi topilmadi.")

    from apps.lessons.models import MicRequest
    deleted, _ = MicRequest.objects.filter(lesson=lesson, student=student).delete()

    if deleted:
        try:
            from apps.board import realtime as board_realtime
            board_realtime.broadcast_mic_denied(lesson_id, student_id=str(student.id))
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger('apps').exception('mic_denied broadcast failed')

        audit.record(
            action='room.deny_mic', actor=teacher, target=lesson,
            meta={'student_id': str(student.id)}, request=request,
        )
    return bool(deleted)


# ── Taklif va chetlashtirish (Zoom uslubidagi invite/ban) ──────────────────

def _get_owned_lesson(*, teacher: User, lesson_id) -> Lesson:
    try:
        lesson = Lesson.objects.select_related('course').get(pk=lesson_id)
    except (Lesson.DoesNotExist, ValueError, TypeError):
        raise NotFound('Dars topilmadi.')
    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi shu amalni bajara oladi.")
    return lesson


def invite_to_lesson(*, teacher: User, lesson_id, student_id=None, request=None) -> int:
    """O'quvchiga (yoki student_id berilmasa — kursga APPROVED yozilgan
    HAMMAGA) "dars boshlandi, kiring" bildirishnomasini yuboradi.

    Faqat ogohlantirish — o'quvchi xonaga baribir o'zi token so'rab kiradi
    (room.token ruxsati bo'lsa allaqachon kira oladi); bu shunchaki uni
    xabardor qiladi.
    """
    lesson = _get_owned_lesson(teacher=teacher, lesson_id=lesson_id)

    qs = lesson.course.enrollments.filter(status=Enrollment.Status.APPROVED).select_related('student')
    if student_id:
        qs = qs.filter(student_id=student_id)
        if not qs.exists():
            raise NotFound("O'quvchi bu kursga yozilmagan.")
    students = [e.student for e in qs]
    if not students:
        return 0

    from apps.notifications.models import Notification
    from apps.notifications.services import send_notification

    description = f'«{lesson.title}» darsi boshlandi — hoziroq kiring.'
    for student in students:
        send_notification(
            sender=teacher, description=description,
            target_type=Notification.Target.USER, user_id=student.id, request=request,
        )
    audit.record(
        action='lesson.invite', actor=teacher, target=lesson,
        meta={'student_count': len(students)}, request=request,
    )
    return len(students)


def ban_participant(*, teacher: User, lesson_id, student_id, request=None) -> bool:
    """O'quvchini darsdan chetlashtiradi: hozir xonada bo'lsa darhol chiqarib
    yuboradi (LiveKit), va LessonBan yaratib qayta kirishini bloklaydi
    (issue_room_token shu jadvalni tekshiradi). Talaba hozir ulanmagan
    bo'lsa ham — ban baribir saqlanadi, keyingi token so'rovi rad etiladi.
    """
    lesson = _get_owned_lesson(teacher=teacher, lesson_id=lesson_id)
    try:
        student = User.objects.get(pk=student_id, role=User.Role.STUDENT)
    except (User.DoesNotExist, ValueError, TypeError):
        raise NotFound("O'quvchi topilmadi.")

    LessonBan.objects.get_or_create(lesson=lesson, student=student, defaults={'banned_by': teacher})

    async def _remove():
        from livekit.protocol.room import RoomParticipantIdentity

        client = LiveKitAPI(
            url=_livekit_http_url(),
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        try:
            await client.room.remove_participant(RoomParticipantIdentity(
                room=lesson.room_name, identity=f'user-{student.id}',
            ))
        finally:
            await client.aclose()

    try:
        asyncio.run(_remove())
    except Exception:  # noqa: BLE001 — talaba hozir xonada bo'lmasligi mumkin, ban baribir saqlandi
        import logging
        logging.getLogger('apps').info('ban_participant: xonadan chiqarib bo\'lmadi (ulanmagan bo\'lishi mumkin)')

    audit.record(
        action='room.ban', actor=teacher, target=lesson,
        meta={'student_id': str(student.id)}, request=request,
    )
    return True


def unban_participant(*, teacher: User, lesson_id, student_id, request=None) -> bool:
    """Chetlashtirishni bekor qiladi — o'quvchi qayta token so'rab kira oladi."""
    lesson = _get_owned_lesson(teacher=teacher, lesson_id=lesson_id)
    deleted, _ = LessonBan.objects.filter(lesson=lesson, student_id=student_id).delete()
    if deleted:
        audit.record(
            action='room.unban', actor=teacher, target=lesson,
            meta={'student_id': str(student_id)}, request=request,
        )
    return bool(deleted)


# ── Dars video yozuvi (LiveKit Track Egress + brauzerdan audio) ────────────
# EduTech.docx: "dars video zapisi avtomatik saqlansin — o'qituvchi guruhni
# o'chirmaguncha". Ikki qismdan yig'iladi (CPU tejash uchun — RoomComposite
# o'rniga, 2026-08-27 optimallashtirish):
#   VIDEO — Track Egress o'qituvchi kamerasini XOM nusxa ko'chiradi (Chrome
#     render/qayta kodlash yo'q, ~0.15-0.2 CPU).
#   AUDIO — o'qituvchi brauzeri BARCHA ishtirokchilar ovozini ichkarida
#     (Web Audio API) aralashtirib, bo'lak-bo'lak (chunk) yuklaydi (server
#     CPU'si deyarli 0 — faqat diskka yozish). Ko'proq ishonchlilik uchun:
#     brauzer har bo'lak serverga tushgach, o'z xotirasidan o'chiradi.
# Ikkalasi ham tayyor bo'lgach, fon jarayonida `ffmpeg`da (qayta kodlashsiz,
# faqat audio->AAC) vaqt farqiga moslab birlashtiriladi. Fayl recordings
# volume'ida; faqat auth endpoint orqali beriladi (apps/lessons).

def _friendly_egress_error(exc) -> str:
    """Xom SDK xatosini foydalanuvchi tushunadigan o'zbekcha matnga aylantiradi
    (frontend `error` maydonini to'g'ridan-to'g'ri ko'rsatadi)."""
    raw = str(exc)
    if 'does not exist' in raw:
        return "Yozuv boshlanmadi: darsga hech kim ulanmadi (xona ochilmadi)."
    if 'status=401' in raw or 'unauthenticated' in raw.lower():
        return 'Yozuv xizmati avtorizatsiyadan o\'tmadi — server sozlamalarini tekshiring.'
    if 'Start signal' in raw:
        return "Yozuv bekor qilindi: xonada video/audio bo'lmadi."
    if 'resource' in raw.lower() or 'exhausted' in raw.lower():
        return "Yozuv xizmati band — birozdan so'ng darsga qayta kiring."
    return f'Yozuvda texnik xato: {raw[:200]}'


def start_recording(*, lesson: Lesson) -> None:
    """Dars yozuvini KAFOLATLAYDI (idempotent) — o'qituvchi darsga har kirganda
    chaqiriladi:

      - xonada allaqachon aktiv egress bo'lsa — o'shani o'zlashtiradi (backend
        restart / qayta kirish holatlari);
      - bo'lmasa yangisini boshlaydi (xona ochilguncha 2 daqiqagacha kutadi);
      - avvalgi urinish FAILED/abort bo'lgan bo'lsa ham qayta uriniladi.

    Xatolar dars oqimini hech qachon buzmaydi (fon thread).
    """
    import logging
    import threading

    from apps.lessons.models import LessonRecording

    if not getattr(settings, 'RECORDINGS_AUTO_START', True):
        return  # testlarda o'chirilgan (fon thread + tarmoq kerak emas)

    recording, _created = LessonRecording.objects.get_or_create(lesson=lesson)
    teacher_identity = f'user-{lesson.course.teacher_id}'

    def _target():
        import time as _time
        import uuid as _uuid

        from django.db import close_old_connections

        try:
            # 1) Xonada aktiv egress bormi? Bor bo'lsa — o'zlashtiramiz.
            try:
                active = asyncio.run(_egress_active(lesson.room_name))
            except Exception:  # noqa: BLE001 — ro'yxat olinmasa, yangi boshlaymiz
                active = None
            if active:
                LessonRecording.objects.filter(pk=recording.pk).update(
                    egress_id=active, status=LessonRecording.Status.RECORDING, error='',
                    video_started_at=recording.video_started_at or timezone.now(),
                )
                return

            # 2) Yangi egress. Fayl nomi har urinishda unikal — avvalgi
            #    abort qoldig'i ustiga yozilmaydi.
            file_name = f'{lesson.room_name}-{_uuid.uuid4().hex[:6]}.mp4'
            LessonRecording.objects.filter(pk=recording.pk).update(
                status=LessonRecording.Status.PENDING,
            )

            # Token berilgan payt o'qituvchi brauzeri hali xonaga ULANMAGAN
            # (yoki kamerasi hali publish qilinmagan) bo'lishi mumkin —
            # "does not exist"da 2 daqiqagacha kutamiz.
            last_error = None
            for _attempt in range(24):
                try:
                    egress_id = asyncio.run(_egress_start(lesson.room_name, file_name, teacher_identity))
                    LessonRecording.objects.filter(pk=recording.pk).update(
                        egress_id=egress_id, video_file_name=file_name,
                        video_started_at=timezone.now(),
                        status=LessonRecording.Status.RECORDING, error='',
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if 'does not exist' not in str(exc):
                        break  # boshqa xato — kutish foyda bermaydi
                    _time.sleep(5)
            logging.getLogger('apps').warning('egress start failed: %s', last_error)
            LessonRecording.objects.filter(pk=recording.pk).update(
                status=LessonRecording.Status.FAILED,
                error=_friendly_egress_error(last_error),
            )
        finally:
            close_old_connections()

    threading.Thread(target=_target, daemon=True).start()


async def _egress_active(room_name: str) -> str | None:
    """Xonadagi aktiv (tugamagan) egress ID sini qaytaradi, bo'lmasa None."""
    from livekit.protocol.egress import ListEgressRequest

    client = LiveKitAPI(
        url=_livekit_http_url(),
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    try:
        result = await client.egress.list_egress(ListEgressRequest(
            room_name=room_name, active=True,
        ))
        items = list(result.items)
        return items[0].egress_id if items else None
    finally:
        await client.aclose()


async def _egress_start(room_name: str, file_name: str, teacher_identity: str) -> str:
    """O'qituvchining kamera trackini XOM nusxa ko'chiradi (qayta kodlashsiz —
    Chrome render yo'q, CPU narxi RoomComposite'ga nisbatan ~7-10x arzon).
    Audio endi bu yerda yo'q — brauzerdan alohida yuklanadi (yuqoridagi izoh)."""
    from livekit.protocol.egress import DirectFileOutput, TrackEgressRequest
    from livekit.protocol.models import TrackType
    from livekit.protocol.room import ListParticipantsRequest

    client = LiveKitAPI(
        url=_livekit_http_url(),
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    try:
        result = await client.room.list_participants(ListParticipantsRequest(room=room_name))
        track_id = None
        for p in result.participants:
            if p.identity != teacher_identity:
                continue
            for t in p.tracks:
                if t.type == TrackType.VIDEO and t.source == TrackSource.CAMERA:
                    track_id = t.sid
        if not track_id:
            # start_recording'dagi kutish tsikli aynan shu matnni kutadi
            raise RuntimeError('room does not exist — teacher camera track not published yet')
        info = await client.egress.start_track_egress(TrackEgressRequest(
            room_name=room_name, track_id=track_id,
            file=DirectFileOutput(filepath=f'{settings.EGRESS_OUTPUT_PREFIX}/{file_name}'),
        ))
        return info.egress_id
    finally:
        await client.aclose()


def _resolve_video_file(recording) -> str | None:
    """LiveKit Track Egress biz so'ragan kengaytmani (masalan `.mp4`)
    e'tiborsiz qoldirib, trackning HAQIQIY kodekiga mos konteynerda
    (masalan VP8 uchun `.webm`) yozishi mumkin — bu hujjatlashtirilmagan,
    lekin kuzatilgan xatti-harakat (2026-08-28: production'da topilgan
    xato — bazada `.mp4` yozilgan, diskda `.webm` fayl bor edi, shu sabab
    yozuv "recording" holatida abadiy qolib qolgan). Shuning uchun
    kengaytmaga ishonmasdan, diskdan bir xil BAZA nomli faylni qidiramiz."""
    if not recording.video_file_name:
        return None
    path = settings.RECORDINGS_DIR / recording.video_file_name
    if path.exists():
        return recording.video_file_name
    base = recording.video_file_name.rsplit('.', 1)[0]
    matches = sorted(settings.RECORDINGS_DIR.glob(f'{base}.*'))
    return matches[0].name if len(matches) == 1 else None


def stop_recording(*, lesson: Lesson) -> None:
    """Darsni yakunlashda video egress'ni to'xtatadi (best-effort — xona
    bo'shasa egress baribir o'zi yakunlaydi), so'ng audio ham tayyor bo'lsa
    birlashtirishni ishga tushiradi."""
    import logging

    from apps.lessons.models import LessonRecording

    recording = LessonRecording.objects.filter(lesson=lesson).first()
    if recording is None or not recording.egress_id:
        return

    async def _stop():
        from livekit.protocol.egress import StopEgressRequest

        client = LiveKitAPI(
            url=_livekit_http_url(),
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        try:
            await client.egress.stop_egress(StopEgressRequest(egress_id=recording.egress_id))
        finally:
            await client.aclose()

    try:
        asyncio.run(_stop())
    except Exception as exc:  # allaqachon tugagan bo'lishi mumkin
        logging.getLogger('apps').info('egress stop: %s', exc)
    resolved = _resolve_video_file(recording)
    if resolved:
        recording.video_file_name = resolved
    recording.ended_at = timezone.now()
    recording.video_ready_at = timezone.now()
    recording.save(update_fields=['ended_at', 'video_ready_at', 'video_file_name', 'updated_at'])
    maybe_start_merge(lesson.id)


def end_room(lesson: Lesson) -> None:
    """LiveKit xonasini BUTUNLAY o'chiradi — barcha ishtirokchilarni (video/
    audio) bir vaqtda uzadi. Dars rejalashtirilgan vaqti tugab, avtomatik
    yakunlanganda ishlatiladi (apps.lessons.services.auto_finish_expired_lessons) —
    o'qituvchi qo'lda "tugatish"ni bosmagan bo'lsa ham, video cheksiz
    ochiq qolib ketmasin. Xona allaqachon bo'sh/yo'q bo'lsa ham xato
    bermaydi (best-effort, xuddi stop_recording kabi)."""
    import logging

    async def _delete():
        from livekit.protocol.room import DeleteRoomRequest

        client = LiveKitAPI(
            url=_livekit_http_url(),
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        try:
            await client.room.delete_room(DeleteRoomRequest(room=lesson.room_name))
        finally:
            await client.aclose()

    try:
        asyncio.run(_delete())
    except Exception as exc:  # noqa: BLE001 — xona allaqachon yo'q bo'lishi mumkin
        logging.getLogger('apps').info('end_room: %s', exc)


def maybe_start_merge(lesson_id) -> None:
    """Video (Track Egress) va audio (brauzerdan yuklangan) ikkalasi ham
    tayyor bo'lsa — fon jarayonida (thread) ffmpeg bilan birlashtiradi.
    Ikkala tomondan ham (stop_recording va audio finalize) chaqiriladi;
    DB-level atomik status o'tishi (RECORDING -> MERGING) ikki marta ishga
    tushishining oldini oladi."""
    import threading

    from apps.lessons.models import LessonRecording

    recording = LessonRecording.objects.filter(lesson_id=lesson_id).first()
    if recording is None:
        return
    if not (recording.video_ready_at and recording.audio_finalized_at):
        return
    if not (recording.video_file_name and recording.audio_file_name):
        return
    updated = LessonRecording.objects.filter(
        pk=recording.pk, status=LessonRecording.Status.RECORDING,
    ).update(status=LessonRecording.Status.MERGING)
    if not updated:
        return  # allaqachon merge boshlangan/tugagan
    threading.Thread(target=_merge_recording, args=(recording.pk,), daemon=True).start()


def finalize_video_only(lesson_id) -> None:
    """Audio (brauzerdan) hech qachon kelmasa (masalan o'qituvchi brauzeri
    yopilib qolgan) — video yozuvni OVOZSIZ, lekin YO'QOTMASDAN yakunlaydi.
    `maybe_start_merge`ga o'xshab, atomik DB guard ikki marta ishlashning
    oldini oladi. Chaqiruvchi (`apps.lessons.services.recording_info`)
    kutish vaqtini (video_ready_at'dan necha daqiqa) o'zi hisoblaydi."""
    import logging

    from apps.lessons.models import LessonRecording

    recording = LessonRecording.objects.filter(lesson_id=lesson_id).first()
    if recording is None or not recording.video_file_name:
        return
    resolved = _resolve_video_file(recording)
    if not resolved:
        return
    updated = LessonRecording.objects.filter(
        pk=recording.pk, status=LessonRecording.Status.RECORDING,
    ).update(
        file_name=resolved, video_file_name=resolved,
        status=LessonRecording.Status.COMPLETED,
    )
    if updated:
        logging.getLogger('apps').info('recording %s finalized video-only (no audio)', recording.pk)


def _merge_recording(recording_pk) -> None:
    """Video+audio fayllarini vaqt farqiga moslab (`-itsoffset`) bitta faylga
    birlashtiradi. Video qayta kodlanmaydi (`-c copy`), faqat audio AAC'ga
    o'tkaziladi (MP4 konteyner mosligi uchun — bu arzon, video kabi og'ir
    emas).

    `-fflags +genpts` audio kirishida SHART — brauzer audio faylini
    bo'lak-bo'lak (bir nechta alohida MediaRecorder seansi) yozib
    yuborganda, har seans o'z vaqtini noldan boshlashi mumkin va bu
    ulanish nuqtalarida vaqt belgisi orqaga qaytib qoladi (production'da
    2026-08-28: "non monotonically increasing dts" bilan `-c:a aac`
    QATTIQ xato berib, chiqish fayli umuman yaratilmagan edi — `+genpts`
    buni silliq tuzatib, faylni saqlab qoladi)."""
    import logging
    import subprocess
    import uuid as _uuid

    from django.db import close_old_connections

    from apps.lessons.models import LessonRecording

    try:
        recording = LessonRecording.objects.select_related('lesson').get(pk=recording_pk)
        video_path = settings.RECORDINGS_DIR / (_resolve_video_file(recording) or recording.video_file_name)
        audio_path = settings.RECORDINGS_DIR / recording.audio_file_name
        output_name = f'{recording.lesson.room_name}-{_uuid.uuid4().hex[:6]}-final.mp4'
        output_path = settings.RECORDINGS_DIR / output_name

        if recording.video_started_at and recording.audio_started_at:
            delta = (recording.video_started_at - recording.audio_started_at).total_seconds()
        else:
            delta = 0.0
        video_offset = max(delta, 0.0)
        audio_offset = max(-delta, 0.0)

        cmd = [
            'ffmpeg', '-y',
            '-itsoffset', f'{video_offset:.3f}', '-i', str(video_path),
            '-fflags', '+genpts',
            '-itsoffset', f'{audio_offset:.3f}', '-i', str(audio_path),
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy', '-c:a', 'aac',
            '-shortest', str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not output_path.exists():
            LessonRecording.objects.filter(pk=recording_pk).update(
                status=LessonRecording.Status.FAILED,
                error=f'Birlashtirish xatosi: {result.stderr[-500:]}',
            )
            return
        LessonRecording.objects.filter(pk=recording_pk).update(
            file_name=output_name, status=LessonRecording.Status.COMPLETED,
        )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger('apps').exception('recording merge failed: %s', exc)
        LessonRecording.objects.filter(pk=recording_pk).update(
            status=LessonRecording.Status.FAILED, error=str(exc)[:500],
        )
    finally:
        close_old_connections()
