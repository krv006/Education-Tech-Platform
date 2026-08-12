from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0003_message_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatroom',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='group_images/'),
        ),
    ]
