from rest_framework.test import APITestCase

from .models import ParentChildLink, User

PASSWORD = 'StrongPass123!'


def register(client, username, role, **extra):
    return client.post('/api/v1/auth/register/', {
        'username': username, 'password': PASSWORD, 'role': role, **extra,
    })


def login(client, username):
    resp = client.post('/api/v1/auth/login/', {'username': username, 'password': PASSWORD})
    return resp.json()['access']


class AuthTests(APITestCase):
    def test_register_and_login_teacher(self):
        resp = register(self.client, 'teacher1', 'teacher')
        self.assertEqual(resp.status_code, 201)
        token = login(self.client, 'teacher1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me.json()['role'], 'teacher')

    def test_student_cannot_register_publicly(self):
        resp = register(self.client, 'student1', 'student')
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertFalse(body['success'])
        self.assertIn('error', body)

    def test_error_envelope_shape(self):
        resp = self.client.post('/api/v1/auth/login/', {'username': 'nobody', 'password': 'x'})
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self.assertFalse(body['success'])
        self.assertIn('code', body['error'])
        self.assertIn('message', body['error'])


class LinkFlowTests(APITestCase):
    def setUp(self):
        register(self.client, 'parent1', 'parent')
        self.parent_token = login(self.client, 'parent1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        resp = self.client.post('/api/v1/auth/children/', {
            'username': 'child1', 'password': PASSWORD, 'first_name': 'Sardor',
        })
        self.invite_code = resp.json()['invite_code']
        self.child_token = login(self.client, 'child1')

    def test_child_create_gives_approved_link(self):
        link = ParentChildLink.objects.get(parent__username='parent1', student__username='child1')
        self.assertEqual(link.status, ParentChildLink.Status.APPROVED)
        self.assertTrue(self.invite_code.startswith('FK-'))

    def test_invite_code_flow_approve_and_revoke(self):
        register(self.client, 'parent2', 'parent')
        parent2_token = login(self.client, 'parent2')

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {parent2_token}')
        resp = self.client.post('/api/v1/auth/links/request/', {'invite_code': self.invite_code})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['status'], 'pending')
        link_id = resp.json()['id']

        # student approves
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.child_token}')
        resp = self.client.post(f'/api/v1/auth/links/{link_id}/respond/', {'action': 'approve'})
        self.assertEqual(resp.json()['status'], 'approved')

        # student revokes any time (consent model)
        resp = self.client.post(f'/api/v1/auth/links/{link_id}/respond/', {'action': 'decline'})
        self.assertEqual(resp.json()['status'], 'declined')

    def test_wrong_invite_code_404(self):
        register(self.client, 'parent3', 'parent')
        token = login(self.client, 'parent3')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self.client.post('/api/v1/auth/links/request/', {'invite_code': 'FK-XXXX'})
        self.assertEqual(resp.status_code, 404)

    def test_consent_requires_approved_link(self):
        register(self.client, 'parent4', 'parent')
        token = login(self.client, 'parent4')
        child_id = User.objects.get(username='child1').id
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self.client.post('/api/v1/auth/consents/', {
            'student': child_id, 'kind': 'analytics', 'granted': True,
        })
        self.assertEqual(resp.status_code, 403)

        # linked parent CAN set consent
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        resp = self.client.post('/api/v1/auth/consents/', {
            'student': child_id, 'kind': 'analytics', 'granted': True,
        })
        self.assertEqual(resp.status_code, 201)

    def test_student_cannot_create_child(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.child_token}')
        resp = self.client.post('/api/v1/auth/children/', {
            'username': 'child2', 'password': PASSWORD,
        })
        self.assertEqual(resp.status_code, 403)


class LoginJournalTests(APITestCase):
    """Login jurnali: IP/qurilma o'zgarishi bayroqlari va tarix endpointi."""

    def setUp(self):
        register(self.client, 'lj_p', 'parent')
        self.parent_token = login(self.client, 'lj_p')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        self.child_id = self.client.post(
            '/api/v1/auth/children/', {'username': 'lj_s', 'password': PASSWORD},
        ).json()['id']
        self.client.credentials()

    def _login(self, username, ua):
        return self.client.post(
            '/api/v1/auth/login/', {'username': username, 'password': PASSWORD},
            HTTP_USER_AGENT=ua,
        )

    def test_new_device_flagged(self):
        self._login('lj_s', 'Chrome/Telefon')
        self._login('lj_s', 'Chrome/Telefon')
        self._login('lj_s', 'Firefox/Kompyuter')  # qurilma o'zgardi

        token = self._login('lj_s', 'Firefox/Kompyuter').json()['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        rows = self.client.get('/api/v1/auth/logins/').json()
        self.assertGreaterEqual(len(rows), 4)
        # rows[1] — Firefox'ga o'tgan login (eng oxirgisi rows[0])
        self.assertTrue(rows[1]['new_device'])
        self.assertFalse(rows[2]['new_device'])  # Chrome -> Chrome

    def test_parent_sees_child_logins_stranger_not(self):
        self._login('lj_s', 'Chrome/Telefon')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.parent_token}')
        rows = self.client.get(f'/api/v1/auth/logins/?student={self.child_id}').json()
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn('user_agent', rows[0])

        register(self.client, 'lj_p2', 'parent')
        p2 = login(self.client, 'lj_p2')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {p2}')
        r = self.client.get(f'/api/v1/auth/logins/?student={self.child_id}')
        self.assertEqual(r.status_code, 403)
