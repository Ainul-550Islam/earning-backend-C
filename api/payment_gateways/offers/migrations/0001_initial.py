# offers/migrations/0001_initial.py
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Offer', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('slug', models.SlugField(max_length=220, unique=True, blank=True)),
            ('description', models.TextField(blank=True)),
            ('short_desc', models.CharField(max_length=500, blank=True)),
            ('offer_type', models.CharField(max_length=5, default='cpa')),
            ('status', models.CharField(max_length=10, default='draft')),
            ('destination_url', models.URLField(max_length=2000)),
            ('tracking_url', models.URLField(max_length=2000, blank=True)),
            ('preview_url', models.URLField(max_length=2000, blank=True)),
            ('postback_url', models.URLField(max_length=2000, blank=True)),
            ('publisher_postback_url', models.URLField(max_length=2000, blank=True)),
            ('publisher_payout', models.DecimalField(max_digits=10, decimal_places=4)),
            ('advertiser_cost', models.DecimalField(max_digits=10, decimal_places=4)),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('payout_model', models.CharField(max_length=10, default='fixed')),
            ('target_countries', models.JSONField(default=list, blank=True)),
            ('blocked_countries', models.JSONField(default=list, blank=True)),
            ('target_devices', models.JSONField(default=list, blank=True)),
            ('target_os', models.JSONField(default=list, blank=True)),
            ('daily_cap', models.IntegerField(null=True, blank=True)),
            ('total_cap', models.IntegerField(null=True, blank=True)),
            ('category', models.CharField(max_length=100, blank=True)),
            ('is_public', models.BooleanField(default=True)),
            ('requires_approval', models.BooleanField(default=False)),
            ('total_clicks', models.BigIntegerField(default=0)),
            ('total_conversions', models.BigIntegerField(default=0)),
            ('epc', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('advertiser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                           related_name='advertiser_offers', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Offer', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='Campaign', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('status', models.CharField(max_length=10, default='draft')),
            ('total_budget', models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)),
            ('spent', models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('total_clicks', models.BigIntegerField(default=0)),
            ('total_conversions', models.BigIntegerField(default=0)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('advertiser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                           related_name='campaigns', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Campaign', 'ordering': ['-created_at']}),
    ]
