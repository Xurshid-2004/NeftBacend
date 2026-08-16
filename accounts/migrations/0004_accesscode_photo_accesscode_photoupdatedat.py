from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_facetemplate_staff_photo_staff_photoupdatedat'),
    ]

    operations = [
        migrations.AddField(
            model_name='accesscode',
            name='photo',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='accesscode',
            name='photoUpdatedAt',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
