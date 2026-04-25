# integrations/migrations/0001_initial.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name='AdvertiserTrackerIntegration', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('tracker', models.CharField(max_length=20)),
            ('app_id', models.CharField(max_length=200)),
            ('dev_key', models.CharField(max_length=200, blank=True)),
            ('is_active', models.BooleanField(default=True)),
            ('postback_url', models.URLField(max_length=2000, blank=True)),
            ('advertiser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                           related_name='tracker_integrations', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Advertiser Tracker Integration'}),
    ]
