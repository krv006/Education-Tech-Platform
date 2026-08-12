from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0002_backfill_course_rooms'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='file',
            field=models.FileField(blank=True, upload_to='chat_files/'),
        ),
    ]
