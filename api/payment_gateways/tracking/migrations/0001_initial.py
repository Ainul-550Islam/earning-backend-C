# tracking/migrations/0001_initial.py
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

def gen_click_id():
    return uuid.uuid4().hex

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Click', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('click_id', models.CharField(max_length=64, unique=True, default=gen_click_id)),
            ('ip_address', models.GenericIPAddressField(null=True, blank=True)),
            ('user_agent', models.TextField(blank=True)),
            ('country_code', models.CharField(max_length=2, blank=True)),
            ('device_type', models.CharField(max_length=20, blank=True)),
            ('os_name', models.CharField(max_length=50, blank=True)),
            ('is_bot', models.BooleanField(default=False)),
            ('is_duplicate', models.BooleanField(default=False)),
            ('is_fraud', models.BooleanField(default=False)),
            ('is_converted', models.BooleanField(default=False)),
            ('converted_at', models.DateTimeField(null=True, blank=True)),
            ('sub1', models.CharField(max_length=255, blank=True)),
            ('sub2', models.CharField(max_length=255, blank=True)),
            ('sub3', models.CharField(max_length=255, blank=True)),
            ('payout', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('publisher', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                          related_name='tracking_clicks', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Click', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='Conversion', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('conversion_id', models.CharField(max_length=64, unique=True, default=gen_click_id)),
            ('click_id_raw', models.CharField(max_length=64, blank=True)),
            ('conversion_type', models.CharField(max_length=20, default='action')),
            ('status', models.CharField(max_length=15, default='pending')),
            ('payout', models.DecimalField(max_digits=10, decimal_places=4)),
            ('cost', models.DecimalField(max_digits=10, decimal_places=4)),
            ('revenue', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('country_code', models.CharField(max_length=2, blank=True)),
            ('publisher_paid', models.BooleanField(default=False)),
            ('postback_received', models.BooleanField(default=False)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('click', models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL,
                      related_name='conversion', to='payment_gateways_tracking.click')),
            ('publisher', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                          related_name='conversions', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Conversion', 'ordering': ['-created_at']}),
    ]
