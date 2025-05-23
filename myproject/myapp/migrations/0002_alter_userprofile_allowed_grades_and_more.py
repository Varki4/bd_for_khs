# Generated by Django 5.1.1 on 2025-02-01 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='allowed_grades',
            field=models.CharField(blank=True, default='', help_text='Классы, доступные для просмотра (через запятую)', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='allowed_tables',
            field=models.CharField(blank=True, default='', help_text='Доступные таблицы (cadets и/или employees)', max_length=255, null=True),
        ),
    ]
