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

    # O'quvchi default ekran share qila olmaydi — o'qituvchi ruxsat berganda
    # grant_screen_share() orqali jonli ochiladi (EduTech.docx).
    publish_sources = None if is_teacher else ['camera', 'microphone']
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


# ── Dars video yozuvi (LiveKit Egress) ─────────────────────────────────────
# EduTech.docx: "dars video zapisi avtomatik saqlansin — o'qituvchi guruhni
# o'chirmaguncha". Dars LIVE bo'lganda yozish boshlanadi, dars tugaganda
# (yoki xona bo'shaganda egress o'zi) yakunlanadi. Fayl recordings
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
                )
                return

            # 2) Yangi egress. Fayl nomi har urinishda unikal — avvalgi
            #    abort qoldig'i ustiga yozilmaydi.
            file_name = f'{lesson.room_name}-{_uuid.uuid4().hex[:6]}.mp4'
            LessonRecording.objects.filter(pk=recording.pk).update(
                status=LessonRecording.Status.PENDING,
            )

            # Token berilgan payt o'qituvchi brauzeri hali xonaga ULANMAGAN
            # bo'lishi mumkin — "room does not exist"da 2 daqiqagacha kutamiz.
            last_error = None
            for _attempt in range(24):
                try:
                    egress_id = asyncio.run(_egress_start(lesson.room_name, file_name))
                    LessonRecording.objects.filter(pk=recording.pk).update(
                        egress_id=egress_id, file_name=file_name,
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


async def _egress_start(room_name: str, file_name: str) -> str:
    from livekit.protocol.egress import (
        EncodedFileOutput,
        EncodingOptions,
        RoomCompositeEgressRequest,
    )

    client = LiveKitAPI(
        url=_livekit_http_url(),
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    try:
        info = await client.egress.start_room_composite_egress(RoomCompositeEgressRequest(
            room_name=room_name,
            layout='speaker',
            audio_only=False,
            # 480p/15 — LiveKit'ning EncodingOptionsPreset ro'yxatida 480p
            # umuman yo'q (faqat 720p/1080p bor, tekshirilgan: livekit-protocol
            # 1.1.22, eng oxirgi versiya) — shuning uchun tayyor preset o'rniga
            # o'zimiz `advanced` (custom EncodingOptions) bilan belgilaymiz.
            # 720p30'ga nisbatan piksel/soniya hajmi ~5.7x kam
            # (1280x720x30 -> 854x480x15), kompozitor+kodlash yuki shunga
            # yaqin nisbatda tushishi kutiladi — CHIN qiymatni real yozuv
            # bilan `docker stats egress`da tekshirish shart (pastda eslatma).
            advanced=EncodingOptions(
                width=854, height=480, framerate=15,
                video_bitrate=900, audio_bitrate=64, audio_frequency=44100,
            ),
            file_outputs=[EncodedFileOutput(
                filepath=f'{settings.EGRESS_OUTPUT_PREFIX}/{file_name}',
            )],
        ))
        return info.egress_id
    finally:
        await client.aclose()


def stop_recording(*, lesson: Lesson) -> None:
    """Darsni yakunlashda egress'ni to'xtatadi (best-effort — xona bo'shasa
    egress baribir o'zi yakunlaydi)."""
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
    recording.ended_at = timezone.now()
    recording.save(update_fields=['ended_at', 'updated_at'])


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
