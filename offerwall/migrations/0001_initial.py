from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(default='', max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('source', models.CharField(choices=[('cpalead', 'CPAlead'), ('internal', 'Internal'), ('partner', 'Partner Network')], default='cpalead', max_length=20)),
                ('external_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('payout_usd', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('virtual_payout', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('revenue_share', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('expired', 'Expired'), ('draft', 'Draft')], db_index=True, default='draft', max_length=20)),
                ('is_featured', models.BooleanField(default=False)),
                ('target_device', models.CharField(choices=[('all', 'All Devices'), ('mobile', 'Mobile Only'), ('desktop', 'Desktop Only')], default='all', max_length=20)),
                ('target_countries', models.JSONField(blank=True, default=list)),
                ('min_user_level', models.PositiveSmallIntegerField(default=0)),
                ('image_url', models.URLField(blank=True, default='')),
                ('click_url', models.URLField(blank=True, default='')),
                ('total_clicks', models.PositiveIntegerField(default=0)),
                ('total_conversions', models.PositiveIntegerField(default=0)),
                ('total_paid_usd', models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'app_label': 'offerwall', 'ordering': ['-is_featured', '-payout_usd']},
        ),
        migrations.CreateModel(
            name='OfferClick',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('country', models.CharField(blank=True, default='', max_length=2)),
                ('device_type', models.CharField(blank=True, default='', max_length=20)),
                ('subid', models.CharField(blank=True, db_index=True, default='', max_length=255)),
                ('clicked_at', models.DateTimeField(auto_now_add=True)),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clicks', to='offerwall.offer')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offer_clicks', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'offerwall', 'ordering': ['-clicked_at']},
        ),
        migrations.CreateModel(
            name='OfferConversion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('lead_id', models.CharField(db_index=True, max_length=255, unique=True)),
                ('payout_usd', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('virtual_awarded', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=20)),
                ('fraud_score', models.PositiveSmallIntegerField(default=0)),
                ('fraud_reasons', models.JSONField(default=list)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('postback_raw', models.JSONField(blank=True, default=dict)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('converted_at', models.DateTimeField(auto_now_add=True)),
                ('click', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversions', to='offerwall.offerclick')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversions', to='offerwall.offer')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offer_conversions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'offerwall', 'ordering': ['-converted_at']},
        ),
        migrations.AddIndex(model_name='offer', index=models.Index(fields=['status', 'source'], name='ow_offer_status_source_idx')),
        migrations.AddIndex(model_name='offer', index=models.Index(fields=['target_device', 'status'], name='ow_offer_device_status_idx')),
        migrations.AddIndex(model_name='offerclick', index=models.Index(fields=['offer', 'clicked_at'], name='ow_click_offer_date_idx')),
        migrations.AddIndex(model_name='offerclick', index=models.Index(fields=['user', 'clicked_at'], name='ow_click_user_date_idx')),
        migrations.AddIndex(model_name='offerconversion', index=models.Index(fields=['status', 'converted_at'], name='ow_conv_status_date_idx')),
        migrations.AddIndex(model_name='offerconversion', index=models.Index(fields=['user', 'status'], name='ow_conv_user_status_idx')),
    ]
