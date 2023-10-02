# Generated by Django 4.2.5 on 2023-09-28 12:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RefreshToken',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('token', models.CharField(editable=False, max_length=255, verbose_name='token')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('revoked', models.DateTimeField(blank=True, null=True, verbose_name='revoked')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refresh_tokens', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'refresh token',
                'verbose_name_plural': 'refresh tokens',
                'abstract': False,
                'unique_together': {('token', 'revoked')},
            },
        ),
    ]
