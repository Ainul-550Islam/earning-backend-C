from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('smartlink', '0002_targeting'),
        ('offer_inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfferPool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('min_epc_threshold', models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('smartlink', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='offer_pool', to='smartlink.smartlink')),
            ],
            options={'db_table': 'sl_offer_pool'},
        ),
        migrations.CreateModel(
            name='OfferPoolEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('weight', models.PositiveSmallIntegerField(default=100)),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('cap_per_day', models.PositiveIntegerField(blank=True, null=True)),
                ('cap_per_month', models.PositiveIntegerField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('epc_override', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='smartlink.offerpool')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pool_entries', to='offer_inventory.offer')),
            ],
            options={'db_table': 'sl_offer_pool_entry', 'ordering': ['-priority', '-weight'], 'unique_together': {('pool', 'offer')}},
        ),
        migrations.CreateModel(
            name='OfferCapTracker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('period', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('total', 'Total')], default='daily', max_length=10)),
                ('period_date', models.DateField(db_index=True)),
                ('clicks_count', models.PositiveIntegerField(default=0)),
                ('cap_limit', models.PositiveIntegerField()),
                ('is_capped', models.BooleanField(db_index=True, default=False)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('pool_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cap_trackers', to='smartlink.offerpoolentry')),
            ],
            options={'db_table': 'sl_offer_cap_tracker', 'unique_together': {('pool_entry', 'period', 'period_date')}},
        ),
        migrations.CreateModel(
            name='OfferBlacklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('smartlink', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blacklisted_offers', to='smartlink.smartlink')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='offer_inventory.offer')),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'sl_offer_blacklist', 'unique_together': {('smartlink', 'offer')}},
        ),
        migrations.CreateModel(
            name='OfferRotationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('selected_reason', models.CharField(max_length=30)),
                ('offer_weight', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('offer_epc', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('country', models.CharField(blank=True, max_length=2)),
                ('device_type', models.CharField(blank=True, max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('smartlink', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rotation_logs', to='smartlink.smartlink')),
                ('offer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='offer_inventory.offer')),
            ],
            options={'db_table': 'sl_offer_rotation_log', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OfferScoreCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('country', models.CharField(db_index=True, max_length=2)),
                ('device_type', models.CharField(max_length=10)),
                ('epc', models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ('conversion_rate', models.DecimalField(decimal_places=4, default=0, max_digits=6)),
                ('total_clicks', models.PositiveIntegerField(default=0)),
                ('total_conversions', models.PositiveIntegerField(default=0)),
                ('score', models.FloatField(db_index=True, default=0.0)),
                ('calculated_at', models.DateTimeField(auto_now=True)),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_caches', to='offer_inventory.offer')),
            ],
            options={'db_table': 'sl_offer_score_cache', 'unique_together': {('offer', 'country', 'device_type')}},
        ),
    ]
