# locker/migrations/0001_initial.py
import django.db.models.deletion
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

def gen_key():
    return uuid.uuid4().hex[:16].upper()

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payment_gateways_offers', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(name='ContentLocker', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('locker_type', models.CharField(max_length=15, default='url_locker')),
            ('status', models.CharField(max_length=10, default='active')),
            ('locker_key', models.CharField(max_length=20, unique=True, default=gen_key)),
            ('destination_url', models.URLField(max_length=2000, blank=True)),
            ('title', models.CharField(max_length=200, default='Complete an offer to unlock')),
            ('description', models.TextField(blank=True)),
            ('theme', models.CharField(max_length=20, default='default')),
            ('primary_color', models.CharField(max_length=7, default='#635BFF')),
            ('unlock_duration_hours', models.CharField(max_length=10, default='24')),
            ('show_offer_count', models.IntegerField(default=1)),
            ('total_impressions', models.BigIntegerField(default=0)),
            ('total_unlocks', models.BigIntegerField(default=0)),
            ('total_earnings', models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                          related_name='content_lockers', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Content Locker', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='OfferWall', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=200)),
            ('status', models.CharField(max_length=10, default='active')),
            ('wall_key', models.CharField(max_length=20, unique=True, default=gen_key)),
            ('currency_name', models.CharField(max_length=50, default='Coins')),
            ('exchange_rate', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('100'))),
            ('title', models.CharField(max_length=200, default='Earn rewards')),
            ('description', models.TextField(blank=True)),
            ('theme', models.CharField(max_length=20, default='default')),
            ('primary_color', models.CharField(max_length=7, default='#635BFF')),
            ('android_app_id', models.CharField(max_length=200, blank=True)),
            ('postback_url', models.URLField(max_length=2000, blank=True)),
            ('target_countries', models.JSONField(default=list, blank=True)),
            ('total_completions', models.BigIntegerField(default=0)),
            ('total_earnings', models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                          related_name='offer_walls', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Offer Wall', 'ordering': ['-created_at']}),
        migrations.CreateModel(name='UserVirtualBalance', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('balance', models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))),
            ('total_earned', models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))),
            ('total_spent', models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='virtual_balances', to=settings.AUTH_USER_MODEL)),
            ('offer_wall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                           related_name='user_balances', to='payment_gateways_locker.offerwall')),
        ], options={'verbose_name': 'User Virtual Balance', 'unique_together': {('user','offer_wall')}}),
        migrations.CreateModel(name='VirtualReward', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('reward_type', models.CharField(max_length=15, default='earned')),
            ('amount', models.DecimalField(max_digits=12, decimal_places=2)),
            ('usd_equivalent', models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))),
            ('description', models.CharField(max_length=200, blank=True)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='virtual_rewards', to=settings.AUTH_USER_MODEL)),
            ('offer_wall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                           related_name='rewards', to='payment_gateways_locker.offerwall')),
        ], options={'verbose_name': 'Virtual Reward', 'ordering': ['-created_at']}),
    ]
