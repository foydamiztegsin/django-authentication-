# Generated by Django 4.1.5 on 2023-01-26 17:26

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_alter_user_auth_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='bio',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True, validators=[django.core.validators.RegexValidator(message='Telefon raqamingiz 9 bilan boshlanishi va 12 ta belgidan oshmasligi lozim. Masalan: 998993451545', regex='^9\\d{12}$')]),
        ),
        migrations.AlterField(
            model_name='user',
            name='sex',
            field=models.CharField(blank=True, choices=[('male', 'male'), ('female', 'female')], max_length=20, null=True),
        ),
    ]
