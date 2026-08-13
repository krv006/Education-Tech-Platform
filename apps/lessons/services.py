"""Lessons service layer — kurs/dars/yozilish bo'yicha yozuvchi biznes-logika."""
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts import selectors as account_selectors
from apps.accounts.models import User
from apps.core import audit

from .models import Attendance, Course, Enrollment, Lesson


@transaction.atomic
def create_course(*, teacher: User, request=None, **data) -> Course:
    course = Course.objects.create(teacher=teacher, **data)
    # Har kurs = bitta guruh chat (EduTech.docx) — kurs bilan birga ochiladi
    from apps.chat import services as chat_services
    chat_services.ensure_course_room(course)
    audit.record(action='course.create', actor=teacher, target=course, request=request)
    return course


@transaction.atomic
def schedule_lesson(*, teacher: User, course: Course, request=None, **data) -> Lesson:
    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs egasi dars qo'sha oladi.")
    lesson = Lesson.objects.create(course=course, **data)
    audit.record(action='lesson.schedule', actor=teacher, target=lesson, request=request)
    return lesson


@transaction.atomic
def schedule_recurring(*, teacher: User, course: Course, title: str, days: list[int],
                       start_time, end_time, weeks: int, start_date, note: str = '',
                       request=None) -> list[Lesson]:
    """Haftalik jadval asosida ko'plab darslarni bir yo'la yaratadi.

    O'qituvchining BOSHQA kurslari bilan ham (masalan ingliz tili + matematika)
    vaqt ustma-ust tushmasligini tekshiradi — course__teacher bo'yicha, faqat
    joriy kurs emas.
    """
    from datetime import datetime, timedelta

    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs egasi dars qo'sha oladi.")

    duration_min = int(
        (datetime.combine(start_date, end_time) - datetime.combine(start_date, start_time)).total_seconds() // 60,
    )

    now = timezone.now()
    week_start = start_date - timedelta(days=start_date.weekday())
    slots = []
    for week in range(weeks):
        for day in sorted(set(days)):
            lesson_date = week_start + timedelta(weeks=week, days=day)
            if lesson_date < start_date:
                continue
            slot = timezone.make_aware(datetime.combine(lesson_date, start_time))
            if slot < now:  # bugungi kun uchun soat allaqachon o'tib ketgan bo'lishi mumkin
                continue
            slots.append(slot)

    if not slots:
        raise ValidationError("Berilgan parametrlar bo'yicha hech qanday dars yaratilmaydi.")

    existing = list(Lesson.objects.filter(
        course__teacher=teacher,
        status__in=[Lesson.Status.SCHEDULED, Lesson.Status.LIVE],
        starts_at__range=(slots[0] - timedelta(hours=24), slots[-1] + timedelta(minutes=duration_min)),
    ).values('title', 'starts_at', 'duration_min'))

    conflicts = []
    for new_start in slots:
        new_end = new_start + timedelta(minutes=duration_min)
        for ex in existing:
            ex_end = ex['starts_at'] + timedelta(minutes=ex['duration_min'])
            if ex['starts_at'] < new_end and ex_end > new_start:
                conflicts.append({
                    'date': new_start.strftime('%Y-%m-%d'),
                    'time': f"{new_start.strftime('%H:%M')}-{new_end.strftime('%H:%M')}",
                    'existing': ex['title'],
                })
                break

    if conflicts:
        raise ValidationError({'conflicts': conflicts})

    lessons = Lesson.objects.bulk_create([
        Lesson(
            course=course, title=title, starts_at=s, duration_min=duration_min,
            room_name=f'lesson-{uuid.uuid4().hex[:12]}',
        )
        for s in slots
    ])
    audit.record(
        action='lesson.schedule_recurring', actor=teacher, target=course,
        meta={'count': len(lessons), 'weeks': weeks, 'days': days, 'note': note},
        request=request,
    )
    return lessons


def _get_course(course_id) -> Course:
    try:
        return Course.objects.get(pk=course_id, is_active=True)
    except (Course.DoesNotExist, ValueError):
        raise NotFound('Kurs topilmadi.')


def _resolve_student_ref(student_ref: str) -> User:
    """O'quvchini login yoki taklif kodi bo'yicha topadi (o'qituvchi biriktirishi uchun)."""
    student = User.objects.filter(role=User.Role.STUDENT, username=student_ref).first()
    if student is None:
        student = User.objects.filter(role=User.Role.STUDENT, invite_code=student_ref.upper()).first()
    if student is None:
        raise NotFound("Bunday login yoki taklif kodli o'quvchi topilmadi.")
    return student


def _resolve_enroll_target(*, course: Course, by_user: User, student_id=None, student_ref=None) -> User:
    """Kimni yozish/chiqarish mumkinligini aniqlaydi — enroll va unenroll uchun bitta qoida."""
    if by_user.role == User.Role.STUDENT:
        return by_user
    if by_user.role == User.Role.PARENT:
        if not student_id or not account_selectors.is_linked(by_user, student_id):
            raise PermissionDenied("Bu o'quvchi sizga bog'lanmagan.")
        return User.objects.get(pk=student_id)
    if by_user.role == User.Role.TEACHER:
        if course.teacher_id != by_user.id:
            raise PermissionDenied("Faqat o'z kursingizga o'quvchi biriktira olasiz.")
        if student_id:
            try:
                return User.objects.get(pk=student_id, role=User.Role.STUDENT)
            except (User.DoesNotExist, ValueError):
                raise NotFound("O'quvchi topilmadi.")
        if not student_ref:
            raise NotFound("O'quvchi login yoki taklif kodini kiriting.")
        return _resolve_student_ref(student_ref)
    raise PermissionDenied("Faqat o'quvchi, ota-ona yoki kurs o'qituvchisi yoza oladi.")


@transaction.atomic
def enroll(*, course_id, by_user: User, student_id=None, student_ref=None, request=None) -> tuple[Enrollment, bool]:
    """O'quvchi/ota-ona yozilish SO'ROVI yuboradi (pending), o'qituvchi o'z kursiga
    biriktirsa darhol tasdiqlanadi. O'quvchi darsga faqat APPROVED bo'lgach kiradi."""
    course = _get_course(course_id)
    student = _resolve_enroll_target(
        course=course, by_user=by_user, student_id=student_id, student_ref=student_ref,
    )
    target_status = (
        Enrollment.Status.APPROVED if by_user.role == User.Role.TEACHER
        else Enrollment.Status.PENDING
    )
    enrollment, created = Enrollment.objects.get_or_create(
        course=course, student=student, defaults={'status': target_status},
    )
    if not created and enrollment.status != Enrollment.Status.APPROVED and enrollment.status != target_status:
        # rad etilgan so'rov qayta yuborilsa yana pending; o'qituvchi biriktirsa approved
        enrollment.status = target_status
        enrollment.save(update_fields=['status'])
    if created:
        audit.record(
            action='course.enroll', actor=by_user, target=course,
            meta={'student_id': str(student.id), 'status': enrollment.status}, request=request,
        )
    return enrollment, created


@transaction.atomic
def respond_enrollment(*, teacher: User, enrollment_id, action: str, request=None) -> Enrollment:
    """O'qituvchi yozilish so'rovini tasdiqlaydi yoki rad etadi."""
    try:
        enrollment = Enrollment.objects.select_related('course').get(pk=enrollment_id)
    except (Enrollment.DoesNotExist, ValueError):
        raise NotFound("So'rov topilmadi.")
    if enrollment.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs o'qituvchisi so'rovga javob beradi.")
    if action not in ('approve', 'decline'):
        raise NotFound("Amal noto'g'ri: approve yoki decline.")
    enrollment.status = (
        Enrollment.Status.APPROVED if action == 'approve' else Enrollment.Status.DECLINED
    )
    enrollment.save(update_fields=['status'])
    audit.record(
        action=f'course.enroll_{action}', actor=teacher, target=enrollment.course,
        meta={'student_id': str(enrollment.student_id)}, request=request,
    )
    return enrollment


@transaction.atomic
def unenroll(*, course_id, by_user: User, student_id=None, request=None) -> bool:
    """Yozuvni bekor qilish — o'quvchi o'zini, ota-ona bolasini, o'qituvchi o'z kursidan chiqaradi."""
    course = _get_course(course_id)
    student = _resolve_enroll_target(course=course, by_user=by_user, student_id=student_id)
    deleted, _ = Enrollment.objects.filter(course=course, student=student).delete()
    if deleted:
        audit.record(
            action='course.unenroll', actor=by_user, target=course,
            meta={'student_id': str(student.id)}, request=request,
        )
        # Guruh chatidagi ALLAQACHON ochiq WebSocket ulanishi bo'lsa — o'zini
        # yopsin (ruxsat faqat yangi so'rovda tekshiriladi, ochiq soket buni
        # bilmaydi). Xato bo'lsa ham unenroll o'zi muvaffaqiyatli qolaveradi.
        try:
            from apps.chat import realtime as chat_realtime
            chat_realtime.broadcast_member_removed(course.id, student.id)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger('apps').exception('member_removed broadcast failed')
    return bool(deleted)


@transaction.atomic
def delete_course(*, teacher: User, course: Course, request=None) -> None:
    """Guruhni (kursni) o'chiradi — barcha a'zolar chiqib ketadi, chat/doska/video
    ma'lumotlari BUTUNLAY o'chadi (fayllar diskdan ham). Davomat va baholar tarix
    sifatida saqlanadi — shu sabab Kurs/Dars o'zi faqat soft-delete qilinadi
    (Attendance/LessonRating shularga CASCADE FK bilan bog'langan)."""
    if course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat kurs egasi guruhni o'chira oladi.")

    lessons = list(course.lessons.all())
    lesson_ids = [lesson.id for lesson in lessons]

    # Jonli darslar bo'lsa — yozuvni/xonani to'xtatishga urinamiz (best-effort,
    # LiveKit muammosi o'chirishni to'xtatmasin)
    from apps.live import services as live_services
    for lesson in lessons:
        if lesson.status == Lesson.Status.LIVE:
            try:
                live_services.stop_recording(lesson=lesson)
                live_services.end_room(lesson=lesson)
            except Exception:  # noqa: BLE001
                import logging
                logging.getLogger('apps').exception('course delete: live room stop failed')

    # Video yozuvlar — fayl + baza yozuvi butunlay o'chadi
    from .models import LessonRecording
    for recording in LessonRecording.objects.filter(lesson_id__in=lesson_ids):
        if recording.file_name:
            path = _recording_path(recording)
            if path.exists():
                path.unlink()
        recording.delete()

    # Doska — chizmalar, chizish ruxsatlari, o'chirish jurnali + PDF fayllar
    from pathlib import Path

    from django.conf import settings as dj_settings

    from apps.board.models import BoardErase, BoardGrant, BoardSheet
    BoardSheet.objects.filter(lesson_id__in=lesson_ids).delete()
    BoardGrant.objects.filter(lesson_id__in=lesson_ids).delete()
    BoardErase.objects.filter(lesson_id__in=lesson_ids).delete()
    boards_dir = Path(dj_settings.BASE_DIR) / 'private' / 'boards'
    for lesson_id in lesson_ids:
        pdf_path = boards_dir / f'{lesson_id}.pdf'
        if pdf_path.exists():
            pdf_path.unlink()

    # Chat — guruh xonasi + barcha xabarlar (biriktirilgan fayllar diskdan ham) butunlay o'chadi
    from apps.chat.models import ChatRoom
    room = ChatRoom.objects.filter(kind=ChatRoom.Kind.COURSE, course=course).first()
    if room is not None:
        for msg in room.messages.exclude(file=''):
            msg.file.delete(save=False)
        room.delete()

    # A'zolik — barcha userlar guruhdan chiqib ketadi
    course.enrollments.all().delete()

    # Kurs/darslar — SOFT delete (Attendance/LessonRating tarixi saqlanishi uchun)
    course.lessons.update(is_deleted=True, deleted_at=timezone.now())
    course.delete()

    audit.record(
        action='course.delete', actor=teacher, target=course,
        meta={'lesson_count': len(lesson_ids)}, request=request,
    )


@transaction.atomic
def finish_lesson(*, teacher: User, lesson: Lesson, recording_title: str = '', request=None) -> Lesson:
    """Darsni yakunlash — davomatlar yopiladi, doska PDF chatga tushadi,
    video yozuv to'xtatilib O'QITUVCHI BERGAN NOM bilan guruh chatga e'lon qilinadi."""
    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Faqat o'qituvchi darsni tugata oladi.")
    lesson.status = Lesson.Status.FINISHED
    lesson.save(update_fields=['status'])
    lesson.attendances.filter(left_at__isnull=True).update(left_at=timezone.now())
    # Guruh chatga "jonli dars tugadi" signali (Telegram uslubidagi chiziq yo'qoladi)
    try:
        from apps.chat import realtime as chat_realtime
        chat_realtime.broadcast_lesson_ended(lesson)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger('apps').exception('lesson_ended broadcast failed')
    # Doska lentasi -> PDF -> guruh chat (EduTech.docx). Xato yakunlashni to'xtatmaydi.
    try:
        from apps.board import services as board_services
        board_services.publish_board_pdf(lesson)
    except Exception:  # noqa: BLE001 — PDF muammosi dars yakunidan muhimroq emas
        import logging
        logging.getLogger('apps').exception('board pdf publish failed')
    # Video yozuv: to'xtatish + nom berish + guruh chatga e'lon (best-effort)
    try:
        from apps.live import services as live_services

        from .models import LessonRecording
        live_services.stop_recording(lesson=lesson)
        recording = LessonRecording.objects.filter(lesson=lesson).first()
        # E'lon faqat egress HAQIQATAN boshlanganida — aks holda chatga
        # "tayyor!" deb yolg'on xabar tushib qoladi
        if (
            recording is not None
            and recording.egress_id
            and recording.status != LessonRecording.Status.FAILED
        ):
            title = (recording_title or '').strip() or lesson.title
            recording.title = title[:200]
            recording.save(update_fields=['title', 'updated_at'])
            publish_recording_message(lesson, recording.title)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger('apps').exception('recording finalize failed')
    audit.record(action='lesson.finish', actor=teacher, target=lesson, request=request)
    return lesson


@transaction.atomic
def mark_joined(*, lesson: Lesson, student: User) -> Attendance:
    attendance, _ = Attendance.objects.get_or_create(lesson=lesson, student=student)
    if attendance.joined_at is None:
        attendance.joined_at = timezone.now()
        attendance.save(update_fields=['joined_at'])
    return attendance


@transaction.atomic
def mark_left(*, lesson_id, student: User) -> bool:
    updated = Attendance.objects.filter(
        lesson_id=lesson_id, student=student, left_at__isnull=True
    ).update(left_at=timezone.now())
    return bool(updated)


# ── Dars video yozuvi: ko'rish/oqim/o'chirish (faqat platforma ichida) ──────
# EduTech.docx: yozuv faqat platformada ochiladi — yuklab olib bo'lmaydi.
# Himoya: auth bilan beriladigan MUDDATLI imzolangan stream havolasi (3 soat),
# Content-Disposition: inline (pleer ochadi, "saqlash" taklif qilinmaydi),
# doimiy/ochiq URL yo'q.

RECORDING_STREAM_MAX_AGE = 3 * 60 * 60  # imzolangan havola muddati (sekund)


def _can_view_lesson(user: User, lesson: Lesson) -> bool:
    if lesson.course.teacher_id == user.id:
        return True
    if Enrollment.objects.filter(
        course=lesson.course, student=user, status=Enrollment.Status.APPROVED,
    ).exists():
        return True
    from apps.accounts.models import ParentChildLink
    child_ids = ParentChildLink.objects.filter(
        parent=user, status=ParentChildLink.Status.APPROVED,
    ).values_list('student_id', flat=True)
    return Enrollment.objects.filter(
        course=lesson.course, student_id__in=child_ids,
        status=Enrollment.Status.APPROVED,
    ).exists()


def _recording_path(recording):
    from django.conf import settings
    return settings.RECORDINGS_DIR / recording.file_name


def recording_info(*, user: User, lesson: Lesson) -> dict:
    """Yozuv holati + tayyor bo'lsa muddatli stream havolasi."""
    from django.core import signing

    from .models import LessonRecording

    if not _can_view_lesson(user, lesson):
        raise PermissionDenied("Bu dars yozuvini ko'rish huquqingiz yo'q.")
    recording = LessonRecording.objects.filter(lesson=lesson).first()
    if recording is None:
        raise NotFound("Bu darsda video yozuv yo'q.")

    # Fayl diskka tushgan bo'lsa — tayyor deb belgilaymiz
    path = _recording_path(recording) if recording.file_name else None
    file_ready = bool(path and path.exists() and path.stat().st_size > 0)
    in_progress = recording.status in (
        LessonRecording.Status.PENDING, LessonRecording.Status.RECORDING,
    )
    if file_ready and in_progress and lesson.status == Lesson.Status.FINISHED:
        recording.status = LessonRecording.Status.COMPLETED
        recording.save(update_fields=['status', 'updated_at'])
    elif in_progress and lesson.status == Lesson.Status.FINISHED and not file_ready:
        # Dars tugagan, fayl esa 3 daqiqadan beri yo'q — yozuv chiqmagan
        # (masalan, xonada media bo'lmagan). Abadiy "yozilmoqda" qolib
        # ketmasin — halol failed holatiga o'tkazamiz.
        from datetime import timedelta

        from django.utils import timezone as _tz
        reference = recording.ended_at or recording.updated_at
        if reference and _tz.now() - reference > timedelta(minutes=3):
            recording.status = LessonRecording.Status.FAILED
            recording.error = (
                "Yozuv fayli yaratilmadi — darsda video/audio bo'lmagan "
                "bo'lishi mumkin."
            )
            recording.save(update_fields=['status', 'error', 'updated_at'])

    data = {
        'lesson_id': str(lesson.id),
        'title': recording.title or lesson.title,
        'status': recording.status,
        'ready': file_ready,
        'created_at': recording.created_at,
        'ended_at': recording.ended_at,
        'error': recording.error,
        'stream_url': None,
    }
    if file_ready:
        # Imzolangan, muddatli havola — <video src> uchun (headerlarsiz),
        # 3 soatdan keyin yaroqsiz. Foydalanuvchi tekshiruvi SHU yerda bo'ldi.
        token = signing.TimestampSigner().sign(str(lesson.id))
        data['stream_url'] = f'/api/v1/lessons/{lesson.id}/recording/stream/?t={token}'
    return data


def recording_stream_path(*, lesson: Lesson, token: str):
    """Imzolangan tokenni tekshirib fayl yo'lini qaytaradi (stream view uchun)."""
    from django.core import signing

    from .models import LessonRecording

    try:
        value = signing.TimestampSigner().unsign(token, max_age=RECORDING_STREAM_MAX_AGE)
    except signing.BadSignature:
        raise PermissionDenied('Havola yaroqsiz yoki muddati tugagan.')
    if value != str(lesson.id):
        raise PermissionDenied('Havola boshqa darsga tegishli.')
    recording = LessonRecording.objects.filter(lesson=lesson).first()
    if recording is None or not recording.file_name:
        raise NotFound("Yozuv topilmadi.")
    path = _recording_path(recording)
    if not path.exists():
        raise NotFound("Yozuv fayli hali tayyor emas.")
    return path


def delete_recording(*, teacher: User, lesson: Lesson) -> None:
    """Faqat kurs o'qituvchisi. Fayl ham, yozuv ham o'chadi."""
    from .models import LessonRecording

    if lesson.course.teacher_id != teacher.id:
        raise PermissionDenied("Yozuvni faqat kurs o'qituvchisi o'chira oladi.")
    recording = LessonRecording.objects.filter(lesson=lesson).first()
    if recording is None:
        raise NotFound("Yozuv yo'q.")
    if recording.file_name:
        path = _recording_path(recording)
        if path.exists():
            path.unlink()
    recording.delete()


def publish_recording_message(lesson: Lesson, title: str) -> None:
    """Dars tugagach guruh chatga yozuv havolasini tashlaydi (board PDF uslubi)."""
    from apps.chat import services as chat_services
    from apps.chat.models import Message

    room = chat_services.ensure_course_room(lesson.course)
    Message.objects.create(
        room=room,
        sender=lesson.course.teacher,
        text=(
            f'🎥 "{title}" — dars video yozuvi tayyor!\n'
            f"Ko'rish (faqat platformada): /recordings/{lesson.id}"
        ),
    )
