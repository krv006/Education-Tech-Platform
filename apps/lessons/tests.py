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
        self.lesson_id = self.client.post('/api/v1/lessons/', {
            'course': self.course_id, 'title': 'Dars 1',
            'starts_at': '2026-08-01T14:00:00+05:00', 'duration_min': 45,
        }).json()['id']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_student_cannot_create_course(self):
        self.auth(self.child_token)
        resp = self.client.post('/api/v1/courses/', {'title': 'Hack'})
        self.assertEqual(resp.status_code, 403)

    def test_parent_enrolls_linked_child_only(self):
        self.auth(self.parent_token)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.assertEqual(resp.status_code, 201)

        # another parent with no link cannot enroll this child
        register(self.client, 'p2', 'parent')
        p2 = login(self.client, 'p2')
        self.auth(p2)
        resp = self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})
        self.assertEqual(resp.status_code, 403)

    def test_room_token_flow_and_attendance(self):
        self.auth(self.parent_token)
        self.client.post(f'/api/v1/courses/{self.course_id}/enroll/', {'student_id': self.child_id})

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
