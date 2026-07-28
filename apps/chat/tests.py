"""Chat oqimi testlari — guruh, direct so'rov/qabul/block, ruxsatlar."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import ChatRoom
from apps.lessons.models import Course, Enrollment

from . import services


def make(username, role):
    u = User(username=username, role=role)
    u.set_password('x')
    u.save()
    return u


class ChatFlowTests(TestCase):
    def setUp(self):
        self.teacher = make('t1', User.Role.TEACHER)
        self.student = make('s1', User.Role.STUDENT)
        self.stranger = make('s2', User.Role.STUDENT)
        self.course = Course.objects.create(teacher=self.teacher, title='Algebra')
        services.ensure_course_room(self.course)
        Enrollment.objects.create(
            course=self.course, student=self.student, status=Enrollment.Status.APPROVED,
        )
        self.client = APIClient()

    def api(self, user):
        self.client.force_authenticate(user)
        return self.client

    def test_course_room_visible_to_members_only(self):
        r = self.api(self.teacher).get('/api/v1/chat/rooms/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['results']), 1)
        r = self.api(self.stranger).get('/api/v1/chat/rooms/')
        self.assertEqual(len(r.data['results']), 0)

    def test_send_and_read_group_message(self):
        room = self.course.chat_room
        r = self.api(self.student).post(f'/api/v1/chat/rooms/{room.id}/send/', {'text': 'Salom!'})
        self.assertEqual(r.status_code, 201)
        r = self.api(self.teacher).get(f'/api/v1/chat/rooms/{room.id}/messages/')
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['text'], 'Salom!')

    def test_stranger_cannot_write_group(self):
        room = self.course.chat_room
        r = self.api(self.stranger).post(f'/api/v1/chat/rooms/{room.id}/send/', {'text': 'hey'})
        self.assertEqual(r.status_code, 403)

    def test_direct_request_flow(self):
        # so'rov -> pending, yozib bo'lmaydi
        r = self.api(self.student).post('/api/v1/chat/rooms/direct/request/', {'teacher': 't1'})
        self.assertEqual(r.status_code, 201)
        room_id = r.data['id']
        r = self.api(self.student).post(f'/api/v1/chat/rooms/{room_id}/send/', {'text': 'salom'})
        self.assertEqual(r.status_code, 403)
        # o'qituvchi qabul qildi -> yoziladi
        self.api(self.teacher).post(
            '/api/v1/chat/rooms/direct/respond/', {'room_id': room_id, 'action': 'accept'},
        )
        r = self.api(self.student).post(f'/api/v1/chat/rooms/{room_id}/send/', {'text': 'salom'})
        self.assertEqual(r.status_code, 201)
        # block -> yana yozib bo'lmaydi
        self.api(self.teacher).post(
            '/api/v1/chat/rooms/direct/respond/', {'room_id': room_id, 'action': 'block'},
        )
        r = self.api(self.student).post(f'/api/v1/chat/rooms/{room_id}/send/', {'text': 'salom'})
        self.assertEqual(r.status_code, 403)
        # qayta so'rov -> pending
        r = self.api(self.student).post('/api/v1/chat/rooms/direct/request/', {'teacher': 't1'})
        self.assertEqual(r.data['direct_status'], ChatRoom.DirectStatus.PENDING)

    def test_student_cannot_request_foreign_teacher(self):
        other = make('t2', User.Role.TEACHER)
        r = self.api(self.student).post('/api/v1/chat/rooms/direct/request/', {'teacher': other.username})
        self.assertEqual(r.status_code, 403)

    def test_parent_has_no_chat(self):
        parent = make('p1', User.Role.PARENT)
        r = self.api(parent).get('/api/v1/chat/rooms/')
        self.assertEqual(r.status_code, 403)
