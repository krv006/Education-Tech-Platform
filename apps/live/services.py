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


# ── Dars video yozuvi (brauzerdan video + audio, chunked upload) ───────────
# EduTech.docx: "dars video zapisi avtomatik saqlansin — o'qituvchi guruhni
# o'chirmaguncha". 2026-08-28 optimallashtirish, 2-bosqich: video ENDI HAM
# server-tomon Track Egress orqali EMAS — audio kabi TO'LIQ o'qituvchi
# brauzeridan keladi. Sabab: Track Egress FAQAT bitta trackni (kamera YOKI
# ekran) yoza olardi, dars davomida almashtirishni qo'llab-quvvatlamas edi.
# Brauzerning o'zi ekranini (`getDisplayMedia` — LiveKit sahifasining o'zi,
# "print screen" kabi) yozib olsa — kim gapirsa, kim ekran ulashsa, kim
# kamerasini yoqsa — HAMMASI tabiiy ravishda ko'rinadi, serverda tanlov/
# almashtirish mantig'i kerak emas, va CPU endi VIDEO uchun HAM deyarli 0.
#
# Video va audio ikkalasi ham bo'lak-bo'lak (chunk) yuklanadi (apps.lessons
# .services.upload_recording_video_chunk/upload_recording_audio_chunk).
# Ikkalasi ham tayyor bo'lgach, fon jarayonida `ffmpeg`da vaqt farqiga
# moslab (qayta kodlashsiz) WebM faylga birlashtiriladi. Faqat BITTASI
# kelsa (ikkinchisi hech qachon kelmasa — brauzer qulab qolgan, ruxsat
# berilmagan) — MAVJUD bo'lgani bilan yakunlanadi, butunlay yo'qotilmaydi.

def end_room(lesson: Lesson) -> None:
    """LiveKit xonasini BUTUNLAY o'chiradi — barcha ishtirokchilarni (video/
    audio) bir vaqtda uzadi. Dars rejalashtirilgan vaqti tugab, avtomatik
    yakunlanganda ishlatiladi (apps.lessons.services.auto_finish_expired_lessons) —
    o'qituvchi qo'lda "tugatish"ni bosmagan bo'lsa ham, xona cheksiz ochiq
    qolib ketmasin. Xona allaqachon bo'sh/yo'q bo'lsa ham xato bermaydi
    (best-effort)."""
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
    """Video va audio (ikkalasi ham brauzerdan yuklangan) tayyor bo'lsa —
    fon jarayonida (thread) ffmpeg bilan birlashtiradi. Ikkala tomondan
    ham (video finalize va audio finalize) chaqiriladi; DB-level atomik
    status o'tishi (RECORDING -> MERGING) ikki marta ishga tushishining
    oldini oladi."""
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


def finalize_single_side(lesson_id) -> None:
    """Video YOKI audiodan faqat BITTASI keladi, ikkinchisi HECH QACHON
    kelmaydi (brauzer qulab qolgan, ruxsat berilmagan va h.k.) — mavjud
    bo'lgan tomon bilan yakunlaydi, butunlay yo'qotmaydi. Ikkala
    yo'nalish uchun ham ishlaydi (faqat video, yoki faqat audio).
    `maybe_start_merge`ga o'xshab, atomik DB guard ikki marta ishlashning
    oldini oladi. Chaqiruvchi (`apps.lessons.services.recording_info`)
    qancha kutish kerakligini o'zi hisoblaydi."""
    import logging

    from apps.lessons.models import LessonRecording

    recording = LessonRecording.objects.filter(lesson_id=lesson_id).first()
    if recording is None:
        return
    if recording.video_file_name and not recording.audio_file_name:
        source, label = recording.video_file_name, "video-only (audio yo'q)"
    elif recording.audio_file_name and not recording.video_file_name:
        source, label = recording.audio_file_name, "audio-only (video yo'q)"
    else:
        return
    path = settings.RECORDINGS_DIR / source
    if not path.exists():
        return
    updated = LessonRecording.objects.filter(
        pk=recording.pk, status=LessonRecording.Status.RECORDING,
    ).update(file_name=source, status=LessonRecording.Status.COMPLETED)
    if updated:
        logging.getLogger('apps').info('recording %s finalized %s', recording.pk, label)
        recording.refresh_from_db()
        _announce_recording_ready(recording)


def _merge_recording(recording_pk) -> None:
    """Video+audio fayllarini vaqt farqiga moslab (`-itsoffset`) bitta
    WebM faylga birlashtiradi. Ikkalasi ham qayta kodlanmaydi (`-c copy`)
    — brauzer kamerasi VP8/VP9, mikrofon-mix esa Opus kodlaydi, ikkalasi
    ham WebM konteynerida TABIIY qo'llab-quvvatlanadi (production'da
    topilgan xato: MP4 konteynerga VP8'ni yozib bo'lmaydi — "codec not
    currently supported in container", chiqish fayli umuman
    yaratilmagan edi).

    `-fflags +genpts` audio kirishida qo'shimcha himoya — brauzer audio
    faylini bo'lak-bo'lak (bir nechta alohida MediaRecorder seansi) yozib
    yuborganda, har seans o'z vaqtini noldan boshlashi mumkin va bu
    ulanish nuqtalarida vaqt belgisi orqaga qaytib qoladi; bu bayroq
    buni silliqlab, muxer ogohlantirish bilan davom etishini ta'minlaydi."""
    import logging
    import subprocess
    import uuid as _uuid

    from django.db import close_old_connections

    from apps.lessons.models import LessonRecording

    try:
        recording = LessonRecording.objects.select_related('lesson').get(pk=recording_pk)
        video_path = settings.RECORDINGS_DIR / recording.video_file_name
        audio_path = settings.RECORDINGS_DIR / recording.audio_file_name
        # .webm, .mp4 EMAS — brauzer kamerasi VP8 (yoki VP9) kodlaydi, va
        # VP8/VP9 MP4 konteynerida UMUMAN qo'llab-quvvatlanmaydi
        # (production'da topilgan xato: "Could not find tag for codec vp8
        # in stream, codec not currently supported in container" — chiqish
        # fayli butunlay yaratilmay qolgan edi). WebM VP8/VP9 + Opus'ni
        # ikkalasini ham TABIIY qo'llab-quvvatlaydi — audio uchun ham AAC'ga
        # aylantirish endi shart emas, to'g'ridan-to'g'ri nusxalanadi.
        output_name = f'{recording.lesson.room_name}-{_uuid.uuid4().hex[:6]}-final.webm'
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
            '-c:v', 'copy', '-c:a', 'copy',
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
        recording.refresh_from_db()
        _announce_recording_ready(recording)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger('apps').exception('recording merge failed: %s', exc)
        LessonRecording.objects.filter(pk=recording_pk).update(
            status=LessonRecording.Status.FAILED, error=str(exc)[:500],
        )
    finally:
        close_old_connections()


def _announce_recording_ready(recording) -> None:
    """Yozuv (video+audio birlashgan, yoki faqat bittasi) tayyor bo'lganda
    guruh chatga e'lon qiladi. Bu — endi `finish_lesson` ichida EMAS,
    chunki brauzer video/audio yuklashni finish tugmasi bosilgandan KEYIN
    ham davom ettirishi mumkin (chunked upload asinxron); e'lon faqat
    fayl HAQIQATAN tayyor bo'lganda yuboriladi."""
    import logging

    try:
        from apps.lessons.services import publish_recording_message
        title = recording.title or recording.lesson.title
        publish_recording_message(recording.lesson, title)
    except Exception:  # noqa: BLE001
        logging.getLogger('apps').exception('recording announce failed')
