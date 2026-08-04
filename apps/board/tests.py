"""Doska oqimi testlari — chizish ruxsati, o'chirish sababi, PDF -> chat."""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import services as chat_services
from apps.chat.models import Message
from apps.lessons.models import Course, Enrollment, Lesson

from . import services


def make(username, role):
    u = User(username=username, role=role)
    u.set_password('x')
    u.save()
    return u


STROKE = {'points': [[10, 10], [100, 100], [200, 150]], 'color': '#ff0000', 'width': 4}


class BoardTests(TestCase):
    def setUp(self):
        self.teacher = make('t1', User.Role.TEACHER)
        self.student = make('s1', User.Role.STUDENT)
        self.course = Course.objects.create(
            teacher=self.teacher, title='Algebra', subject='Matematika',
        )
        chat_services.ensure_course_room(self.course)
        Enrollment.objects.create(
            course=self.course, student=self.student, status=Enrollment.Status.APPROVED,
        )
        self.lesson = Lesson.objects.create(
            course=self.course, title='Dars', starts_at=timezone.now(), duration_min=45,
        )
        self.client = APIClient()

    def api(self, user):
        self.client.force_authenticate(user)
        return self.client

    def url(self, tail=''):
        return f'/api/v1/board/{self.lesson.id}/{tail}'

    def test_teacher_draws_student_views(self):
        r = self.api(self.teacher).post(self.url('stroke/'), {'sheet': 0, 'stroke': STROKE}, format='json')
        self.assertEqual(r.status_code, 201)
        r = self.api(self.student).get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['sheets'][0]['strokes']), 1)
        self.assertFalse(r.data['can_draw'])

    def test_student_needs_grant_to_draw(self):
        r = self.api(self.student).post(self.url('stroke/'), {'sheet': 0, 'stroke': STROKE}, format='json')
        self.assertEqual(r.status_code, 403)
        self.api(self.teacher).post(self.url('grant/'), {'student_id': str(self.student.id)}, format='json')
        r = self.api(self.student).post(self.url('stroke/'), {'sheet': 0, 'stroke': STROKE}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_erase_requires_reason(self):
        r = self.api(self.teacher).post(self.url('stroke/'), {'sheet': 0, 'stroke': STROKE}, format='json')
        sid = r.data['id']
        r = self.api(self.teacher).post(
            self.url('erase/'), {'sheet': 0, 'stroke_ids': [sid], 'reason': ''}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        r = self.api(self.teacher).post(
            self.url('erase/'), {'sheet': 0, 'stroke_ids': [sid], 'reason': "Xato chizildi"}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['removed'], 1)

    def test_finish_publishes_pdf_message(self):
        services.add_stroke(user=self.teacher, lesson_id=self.lesson.id, sheet_index=0, stroke=STROKE)
        self.api(self.teacher).post(f'/api/v1/lessons/{self.lesson.id}/finish/')
        msg = Message.objects.filter(room=self.course.chat_room).last()
        self.assertIsNotNone(msg)
        self.assertIn(f'/boards/{self.lesson.id}', msg.text)
        # PDF autentifikatsiya bilan yuklab olinadi
        r = self.api(self.student).get(self.url('pdf/'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_solve_and_place_formula(self):
        # Photomath uslubi: yechish
        r = self.api(self.teacher).post(self.url('solve/'), {'expr': 'x^2 - 5x + 6 = 0'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('x = 2', r.data['result'])
        self.assertTrue(any('Diskriminant' in s for s in r.data['steps']))
        # yaroqsiz formula
        r = self.api(self.teacher).post(self.url('solve/'), {'expr': '???'}, format='json')
        self.assertEqual(r.status_code, 400)
        # matn elementini doskaga qo'yish
        r = self.api(self.teacher).post(self.url('stroke/'), {
            'sheet': 0,
            'stroke': {'type': 'text', 'text': 'x = 2, x = 3', 'x': 60, 'y': 50, 'size': 22},
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['type'], 'text')

    def test_multiple_sheets(self):
        r = self.api(self.teacher).post(self.url('sheet/'))
        self.assertEqual(r.data['index'], 0)
        self.api(self.teacher).post(self.url('stroke/'), {'sheet': 0, 'stroke': STROKE}, format='json')
        r = self.api(self.teacher).post(self.url('sheet/'))
        self.assertEqual(r.data['index'], 1)


class MathBoardTests(TestCase):
    """MathLive kontrakti: formula bloklari va SymPy yechuvchi FAQAT
    matematika kurslarida; PDF LaTeX'ni render qiladi."""

    MATH_STROKE = {
        'type': 'math', 'latex': r'\frac{x^2-9}{x-3}', 'x': 80, 'y': 90, 'size': 24,
    }

    def setUp(self):
        self.teacher = make('mb_t', User.Role.TEACHER)
        self.math_course = Course.objects.create(
            teacher=self.teacher, title='Algebra 7', subject='Matematika',
        )
        self.eng_course = Course.objects.create(
            teacher=self.teacher, title='English', subject='Ingliz tili',
        )
        chat_services.ensure_course_room(self.math_course)
        chat_services.ensure_course_room(self.eng_course)
        self.math_lesson = Lesson.objects.create(
            course=self.math_course, title='M', starts_at=timezone.now(), duration_min=45,
        )
        self.eng_lesson = Lesson.objects.create(
            course=self.eng_course, title='E', starts_at=timezone.now(), duration_min=45,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.teacher)

    def test_math_enabled_flag_math_only(self):
        r = self.client.get(f'/api/v1/board/{self.math_lesson.id}/')
        self.assertTrue(r.data['math_enabled'])
        r = self.client.get(f'/api/v1/board/{self.eng_lesson.id}/')
        self.assertFalse(r.data['math_enabled'])

    def test_math_stroke_only_on_math_course(self):
        r = self.client.post(
            f'/api/v1/board/{self.math_lesson.id}/stroke/',
            {'sheet': 0, 'stroke': self.MATH_STROKE}, format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['type'], 'math')
        self.assertEqual(r.data['latex'], r'\frac{x^2-9}{x-3}')

        r = self.client.post(
            f'/api/v1/board/{self.eng_lesson.id}/stroke/',
            {'sheet': 0, 'stroke': self.MATH_STROKE}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_solver_only_on_math_course(self):
        r = self.client.post(
            f'/api/v1/board/{self.math_lesson.id}/solve/', {'expr': 'x^2 - 9 = 0'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        r = self.client.post(
            f'/api/v1/board/{self.eng_lesson.id}/solve/', {'expr': 'x^2 - 9 = 0'}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_pdf_renders_math_stroke(self):
        self.client.post(
            f'/api/v1/board/{self.math_lesson.id}/stroke/',
            {'sheet': 0, 'stroke': self.MATH_STROKE}, format='json',
        )
        path = services.generate_pdf(self.math_lesson)
        self.assertIsNotNone(path)
        self.assertGreater(path.stat().st_size, 1000)
        path.unlink()
