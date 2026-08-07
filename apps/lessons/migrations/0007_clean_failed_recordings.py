# Tarixiy tozalash: 401/xona-xatosi davridagi FAILED yozuv qatorlari
# (fayllari yo'q, error matnlari xom SDK satrlari) — o'chiriladi.
# Yangi failed'lar endi do'stona o'zbekcha matn bilan yoziladi
# (apps/live/services._friendly_egress_error).
from django.db import migrations


def clean_failed_recordings(apps, schema_editor):
    LessonRecording = apps.get_model('lessons', 'LessonRecording')
    LessonRecording.objects.filter(status='failed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0006_alter_lessonrecording_status'),
    ]

    operations = [
        migrations.RunPython(clean_failed_recordings, migrations.RunPython.noop),
    ]
