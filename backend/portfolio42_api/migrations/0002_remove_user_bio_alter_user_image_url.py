# Generated by Django 4.2 on 2023-05-03 12:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio42_api', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='bio',
        ),
        migrations.AlterField(
            model_name='user',
            name='image_url',
            field=models.CharField(max_length=800),
        ),
    ]
