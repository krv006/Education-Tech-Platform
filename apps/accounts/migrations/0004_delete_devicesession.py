# "Bitta akkaunt = bitta qurilma" cheklovi olib tashlandi — endi istalgancha
# qurilmadan bir vaqtda kirish mumkin, DeviceSession jadvali kerak emas.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_devicesession'),
    ]

    operations = [
        migrations.DeleteModel(name='DeviceSession'),
    ]
