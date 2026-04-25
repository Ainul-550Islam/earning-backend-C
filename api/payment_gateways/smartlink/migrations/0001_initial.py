# smartlink/migrations/0001_initial.py
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

def gen_key(): return uuid.uuid4().hex[:12].upper()

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='SmartLink', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('slug', models.CharField(max_length=20, unique=True, default=gen_key)),
            ('status', models.CharField(max_length=10, default='active')),
            ('rotation_mode', models.CharField(max_length=20, default='epc_optimized')),
            ('offer_types', models.JSONField(default=list, blank=True)),
            ('categories', models.JSONField(default=list, blank=True)),
            ('min_payout', models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)),
            ('target_countries', models.JSONField(default=list, blank=True)),
            ('target_devices', models.JSONField(default=list, blank=True)),
            ('fallback_url', models.URLField(max_length=2000, blank=True)),
            ('total_clicks', models.BigIntegerField(default=0)),
            ('total_conversions', models.BigIntegerField(default=0)),
            ('total_earnings', models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))),
            ('epc', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                          related_name='smart_links', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Smart Link', 'ordering': ['-created_at']}),
    ]
