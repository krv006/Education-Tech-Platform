"""Mavjud kurslar uchun guruh chatlarni yaratish (yangi kurslar service'da oladi)."""
from django.db import migrations


def create_rooms(apps, schema_editor):
    Course = apps.get_model('lessons', 'Course')
    ChatRoom = apps.get_model('chat', 'ChatRoom')
    for course in Course.objects.filter(is_deleted=False):
        ChatRoom.objects.get_or_create(kind='course', course=course)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0001_initial'),
        ('lessons', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_rooms, noop),
    ]
