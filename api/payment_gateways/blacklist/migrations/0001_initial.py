# blacklist/migrations/0001_initial.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='TrafficBlacklist', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('block_type', models.CharField(max_length=15)),
            ('value', models.CharField(max_length=500)),
            ('reason', models.TextField(blank=True)),
            ('created_by_type', models.CharField(max_length=15, default='advertiser')),
            ('is_active', models.BooleanField(default=True)),
            ('expires_at', models.DateTimeField(null=True, blank=True)),
            ('block_count', models.IntegerField(default=0)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                      related_name='blacklist_entries', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Traffic Blacklist'}),
        migrations.CreateModel(name='OfferQualityScore', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('total_clicks', models.IntegerField(default=0)),
            ('total_conversions', models.IntegerField(default=0)),
            ('conversion_rate', models.DecimalField(max_digits=7, decimal_places=4, default=0)),
            ('fraud_rate', models.DecimalField(max_digits=7, decimal_places=4, default=0)),
            ('quality_score', models.IntegerField(default=100)),
            ('is_blacklisted', models.BooleanField(default=False)),
            ('blacklisted_at', models.DateTimeField(null=True, blank=True)),
            ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                          related_name='quality_scores', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Offer Quality Score'}),
    ]
