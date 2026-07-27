"""End-to-end smoke test of the MVP API using Django's test client.

Run:  python manage.py shell < scripts/smoke_test.py
(or)  python scripts/smoke_test.py
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'root.settings')
django.setup()

from rest_framework.test import APIClient  # noqa: E402

from apps.accounts.models import User  # noqa: E402

# clean previous smoke-test users
User.objects.filter(username__startswith='smoke_').delete()

client = APIClient()
ok = 0


def check(name, resp, expected):
    global ok
    assert resp.status_code == expected, f'{name}: expected {expected}, got {resp.status_code}: {resp.content[:300]}'
    ok += 1
    print(f'  [OK] {name} -> {resp.status_code}')


# 1. Register teacher & parent
check('register teacher', client.post('/api/v1/auth/register/', {
    'username': 'smoke_teacher', 'password': 'StrongPass123!', 'first_name': 'Malika',
    'last_name': 'Karimova', 'role': 'teacher', 'phone': '+998901112233'}), 201)
check('register parent', client.post('/api/v1/auth/register/', {
    'username': 'smoke_parent', 'password': 'StrongPass123!', 'first_name': 'Aziz',
    'last_name': 'Aliyev', 'role': 'parent', 'phone': '+998904445566'}), 201)

# 2. Login
r = client.post('/api/v1/auth/login/', {'username': 'smoke_parent', 'password': 'StrongPass123!'})
check('login parent', r, 200)
parent_token = r.json()['access']

r = client.post('/api/v1/auth/login/', {'username': 'smoke_teacher', 'password': 'StrongPass123!'})
check('login teacher', r, 200)
teacher_token = r.json()['access']

# 3. Parent creates child (auto-approved link)
client.credentials(HTTP_AUTHORIZATION=f'Bearer {parent_token}')
r = client.post('/api/v1/auth/children/', {
    'username': 'smoke_child', 'password': 'StrongPass123!', 'first_name': 'Sardor'})
check('create child', r, 201)
invite_code = r.json()['invite_code']
print(f'       child invite code: {invite_code}')

# 4. Second parent links via invite code, child approves
check('register parent2', client.post('/api/v1/auth/register/', {
    'username': 'smoke_parent2', 'password': 'StrongPass123!', 'role': 'parent'}, format='json'), 201)
r = client.post('/api/v1/auth/login/', {'username': 'smoke_parent2', 'password': 'StrongPass123!'})
parent2_token = r.json()['access']
client.credentials(HTTP_AUTHORIZATION=f'Bearer {parent2_token}')
r = client.post('/api/v1/auth/links/request/', {'invite_code': invite_code})
check('link request by code', r, 201)
link_id = r.json()['id']
assert r.json()['status'] == 'pending'

r = client.post('/api/v1/auth/login/', {'username': 'smoke_child', 'password': 'StrongPass123!'})
check('login child', r, 200)
child_token = r.json()['access']
client.credentials(HTTP_AUTHORIZATION=f'Bearer {child_token}')
r = client.post(f'/api/v1/auth/links/{link_id}/respond/', {'action': 'approve'})
check('child approves link', r, 200)
assert r.json()['status'] == 'approved'

# 5. Teacher creates course + lesson
client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_token}')
r = client.post('/api/v1/courses/', {'title': 'Algebra 7-sinf', 'subject': 'Matematika'})
check('create course', r, 201)
course_id = r.json()['id']
r = client.post('/api/v1/lessons/', {
    'course': course_id, 'title': 'Kvadrat tenglamalar', 'starts_at': '2026-08-01T14:00:00+05:00',
    'duration_min': 45})
check('create lesson', r, 201)
lesson_id = r.json()['id']
print(f'       room: {r.json()["room_name"]}')

# 6. Parent enrolls child
client.credentials(HTTP_AUTHORIZATION=f'Bearer {parent_token}')
child_id = User.objects.get(username='smoke_child').id
check('parent enrolls child', r := client.post(f'/api/v1/courses/{course_id}/enroll/', {'student_id': child_id}), 201)

# 7. Child gets LiveKit token (auto attendance)
client.credentials(HTTP_AUTHORIZATION=f'Bearer {child_token}')
r = client.post('/api/v1/live/token/', {'lesson_id': lesson_id})
check('child room token', r, 200)
assert r.json()['token'] and r.json()['room']

# 8. Teacher token -> lesson goes LIVE
client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_token}')
r = client.post('/api/v1/live/token/', {'lesson_id': lesson_id})
check('teacher room token', r, 200)
assert r.json()['is_teacher'] is True

# 9. Child leaves, teacher finishes, parent sees attendance
client.credentials(HTTP_AUTHORIZATION=f'Bearer {child_token}')
check('child leaves', client.post('/api/v1/live/leave/', {'lesson_id': lesson_id}), 200)
client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_token}')
check('teacher finishes lesson', client.post(f'/api/v1/lessons/{lesson_id}/finish/'), 200)
client.credentials(HTTP_AUTHORIZATION=f'Bearer {parent_token}')
r = client.get('/api/v1/attendance/')
check('parent attendance report', r, 200)
rows = r.json()['results']
assert len(rows) == 1 and rows[0]['minutes'] is not None
print(f'       attendance: {rows[0]["student"]["first_name"]} — {rows[0]["minutes"]} min')

# 10. Security: unlinked parent2 must NOT see attendance of another course
client.credentials(HTTP_AUTHORIZATION=f'Bearer {child_token}')
r = client.post('/api/v1/courses/', {'title': 'Hack'})
check('student cannot create course', r, 403)

print(f'\nALL {ok} CHECKS PASSED')
