from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests import register, login

from .models import Quiz


def _mcq(text, correct_index, options, points=1):
    return {
        'text': text,
        'points': points,
        'options': [
            {'text': opt, 'is_correct': i == correct_index}
            for i, opt in enumerate(options)
        ],
    }


class QuizFlowTests(APITestCase):
    def setUp(self):
        register(self.client, 't1', 'teacher')
        self.teacher_token = login(self.client, 't1')

        register(self.client, 'p1', 'parent')
        self.parent_token = login(self.client, 'p1')
        self.auth(self.parent_token)
        resp = self.client.post('/api/v1/auth/children/', {'username': 's1', 'password': 'StrongPass123!'})
        self.child_id = resp.json()['id']
        self.child_token = login(self.client, 's1')

        self.auth(self.teacher_token)
        self.course_id = self.client.post(
            '/api/v1/courses/', {'title': 'Algebra', 'subject': 'Matematika'}
        ).json()['id']

        self.quiz_payload = {
            'course': self.course_id,
            'title': "1-bob testi",
            'questions': [
                _mcq('2 + 2 = ?', correct_index=1, options=['3', '4', '5']),
                _mcq('Poytaxt?', correct_index=0, options=['Toshkent', 'Samarqand'], points=2),
            ],
        }

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def enroll_child(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.auth(self.teacher_token)
        for req in self.client.get('/api/v1/courses/requests/').json()['results']:
            self.client.post('/api/v1/courses/requests/respond/', {
                'enrollment_id': req['id'], 'action': 'approve',
            })

    def create_quiz(self):
        self.auth(self.teacher_token)
        resp = self.client.post('/api/v1/quizzes/', self.quiz_payload, format='json')
        return resp

    def test_teacher_creates_quiz_with_questions_and_options(self):
        resp = self.create_quiz()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.json()['questions']), 2)
        self.assertEqual(len(resp.json()['questions'][0]['options']), 3)
        self.assertTrue(Quiz.objects.filter(title="1-bob testi").exists())

    def test_student_cannot_create_quiz(self):
        self.enroll_child()
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/quizzes/', self.quiz_payload, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_question_requires_exactly_one_correct_option(self):
        self.auth(self.teacher_token)
        bad = {
            'course': self.course_id,
            'title': 'Xato test',
            'questions': [{
                'text': '1+1=?', 'points': 1,
                'options': [{'text': '2', 'is_correct': True}, {'text': '3', 'is_correct': True}],
            }],
        }
        resp = self.client.post('/api/v1/quizzes/', bad, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_student_take_view_hides_correct_answer(self):
        quiz_id = self.create_quiz().json()['id']
        self.enroll_child()
        self.auth(self.child_token)
        resp = self.client.get(f'/api/v1/quizzes/{quiz_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('is_correct', resp.json()['questions'][0]['options'][0])

    def test_non_enrolled_student_cannot_see_quiz(self):
        quiz_id = self.create_quiz().json()['id']
        self.auth(self.child_token)  # hali enroll qilinmagan
        resp = self.client.get(f'/api/v1/quizzes/{quiz_id}/')
        self.assertEqual(resp.status_code, 404)

    def test_submit_attempt_scores_correctly_and_reveals_answers(self):
        quiz = self.create_quiz().json()
        self.enroll_child()
        q1, q2 = quiz['questions']
        answers = [
            {'question': q1['id'], 'selected_option': q1['options'][1]['id']},  # to'g'ri (4)
            {'question': q2['id'], 'selected_option': q2['options'][1]['id']},  # xato (Samarqand)
        ]
        self.auth(self.child_token)
        resp = self.client.post(f'/api/v1/quizzes/{quiz["id"]}/attempts/', {'answers': answers}, format='json')
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body['score'], 1)
        self.assertEqual(body['max_score'], 3)
        wrong_answer = next(a for a in body['answers'] if not a['is_correct'])
        self.assertEqual(wrong_answer['correct_option']['text'], 'Toshkent')

    def test_student_can_retake_unlimited_times(self):
        quiz = self.create_quiz().json()
        self.enroll_child()
        q1, q2 = quiz['questions']
        self.auth(self.child_token)
        for _ in range(3):
            self.client.post(f'/api/v1/quizzes/{quiz["id"]}/attempts/', {'answers': [
                {'question': q1['id'], 'selected_option': q1['options'][1]['id']},
                {'question': q2['id'], 'selected_option': q2['options'][0]['id']},
            ]}, format='json')
        resp = self.client.get(f'/api/v1/quizzes/{quiz["id"]}/attempts/')
        self.assertEqual(len(resp.json()), 3)
        self.assertTrue(all(a['score'] == 3 for a in resp.json()))

    def test_other_teacher_cannot_see_or_delete_foreign_quiz(self):
        quiz_id = self.create_quiz().json()['id']
        register(self.client, 't2', 'teacher')
        self.auth(login(self.client, 't2'))
        self.assertEqual(self.client.get(f'/api/v1/quizzes/{quiz_id}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/v1/quizzes/{quiz_id}/').status_code, 404)

    def test_owning_teacher_can_delete_quiz(self):
        quiz_id = self.create_quiz().json()['id']
        self.auth(self.teacher_token)
        resp = self.client.delete(f'/api/v1/quizzes/{quiz_id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Quiz.objects.filter(pk=quiz_id).exists())

    def test_creating_quiz_notifies_enrolled_students(self):
        from apps.notifications.models import Notification

        self.enroll_child()
        with self.captureOnCommitCallbacks(execute=True):
            self.create_quiz()
        note = Notification.objects.filter(link_type='quiz').latest('created_at')
        self.assertIn('1-bob testi', note.description)
        self.assertTrue(note.recipients.filter(user_id=self.child_id).exists())

    def test_future_quiz_hidden_from_student_until_opens_at(self):
        from datetime import timedelta

        from django.utils import timezone

        self.enroll_child()
        self.auth(self.teacher_token)
        payload = {**self.quiz_payload, 'opens_at': (timezone.now() + timedelta(days=1)).isoformat()}
        quiz_id = self.client.post('/api/v1/quizzes/', payload, format='json').json()['id']

        self.auth(self.child_token)
        self.assertEqual(self.client.get(f'/api/v1/quizzes/{quiz_id}/').status_code, 404)

        self.auth(self.teacher_token)
        self.assertEqual(self.client.get(f'/api/v1/quizzes/{quiz_id}/').status_code, 200)

    def test_future_quiz_does_not_notify_yet(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.notifications.models import Notification

        self.enroll_child()
        self.auth(self.teacher_token)
        payload = {**self.quiz_payload, 'opens_at': (timezone.now() + timedelta(days=1)).isoformat()}
        self.client.post('/api/v1/quizzes/', payload, format='json')
        self.assertFalse(Notification.objects.filter(link_type='quiz').exists())
