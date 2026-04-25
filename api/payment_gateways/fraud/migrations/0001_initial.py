# FILE 88 of 257 — fraud/migrations/0001_initial.py
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='BlockedIP', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('ip_address', models.GenericIPAddressField(unique=True)),
            ('reason', models.TextField()),
            ('is_active', models.BooleanField(default=True)),
            ('expires_at', models.DateTimeField(null=True, blank=True)),
            ('blocked_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL,
                           related_name='blocked_ips', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name':'Blocked IP'}),
        migrations.CreateModel(name='RiskRule', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('name', models.CharField(max_length=100, unique=True)),
            ('description', models.TextField(blank=True)),
            ('condition_type', models.CharField(max_length=30)),
            ('condition_value', models.CharField(max_length=200)),
            ('score', models.IntegerField()),
            ('reason', models.CharField(max_length=255)),
            ('priority', models.IntegerField(default=100)),
            ('is_active', models.BooleanField(default=True)),
        ], options={'verbose_name':'Risk Rule','ordering':['priority']}),
        migrations.CreateModel(name='FraudAlert', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('gateway', models.CharField(max_length=20)),
            ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('ip_address', models.GenericIPAddressField(null=True, blank=True)),
            ('risk_score', models.IntegerField()),
            ('risk_level', models.CharField(max_length=10)),
            ('action', models.CharField(max_length=10)),
            ('reasons', models.JSONField(default=list)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('resolved', models.BooleanField(default=False)),
            ('resolved_at', models.DateTimeField(null=True, blank=True)),
            ('notes', models.TextField(blank=True, null=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fraud_alerts', to=settings.AUTH_USER_MODEL)),
            ('resolved_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_fraud_alerts', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name':'Fraud Alert','ordering':['-created_at']}),
    ]
