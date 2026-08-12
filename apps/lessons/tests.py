from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests import PASSWORD, login, register

from .models import Attendance


class CourseLessonFlowTests(APITestCase):
    def setUp(self):
        register(self.client, 't1', 'teacher')
        self.teacher_token = login(self.client, 't1')

        register(self.client, 'p1', 'parent')
        self.parent_token = login(self.client, 'p1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        resp = self.client.post('/api/v1/auth/children/', {'username': 's1', 'password': PASSWORD})
        self.child_id = resp.json()['id']
        self.child_token = login(self.client, 's1')

        # teacher creates course + lesson
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.teacher_token}')
        self.course_id = self.client.post(
            '/api/v1/courses/', {'title': 'Algebra', 'subject': 'Matematika'}
        ).json()['id']
        starts_at = (timezone.now() + timedelta(days=1)).isoformat()
        self.lesson_id = self.client.post('/api/v1/lessons/', {
            'course': self.course_id, 'title': 'Dars 1',
            'starts_at': starts_at, 'duration_min': 45,
        }).json()['id']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def approve_all_requests(self):
        """O'qituvchi sifatida barcha kutilayotgan yozilish so'rovlarini tasdiqlaydi."""
        self.auth(self.teacher_token)
        for req in self.client.get('/api/v1/courses/requests/').json()['results']:
            self.client.post('/api/v1/courses/requests/respond/', {
                'enrollment_id': req['id'], 'action': 'approve',
            })

    def test_student_cannot_create_course(self):
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/courses/', {'title': 'Hack'})
        self.assertEqual(resp.status_code, 403)

    def test_parent_enrolls_linked_child_only(self):
        self.auth(self.parent_token)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['status'], 'pending')  # o'qituvchi tasdig'ini kutadi

        # another parent with no link cannot enroll this child
        register(self.client, 'p2', 'parent')
        p2 = login(self.client, 'p2')
        self.auth(p2)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.assertEqual(resp.status_code, 403)

    def test_pending_enrollment_gives_no_access_until_approved(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})

        # tasdiqlanmagan — token yo'q, darslar ko'rinmaydi
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(self.client.get('/api/v1/lessons/').json()['results']), 0)

        # o'qituvchi tasdiqladi — endi kiradi
        self.approve_all_requests()
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})
        self.assertEqual(resp.status_code, 200)

    def test_teacher_direct_enroll_is_approved(self):
        self.auth(self.teacher_token)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student': 's1'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['status'], 'approved')

    def test_room_token_flow_and_attendance(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.approve_all_requests()

        # student joins -> attendance stamped
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['token'])
        self.assertFalse(resp.json()['is_teacher'])
        attendance = Attendance.objects.get(lesson_id=self.lesson_id, student_id=self.child_id)
        self.assertIsNotNone(attendance.joined_at)

        # teacher joins -> lesson goes live
        self.auth(self.teacher_token)
        resp = self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})
        self.assertTrue(resp.json()['is_teacher'])

        # teacher finishes -> open attendance closed
        resp = self.client.post(f'/api/v1/lessons/{self.lesson_id}/finish/')
        self.assertEqual(resp.json()['status'], 'finished')
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.left_at)

    def test_unenrolled_student_cannot_get_token(self):
        register(self.client, 'p3', 'parent')
        p3 = login(self.client, 'p3')
        self.auth(p3)
        outsider = self.client.post('/api/v1/auth/children/', {'username': 's2', 'password': PASSWORD})
        outsider_token = login(self.client, 's2')
        self.auth(outsider_token)
        resp = self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})
        self.assertEqual(resp.status_code, 403)

    def test_parent_sees_only_linked_child_attendance(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.approve_all_requests()
        self.auth(self.child_token)
        self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})

        self.auth(self.parent_token)
        resp = self.client.get('/api/v1/attendance/')
        self.assertEqual(len(resp.json()['results']), 1)

        register(self.client, 'p4', 'parent')
        p4 = login(self.client, 'p4')
        self.auth(p4)
        resp = self.client.get('/api/v1/attendance/')
        self.assertEqual(len(resp.json()['results']), 0)

    def test_soft_delete_course(self):
        self.auth(self.teacher_token)
        resp = self.client.delete(f'/api/v1/courses/{self.course_id}/')
        self.assertEqual(resp.status_code, 204)
        from .models import Course
        self.assertFalse(Course.objects.filter(pk=self.course_id).exists())
        self.assertTrue(Course.all_objects.filter(pk=self.course_id).exists())

    def test_cannot_create_lesson_in_past(self):
        self.auth(self.teacher_token)
        past = (timezone.now() - timedelta(days=1)).isoformat()
        resp = self.client.post('/api/v1/lessons/', {
            'course': self.course_id, 'title': "O'tgan dars",
            'starts_at': past, 'duration_min': 45,
        })
        self.assertEqual(resp.status_code, 400)

    def test_can_edit_other_fields_of_existing_lesson(self):
        """starts_at o'zgarmasa (allaqachon kelajakda bo'lsa ham), boshqa
        maydonni tahrirlash bloklanmasligini tekshiradi."""
        self.auth(self.teacher_token)
        resp = self.client.patch(f'/api/v1/lessons/{self.lesson_id}/', {'title': 'Yangi nom'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['title'], 'Yangi nom')

    def test_schedule_recurring_rejects_past_start_date(self):
        self.auth(self.teacher_token)
        past_date = (timezone.now().date() - timedelta(days=7)).isoformat()
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/schedule/', {
            'title': "O'tgan hafta",
            'days': [0],
            'start_time': '10:00',
            'end_time': '11:00',
            'weeks': 1,
            'start_date': past_date,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_schedule_recurring_creates_lessons(self):
        self.auth(self.teacher_token)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/schedule/', {
            'title': 'Haftalik dars',
            'days': [0, 2, 4],
            'start_time': '10:00',
            'end_time': '11:00',
            'weeks': 2,
            'start_date': '2026-09-07',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['count'], 6)

    def test_schedule_recurring_detects_overlap(self):
        self.auth(self.teacher_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/schedule/', {
            'title': 'Dars A',
            'days': [0],
            'start_time': '14:00',
            'end_time': '15:00',
            'weeks': 1,
            'start_date': '2026-09-07',
        }, format='json')
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/schedule/', {
            'title': 'Dars B',
            'days': [0],
            'start_time': '14:30',
            'end_time': '15:30',
            'weeks': 1,
            'start_date': '2026-09-07',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_rate_finished_lesson(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.approve_all_requests()
        self.auth(self.teacher_token)
        self.client.post(f'/api/v1/lessons/{self.lesson_id}/finish/')

        self.auth(self.child_token)
        resp = self.client.post(f'/api/v1/lessons/{self.lesson_id}/rate/', {'stars': 5, 'description': 'Zo\'r!'})
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get(f'/api/v1/lessons/{self.lesson_id}/')
        self.assertEqual(resp.json()['avg_rating'], 5.0)
        self.assertEqual(resp.json()['rating_count'], 1)

    def test_cannot_rate_unfinished_lesson(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.approve_all_requests()
        self.auth(self.child_token)
        resp = self.client.post(f'/api/v1/lessons/{self.lesson_id}/rate/', {'stars': 4})
        self.assertEqual(resp.status_code, 400)

    def test_delete_course_wipes_group_data_keeps_history(self):
        from apps.board.models import BoardSheet
        from apps.chat.models import ChatRoom, Message

        from .models import Course, LessonRating

        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.approve_all_requests()

        self.auth(self.child_token)
        self.client.post('/api/v1/live/token/', {'lesson_id': self.lesson_id})

        BoardSheet.objects.create(
            lesson_id=self.lesson_id, index=0,
            strokes=[{'id': 'x', 'points': [[0, 0], [1, 1]], 'color': '#000', 'width': 2}],
        )
        room = ChatRoom.objects.get(kind=ChatRoom.Kind.COURSE, course_id=self.course_id)
        teacher = User.objects.get(username='t1')
        Message.objects.create(room=room, sender=teacher, text='Salom guruh!')

        self.auth(self.teacher_token)
        self.client.post(f'/api/v1/lessons/{self.lesson_id}/finish/')

        self.auth(self.child_token)
        self.client.post(f'/api/v1/lessons/{self.lesson_id}/rate/', {'stars': 5})

        self.assertTrue(Attendance.objects.filter(lesson_id=self.lesson_id).exists())
        self.assertTrue(LessonRating.objects.filter(lesson_id=self.lesson_id).exists())

        self.auth(self.teacher_token)
        resp = self.client.delete(f'/api/v1/courses/{self.course_id}/')
        self.assertEqual(resp.status_code, 204)

        # guruh ma'lumotlari butunlay o'chadi
        self.assertFalse(ChatRoom.objects.filter(course_id=self.course_id).exists())
        self.assertFalse(BoardSheet.objects.filter(lesson_id=self.lesson_id).exists())
        self.assertFalse(self.client.get(f'/api/v1/courses/{self.course_id}/').json().get('id'))

        # kurs/dars yashiriladi (soft-delete), lekin bazadan o'chmaydi
        self.assertFalse(Course.objects.filter(pk=self.course_id).exists())
        self.assertTrue(Course.all_objects.filter(pk=self.course_id).exists())

        # Davomat va baho TARIXI saqlanib qoladi
        self.assertTrue(Attendance.objects.filter(lesson_id=self.lesson_id).exists())
        self.assertTrue(LessonRating.objects.filter(lesson_id=self.lesson_id).exists())

    def test_other_teacher_cannot_delete_foreign_course(self):
        register(self.client, 't2', 'teacher')
        t2_token = login(self.client, 't2')
        self.auth(t2_token)
        resp = self.client.delete(f'/api/v1/courses/{self.course_id}/')
        self.assertEqual(resp.status_code, 404)  # boshqa oquvchining kursi korinmaydi (queryset scoped)


class FocusSummaryTests(APITestCase):
    """Chiqish-qaytish tahlili: juftlash, jami/eng uzun vaqt, taymlayn."""

    def setUp(self):
        from apps.accounts.models import User

        self.teacher = User(username='fs_t', role=User.Role.TEACHER)
        self.teacher.set_password('x')
        self.teacher.save()
        self.student = User(username='fs_s', role=User.Role.STUDENT)
        self.student.set_password('x')
        self.student.save()
        from django.utils import timezone

        from .models import Course, Lesson

        course = Course.objects.create(teacher=self.teacher, title='F')
        self.lesson = Lesson.objects.create(
            course=course, title='L', starts_at=timezone.now(), duration_min=45,
        )

    def _event(self, kind, at):
        from .models import FocusEvent

        e = FocusEvent.objects.create(lesson=self.lesson, student=self.student, kind=kind)
        # auto_now_add ni chetlab, vaqtni aniq boshqaramiz
        FocusEvent.objects.filter(pk=e.pk).update(created_at=at)

    def test_pairs_and_totals(self):
        from datetime import timedelta

        from django.utils import timezone

        from . import selectors

        t0 = timezone.now()
        self._event('exit', t0)                                  # 1-chiqish: 30s
        self._event('return', t0 + timedelta(seconds=30))
        self._event('exit', t0 + timedelta(seconds=100))         # 2-chiqish: 120s
        self._event('return', t0 + timedelta(seconds=220))
        s = selectors.focus_summary(self.lesson, self.student)
        self.assertEqual(s['exits'], 2)
        self.assertEqual(s['away_seconds'], 150)
        self.assertEqual(s['longest_seconds'], 120)
        self.assertEqual(len(s['timeline']), 2)
        self.assertEqual(s['timeline'][0]['seconds'], 30)
        self.assertEqual(s['timeline'][1]['seconds'], 120)

    def test_unreturned_exit_capped_by_left_at(self):
        from datetime import timedelta

        from django.utils import timezone

        from . import selectors
        from .models import Attendance

        t0 = timezone.now()
        self._event('exit', t0)
        Attendance.objects.create(
            lesson=self.lesson, student=self.student,
            joined_at=t0 - timedelta(minutes=10), left_at=t0 + timedelta(seconds=60),
        )
        s = selectors.focus_summary(self.lesson, self.student)
        self.assertEqual(s['exits'], 1)
        self.assertEqual(s['away_seconds'], 60)
        self.assertIsNone(s['timeline'][0]['returned_at'])

    def test_empty(self):
        from . import selectors

        s = selectors.focus_summary(self.lesson, self.student)
        self.assertEqual(s, {'exits': 0, 'away_seconds': 0, 'longest_seconds': 0, 'timeline': []})


class ParentSeesFocusTests(APITestCase):
    """Fokus tahlili (chiqish-qaytish taymlayn) aynan o'sha bolaning
    OTA-ONASIGA ko'rinadi; begona ota-onaga ko'rinmaydi."""

    def setUp(self):
        register(self.client, 'pf_t', 'teacher')
        self.teacher_token = login(self.client, 'pf_t')

        register(self.client, 'pf_p', 'parent')
        self.parent_token = login(self.client, 'pf_p')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        self.child_id = self.client.post(
            '/api/v1/auth/children/', {'username': 'pf_s', 'password': PASSWORD},
        ).json()['id']

        from datetime import timedelta

        from django.utils import timezone

        from apps.accounts.models import User

        from .models import Course, Enrollment, FocusEvent, Lesson

        teacher = User.objects.get(username='pf_t')
        self.studentu = User.objects.get(username='pf_s')
        course = Course.objects.create(teacher=teacher, title='PF')
        Enrollment.objects.create(
            course=course, student=self.studentu, status=Enrollment.Status.APPROVED,
        )
        lesson = Lesson.objects.create(
            course=course, title='L', starts_at=timezone.now(), duration_min=45,
        )
        Attendance.objects.create(lesson=lesson, student=self.studentu, joined_at=timezone.now())
        t0 = timezone.now()
        for kind, at in [('exit', t0), ('return', t0 + timedelta(seconds=45))]:
            e = FocusEvent.objects.create(lesson=lesson, student=self.studentu, kind=kind)
            FocusEvent.objects.filter(pk=e.pk).update(created_at=at)

    def test_parent_sees_child_focus_timeline(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        rows = self.client.get('/api/v1/attendance/').json()['results']
        self.assertEqual(len(rows), 1)
        focus = rows[0]['focus']
        self.assertEqual(focus['exits'], 1)
        self.assertEqual(focus['away_seconds'], 45)
        self.assertEqual(len(focus['timeline']), 1)
        self.assertIsNotNone(focus['timeline'][0]['returned_at'])

    def test_other_parent_sees_nothing(self):
        register(self.client, 'pf_p2', 'parent')
        p2 = login(self.client, 'pf_p2')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {p2}')
        rows = self.client.get('/api/v1/attendance/').json()['results']
        self.assertEqual(len(rows), 0)


class RecordingTests(APITestCase):
    """Dars video yozuvi: nom berish + chat e'loni, faqat-platforma stream,
    ruxsatlar, o'chirish."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings
        from django.utils import timezone

        from apps.accounts.models import User

        from .models import Course, Enrollment, Lesson, LessonRecording

        self.tmp = tempfile.mkdtemp()
        self._override = override_settings(RECORDINGS_DIR=Path(self.tmp))
        self._override.enable()
        self.addCleanup(self._override.disable)

        def mk(username, role):
            u = User(username=username, role=role)
            u.set_password('x')
            u.save()
            return u

        self.teacher = mk('rc_t', User.Role.TEACHER)
        self.student = mk('rc_s', User.Role.STUDENT)
        self.stranger = mk('rc_x', User.Role.STUDENT)
        self.course = Course.objects.create(teacher=self.teacher, title='RC')
        Enrollment.objects.create(
            course=self.course, student=self.student, status=Enrollment.Status.APPROVED,
        )
        self.lesson = Lesson.objects.create(
            course=self.course, title='Yozuvli dars',
            starts_at=timezone.now(), duration_min=45,
            status=Lesson.Status.LIVE,
        )
        # Egress yozgan faylni imitatsiya qilamiz (egress tasdiqlagan holat)
        self.recording = LessonRecording.objects.create(
            lesson=self.lesson, file_name=f'{self.lesson.room_name}.mp4',
            egress_id='EG_test', status=LessonRecording.Status.RECORDING,
        )
        (Path(self.tmp) / self.recording.file_name).write_bytes(b'\x00' * 2048)

    def api(self, user):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_finish_names_recording_and_posts_to_chat(self):
        from apps.chat.models import Message

        from . import services as lesson_services
        lesson_services.finish_lesson(
            teacher=self.teacher, lesson=self.lesson,
            recording_title='Kvadrat tenglamalar (video)',
        )
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.title, 'Kvadrat tenglamalar (video)')
        msg = Message.objects.filter(text__contains='/recordings/').latest('created_at')
        self.assertIn('Kvadrat tenglamalar (video)', msg.text)
        self.assertIn(str(self.lesson.id), msg.text)

    def test_info_gives_stream_url_to_member_only(self):
        r = self.api(self.student).get(f'/api/v1/lessons/{self.lesson.id}/recording/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['ready'])
        self.assertIn('/recording/stream/?t=', r.data['stream_url'])
        # begona: dars queryset'ida yo'q — 404 (mavjudligi ham oshkor bo'lmaydi)
        r = self.api(self.stranger).get(f'/api/v1/lessons/{self.lesson.id}/recording/')
        self.assertEqual(r.status_code, 404)

    def test_stream_requires_valid_token(self):
        info = self.api(self.student).get(f'/api/v1/lessons/{self.lesson.id}/recording/')
        url = info.data['stream_url']
        from rest_framework.test import APIClient

        anon = APIClient()  # token URLda — auth header kerak emas
        r = anon.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Disposition'], 'inline')
        # Range (seek) ishlaydi
        r = anon.get(url, HTTP_RANGE='bytes=100-199')
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r['Content-Length'], '100')
        # buzilgan token — yo'q
        r = anon.get(f'/api/v1/lessons/{self.lesson.id}/recording/stream/?t=soxta')
        self.assertEqual(r.status_code, 403)

    def test_delete_teacher_only(self):
        r = self.api(self.student).delete(f'/api/v1/lessons/{self.lesson.id}/recording/')
        self.assertEqual(r.status_code, 403)
        r = self.api(self.teacher).delete(f'/api/v1/lessons/{self.lesson.id}/recording/')
        self.assertEqual(r.status_code, 204)
        from pathlib import Path

        self.assertFalse((Path(self.tmp) / f'{self.lesson.room_name}.mp4').exists())


class FocusEscalationTests(APITestCase):
    """EPAM imtihon uslubi: 1-2 marta oynadan chiqish — o'ziga ogohlantirish,
    3-chisida (FOCUS_PARENT_ALERT_THRESHOLD) — ota-onaga FocusAlert signali."""

    def setUp(self):
        from django.utils import timezone

        from apps.accounts.models import User

        from .models import Course, Enrollment, Lesson

        def mk(username, role):
            u = User(username=username, role=role)
            u.set_password('x')
            u.save()
            return u

        self.teacher = mk('fe_t', User.Role.TEACHER)
        self.student = mk('fe_s', User.Role.STUDENT)
        course = Course.objects.create(teacher=self.teacher, title='FE')
        Enrollment.objects.create(course=course, student=self.student, status=Enrollment.Status.APPROVED)
        self.lesson = Lesson.objects.create(
            course=course, title='L', starts_at=timezone.now(), duration_min=45,
            status=Lesson.Status.LIVE,
        )

    def api(self, user):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(user)
        return c

    def _exit(self):
        return self.api(self.student).post('/api/v1/live/focus/', {
            'lesson_id': str(self.lesson.id), 'kind': 'exit',
        })

    def test_first_two_exits_only_warn_student(self):
        for expected_count in (1, 2):
            resp = self._exit()
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body['exit_count'], expected_count)
            self.assertEqual(body['threshold'], 3)
            self.assertFalse(body['parent_notified'])
        from .models import FocusAlert
        self.assertFalse(FocusAlert.objects.filter(lesson=self.lesson, student=self.student).exists())

    def test_third_exit_notifies_parent_and_creates_alert(self):
        from .models import FocusAlert

        self._exit()
        self._exit()
        resp = self._exit()
        body = resp.json()
        self.assertEqual(body['exit_count'], 3)
        self.assertTrue(body['parent_notified'])
        alert = FocusAlert.objects.get(lesson=self.lesson, student=self.student)
        self.assertEqual(alert.exit_count, 3)

    def test_alert_created_only_once_despite_further_exits(self):
        from .models import FocusAlert

        for _ in range(5):
            self._exit()
        self.assertEqual(
            FocusAlert.objects.filter(lesson=self.lesson, student=self.student).count(), 1,
        )

    def test_attendance_serializer_exposes_focus_alert(self):
        from django.utils import timezone

        from .models import Attendance

        Attendance.objects.create(lesson=self.lesson, student=self.student, joined_at=timezone.now())
        for _ in range(3):
            self._exit()
        rows = self.api(self.teacher).get('/api/v1/attendance/').json()['results']
        row = next(r for r in rows if r['student']['username'] == 'fe_s')
        self.assertTrue(row['focus_alert'])

    def test_return_event_does_not_affect_counter(self):
        r = self.api(self.student).post('/api/v1/live/focus/', {
            'lesson_id': str(self.lesson.id), 'kind': 'return',
        })
        body = r.json()
        self.assertIsNone(body['exit_count'])
        self.assertFalse(body['parent_notified'])


class RecordingLifecycleTests(APITestCase):
    """Yozuv hayotiy tsikli: yolg'on holatlar yo'q — pending/failed halol,
    e'lon faqat haqiqiy yozuvda, qotib qolganlar avtomatik yakunlanadi."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings
        from django.utils import timezone

        from apps.accounts.models import User

        from .models import Course, Enrollment, Lesson

        self._override = override_settings(RECORDINGS_DIR=Path(tempfile.mkdtemp()))
        self._override.enable()
        self.addCleanup(self._override.disable)

        def mk(username, role):
            u = User(username=username, role=role)
            u.set_password('x')
            u.save()
            return u

        self.teacher = mk('rl_t', User.Role.TEACHER)
        self.student = mk('rl_s', User.Role.STUDENT)
        self.course = Course.objects.create(teacher=self.teacher, title='RL')
        from apps.chat import services as chat_services
        chat_services.ensure_course_room(self.course)
        Enrollment.objects.create(
            course=self.course, student=self.student, status=Enrollment.Status.APPROVED,
        )
        self.lesson = Lesson.objects.create(
            course=self.course, title='L', starts_at=timezone.now(),
            duration_min=45, status=Lesson.Status.LIVE,
        )

    def test_no_chat_message_when_egress_never_started(self):
        """Egress boshlanmagan (egress_id yo'q) — chatga yolg'on e'lon tushmaydi."""
        from apps.chat.models import Message

        from . import services as lesson_services
        from .models import LessonRecording

        LessonRecording.objects.create(lesson=self.lesson)  # pending, egresssiz
        before = Message.objects.count()
        lesson_services.finish_lesson(
            teacher=self.teacher, lesson=self.lesson, recording_title='X',
        )
        recording_msgs = Message.objects.filter(text__contains='/recordings/').count()
        self.assertEqual(Message.objects.count() - before, 0)
        self.assertEqual(recording_msgs, 0)

    def test_stale_pending_marked_failed_on_info(self):
        """Dars tugagan, fayl 3+ daqiqa yo'q — info so'ralganda halol failed."""
        from datetime import timedelta

        from django.utils import timezone

        from .models import Lesson, LessonRecording

        recording = LessonRecording.objects.create(
            lesson=self.lesson, egress_id='EG_x', file_name='yoq.mp4',
        )
        self.lesson.status = Lesson.Status.FINISHED
        self.lesson.save(update_fields=['status'])
        LessonRecording.objects.filter(pk=recording.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(self.teacher)
        r = client.get(f'/api/v1/lessons/{self.lesson.id}/recording/')
        self.assertEqual(r.data['status'], 'failed')
        self.assertIn('yaratilmadi', r.data['error'])

    def test_friendly_error_mapping(self):
        from apps.live.services import _friendly_egress_error

        self.assertIn('hech kim ulanmadi', _friendly_egress_error(
            Exception('twirp error not_found: requested room does not exist')))
        self.assertIn('avtorizatsiya', _friendly_egress_error(
            Exception('ServerError(code=unknown, message=, status=401)')))
        self.assertIn("video/audio bo'lmadi", _friendly_egress_error(
            Exception('Start signal not received')))
        self.assertIn('texnik xato', _friendly_egress_error(Exception('boom')))
