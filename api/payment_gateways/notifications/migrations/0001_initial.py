# notifications/migrations/0001_initial.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='InAppNotification', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('notification_type', models.CharField(max_length=50)),
            ('title', models.CharField(max_length=200)),
            ('message', models.TextField()),
            ('is_read', models.BooleanField(default=False)),
            ('read_at', models.DateTimeField(null=True, blank=True)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='payment_notifications', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'In-App Notification', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='DeviceToken', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('token', models.TextField(unique=True)),
            ('platform', models.CharField(max_length=10,
                choices=[('ios','iOS'),('android','Android'),('web','Web')])),
            ('is_active', models.BooleanField(default=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='device_tokens', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Device Token'}),
    ]
