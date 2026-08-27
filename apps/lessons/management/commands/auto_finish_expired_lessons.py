"""Vaqti tugagan (starts_at + duration_min o'tib ketgan), lekin hali LIVE
holatda qolib ketgan darslarni avtomatik yakunlaydi.

    python manage.py auto_finish_expired_lessons

Loyihada Celery/Celery Beat yo'q — shu buyruq server crontab'ida (yoki
docker-compose'da alohida yengil cron konteynerida) har 5-10 daqiqada bir
ishga tushirilishi kerak (send_deadline_reminders bilan bir xil naqsh).
"""
from django.core.management.base import BaseCommand

from apps.lessons import services


class Command(BaseCommand):
    help = "Rejalashtirilgan vaqti tugagan, lekin hali LIVE qolgan darslarni yakunlaydi va video xonasini o'chiradi."

    def handle(self, *args, **options):
        count = services.auto_finish_expired_lessons()
        self.stdout.write(self.style.SUCCESS(f'Yakunlangan darslar: {count}'))
