# migrations/0003_exchange_rates.py
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [('localization', '0002_geo_currency')]
    operations = [
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rate', models.DecimalField(max_digits=20, decimal_places=10)),
                ('bid_rate', models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)),
                ('ask_rate', models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)),
                ('date', models.DateField(db_index=True)),
                ('fetched_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.CharField(max_length=50, default='manual')),
                ('is_official', models.BooleanField(default=False)),
                ('change_percent', models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)),
                ('raw_response', models.JSONField(default=dict, blank=True)),
                ('from_currency', models.ForeignKey('localization.currency', on_delete=django.db.models.deletion.CASCADE, related_name='rates_from')),
                ('to_currency', models.ForeignKey('localization.currency', on_delete=django.db.models.deletion.CASCADE, related_name='rates_to')),
            ],
            options={'verbose_name': 'Exchange Rate', 'ordering': ['-date', '-fetched_at']},
        ),
        migrations.CreateModel(
            name='ExchangeRateProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('provider_type', models.CharField(max_length=50)),
                ('api_key', models.CharField(max_length=500, blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('fetch_interval_minutes', models.PositiveIntegerField(default=60)),
                ('last_fetch_at', models.DateTimeField(null=True, blank=True)),
                ('last_success_at', models.DateTimeField(null=True, blank=True)),
                ('total_requests', models.PositiveIntegerField(default=0)),
                ('failed_requests', models.PositiveIntegerField(default=0)),
                ('priority', models.PositiveSmallIntegerField(default=1)),
                ('config', models.JSONField(default=dict, blank=True)),
            ],
            options={'verbose_name': 'Exchange Rate Provider'},
        ),
        migrations.CreateModel(
            name='CurrencyConversionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('amount', models.DecimalField(max_digits=20, decimal_places=8)),
                ('converted_amount', models.DecimalField(max_digits=20, decimal_places=8)),
                ('rate_used', models.DecimalField(max_digits=20, decimal_places=10)),
                ('rate_source', models.CharField(max_length=50, blank=True)),
                ('ip_address', models.GenericIPAddressField(null=True, blank=True)),
                ('was_cached', models.BooleanField(default=False)),
                ('from_currency', models.ForeignKey('localization.currency', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversion_logs_from')),
                ('to_currency', models.ForeignKey('localization.currency', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversion_logs_to')),
            ],
            options={'verbose_name': 'Currency Conversion Log', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='exchangerate',
            index=models.Index(fields=['from_currency', 'to_currency', 'date'], name='exrate_pair_date_idx'),
        ),
    ]
