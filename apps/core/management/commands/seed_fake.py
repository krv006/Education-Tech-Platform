"""To'liq fake ma'lumot — demo/sinov uchun.

    python manage.py seed_fake

Hisoblar (parol hammasiga: 1):
  teacher  — O'qituvchi (Malika Karimova)
  perents  — Ota-ona (Aziz Aliyev)
  student  — O'quvchi (Sardor, perents'ga bog'langan)
  + qo'shimcha o'quvchilar: nilufar, dilnoza, madina, jasur (parol: 1)

Qayta ishga tushirsa eski fake ma'lumotni o'chirib, yangidan yaratadi (idempotent).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Consent, ParentChildLink, User
from apps.lessons.models import Attendance, Course, Enrollment, Lesson

PASSWORD = '1'
USERNAMES = ['teacher', 'perents', 'student', 'nilufar', 'dilnoza', 'madina', 'jasur']


def make_user(username, role, first_name='', last_name='', phone=None):
    user = User(username=username, role=role, first_name=first_name, last_name=last_name, phone=phone)
    user.set_password(PASSWORD)  # to'g'ridan-to'g'ri saqlash — parol validatsiyasi API'da, bu yerda emas
    user.save()
    return user


class Command(BaseCommand):
    help = "Fake foydalanuvchilar va to'liq demo ma'lumot yaratadi (teacher/perents/student, parol: 1)."

    def handle(self, *args, **options):
        # eski fake/demo ma'lumotni tozalash
        User.objects.filter(username__in=USERNAMES).delete()
        User.objects.filter(username__startswith='demo_').delete()
        Course.all_objects.filter(teacher__isnull=True).delete()

        now = timezone.now()

        # ── foydalanuvchilar ──
        teacher = make_user('teacher', User.Role.TEACHER, 'Malika', 'Karimova', '+998901234567')
        parent = make_user('perents', User.Role.PARENT, 'Aziz', 'Aliyev', '+998907654321')
        student = make_user('student', User.Role.STUDENT, 'Sardor', 'Aliyev')
        others = [
            make_user('nilufar', User.Role.STUDENT, 'Nilufar', 'Rahimova'),
            make_user('dilnoza', User.Role.STUDENT, 'Dilnoza', 'Karimova'),
            make_user('madina', User.Role.STUDENT, 'Madina', 'Tosheva'),
            make_user('jasur', User.Role.STUDENT, 'Jasur', 'Bekov'),
        ]

        # ── ota-ona ↔ bola (tasdiqlangan — rozilik oqimi o'tilgan) ──
        ParentChildLink.objects.create(
            parent=parent, student=student,
            status=ParentChildLink.Status.APPROVED, responded_at=now,
        )
        for kind in (Consent.Kind.ANALYTICS, Consent.Kind.RECORDING):
            Consent.objects.create(student=student, granted_by=parent, kind=kind, granted=True)

        # ── kurslar ──
        algebra = Course.objects.create(
            teacher=teacher, title='Algebra · 7-sinf', subject='Matematika',
            description='Kvadrat tenglamalar, funksiyalar va grafiklar',
        )
        english = Course.objects.create(
            teacher=teacher, title="Ingliz tili · Boshlang'ich", subject='Ingliz tili',
            description='Grammatika va so\'zlashuv asoslari',
        )

        all_students = [student] + others
        for s in all_students:
            Enrollment.objects.create(course=algebra, student=s)
        for s in all_students[:3]:
            Enrollment.objects.create(course=english, student=s)

        # ── o'tgan hafta darslari (tugagan, davomat bilan) ──
        topics = [
            'Kvadrat tenglamalar — kirish',
            'Diskriminant va ildizlar',
            'Vieta teoremasi',
            'Funksiya grafigi',
            'Takrorlash va test',
        ]
        for i, topic in enumerate(topics):
            starts = now - timedelta(days=len(topics) - i, hours=2)
            lesson = Lesson.objects.create(
                course=algebra, title=topic, starts_at=starts,
                duration_min=45, status=Lesson.Status.FINISHED,
            )
            for j, s in enumerate(all_students):
                if s.username == 'jasur' and i % 2 == 0:
                    continue  # Jasur ba'zi darslarni qoldirgan — hisobotda ko'rinsin
                joined = starts + timedelta(minutes=2 + j)
                left = starts + timedelta(minutes=40 + (j % 5))
                Attendance.objects.create(lesson=lesson, student=s, joined_at=joined, left_at=left)

        # ── hozir jonli dars ──
        live = Lesson.objects.create(
            course=algebra, title='Kvadrat tenglamalar — amaliyot',
            starts_at=now - timedelta(minutes=15), duration_min=45, status=Lesson.Status.LIVE,
        )
        Attendance.objects.create(
            lesson=live, student=student, joined_at=now - timedelta(minutes=12),
        )

        # ── kelgusi darslar ──
        for days, (course, topic) in enumerate([
            (algebra, "Chiziqli tenglamalar tizimi"),
            (english, 'Present Simple — amaliyot'),
            (algebra, 'Nazorat ishi'),
        ], start=1):
            Lesson.objects.create(
                course=course, title=topic,
                starts_at=now + timedelta(days=days, hours=3), duration_min=45,
            )

        self.stdout.write(self.style.SUCCESS(
            'Fake ma\'lumot tayyor (parol hammasiga: 1):\n'
            '  teacher  — O\'qituvchi (Malika Karimova)\n'
            '  perents  — Ota-ona (Aziz Aliyev)\n'
            f'  student  — O\'quvchi Sardor (taklif kodi: {student.invite_code})\n'
            '  nilufar / dilnoza / madina / jasur — qo\'shimcha o\'quvchilar\n'
            f'Kurslar: 2 · Darslar: {Lesson.objects.count()} (5 tugagan, 1 jonli, 3 kelgusi) · '
            f'Davomat yozuvlari: {Attendance.objects.count()}'
        ))
