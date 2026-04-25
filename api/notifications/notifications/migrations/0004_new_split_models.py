# earning_backend/api/notifications/migrations/0004_new_split_models.py
"""
Migration 0004: Creates all 17 new models from the split architecture.

New models:
  channel.py   — PushDevice, PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog, InAppMessage
  schedule.py  — NotificationSchedule, NotificationBatch, NotificationQueue, NotificationRetry
  campaign.py  — CampaignSegment, NotificationCampaign (new), CampaignABTest, CampaignResult
  analytics.py — NotificationInsight, DeliveryRate, OptOutTracking, NotificationFatigue
"""

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_remove_notification_progress_value_range'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ================================================================
        # channel.py — PushDevice
        # ================================================================
        migrations.CreateModel(
            name='PushDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('device_type', models.CharField(
                    choices=[
                        ('android', 'Android'), ('ios', 'iOS'),
                        ('web', 'Web Browser'), ('desktop', 'Desktop'), ('other', 'Other'),
                    ],
                    default='android', max_length=20,
                )),
                ('fcm_token', models.CharField(blank=True, max_length=500)),
                ('apns_token', models.CharField(blank=True, max_length=500)),
                ('web_push_subscription', models.JSONField(blank=True, default=dict)),
                ('device_name', models.CharField(blank=True, max_length=150)),
                ('device_model', models.CharField(blank=True, max_length=150)),
                ('os_version', models.CharField(blank=True, max_length=50)),
                ('app_version', models.CharField(blank=True, max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('push_sent', models.PositiveIntegerField(default=0)),
                ('push_delivered', models.PositiveIntegerField(default=0)),
                ('push_failed', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='push_devices',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Push Device',
                'verbose_name_plural': 'Push Devices',
                'ordering': ['-last_used', '-created_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='pushdevice',
            index=models.Index(fields=['user', 'is_active'], name='notif_pushdevice_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='pushdevice',
            index=models.Index(fields=['device_type'], name='notif_pushdevice_dtype_idx'),
        ),

        # ================================================================
        # channel.py — PushDeliveryLog
        # ================================================================
        migrations.CreateModel(
            name='PushDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'),
                        ('failed', 'Failed'), ('invalid_token', 'Invalid Token'),
                        ('rate_limited', 'Rate Limited'),
                    ],
                    default='pending', max_length=20,
                )),
                ('provider', models.CharField(blank=True, max_length=50)),
                ('provider_message_id', models.CharField(blank=True, max_length=255)),
                ('error_code', models.CharField(blank=True, max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('device', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='delivery_logs', to='notifications.pushdevice',
                )),
                ('notification', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='push_delivery_logs', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'Push Delivery Log',
                'verbose_name_plural': 'Push Delivery Logs',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='pushdeliverylog',
            index=models.Index(fields=['notification', 'status'], name='notif_pushdlog_notif_status_idx'),
        ),

        # ================================================================
        # channel.py — EmailDeliveryLog
        # ================================================================
        migrations.CreateModel(
            name='EmailDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('recipient', models.EmailField()),
                ('provider', models.CharField(blank=True, max_length=50)),
                ('message_id', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'), ('queued', 'Queued'), ('sent', 'Sent'),
                        ('delivered', 'Delivered'), ('opened', 'Opened'), ('clicked', 'Clicked'),
                        ('bounced', 'Bounced'), ('spam', 'Marked as Spam'),
                        ('unsubscribed', 'Unsubscribed'), ('failed', 'Failed'),
                    ],
                    default='pending', max_length=20,
                )),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('open_count', models.PositiveIntegerField(default=0)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('click_count', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='email_delivery_logs', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'Email Delivery Log',
                'verbose_name_plural': 'Email Delivery Logs',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='emaildeliverylog',
            index=models.Index(fields=['message_id'], name='notif_emaildlog_msgid_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildeliverylog',
            index=models.Index(fields=['notification', 'status'], name='notif_emaildlog_notif_status_idx'),
        ),

        # ================================================================
        # channel.py — SMSDeliveryLog
        # ================================================================
        migrations.CreateModel(
            name='SMSDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('phone', models.CharField(max_length=30)),
                ('gateway', models.CharField(
                    choices=[
                        ('twilio', 'Twilio'), ('shoho_sms', 'ShohoSMS (Bangladesh)'),
                        ('nexmo', 'Vonage / Nexmo'), ('aws_sns', 'AWS SNS'), ('other', 'Other'),
                    ],
                    default='twilio', max_length=20,
                )),
                ('provider_sid', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'), ('queued', 'Queued'), ('sent', 'Sent'),
                        ('delivered', 'Delivered'), ('failed', 'Failed'),
                        ('undelivered', 'Undelivered'), ('invalid_number', 'Invalid Number'),
                    ],
                    default='pending', max_length=20,
                )),
                ('cost', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('cost_currency', models.CharField(default='USD', max_length=10)),
                ('error_code', models.CharField(blank=True, max_length=50)),
                ('error_message', models.TextField(blank=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sms_delivery_logs', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'SMS Delivery Log',
                'verbose_name_plural': 'SMS Delivery Logs',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='smsdeliverylog',
            index=models.Index(fields=['notification', 'status'], name='notif_smsdlog_notif_status_idx'),
        ),
        migrations.AddIndex(
            model_name='smsdeliverylog',
            index=models.Index(fields=['gateway'], name='notif_smsdlog_gateway_idx'),
        ),

        # ================================================================
        # channel.py — InAppMessage
        # ================================================================
        migrations.CreateModel(
            name='InAppMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('message_type', models.CharField(
                    choices=[
                        ('banner', 'Banner'), ('modal', 'Modal'), ('toast', 'Toast'),
                        ('bottom_sheet', 'Bottom Sheet'), ('full_screen', 'Full Screen'),
                    ],
                    default='toast', max_length=20,
                )),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('image_url', models.URLField(blank=True)),
                ('icon_url', models.URLField(blank=True)),
                ('cta_text', models.CharField(blank=True, max_length=100)),
                ('cta_url', models.URLField(blank=True)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('is_dismissed', models.BooleanField(default=False)),
                ('dismissed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('display_priority', models.PositiveSmallIntegerField(default=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='in_app_messages', to='notifications.notification',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='in_app_messages', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'In-App Message',
                'verbose_name_plural': 'In-App Messages',
                'ordering': ['display_priority', '-created_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='inappmessage',
            index=models.Index(fields=['user', 'is_read', 'is_dismissed'], name='notif_inapp_user_read_idx'),
        ),

        # ================================================================
        # schedule.py — NotificationSchedule
        # ================================================================
        migrations.CreateModel(
            name='NotificationSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('send_at', models.DateTimeField()),
                ('timezone', models.CharField(default='UTC', max_length=64)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'), ('processing', 'Processing'), ('sent', 'Sent'),
                        ('cancelled', 'Cancelled'), ('failed', 'Failed'), ('skipped', 'Skipped'),
                    ],
                    db_index=True, default='pending', max_length=20,
                )),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('failure_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_schedules', to=settings.AUTH_USER_MODEL,
                )),
                ('notification', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='schedule', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'Notification Schedule',
                'verbose_name_plural': 'Notification Schedules',
                'ordering': ['send_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='notificationschedule',
            index=models.Index(fields=['status', 'send_at'], name='notif_sched_status_sendat_idx'),
        ),

        # ================================================================
        # schedule.py — NotificationBatch
        # ================================================================
        migrations.CreateModel(
            name='NotificationBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'), ('queued', 'Queued'), ('processing', 'Processing'),
                        ('completed', 'Completed'), ('partially_failed', 'Partially Failed'),
                        ('failed', 'Failed'), ('cancelled', 'Cancelled'),
                    ],
                    db_index=True, default='draft', max_length=20,
                )),
                ('total_count', models.PositiveIntegerField(default=0)),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('delivered_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('skipped_count', models.PositiveIntegerField(default=0)),
                ('context', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('celery_task_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_batches', to=settings.AUTH_USER_MODEL,
                )),
                ('template', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='batches', to='notifications.notificationtemplate',
                )),
            ],
            options={
                'verbose_name': 'Notification Batch',
                'verbose_name_plural': 'Notification Batches',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # schedule.py — NotificationQueue
        # ================================================================
        migrations.CreateModel(
            name='NotificationQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('priority', models.PositiveSmallIntegerField(
                    default=5,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(10),
                    ],
                )),
                ('scheduled_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(
                    choices=[
                        ('waiting', 'Waiting'), ('processing', 'Processing'),
                        ('done', 'Done'), ('failed', 'Failed'), ('cancelled', 'Cancelled'),
                    ],
                    db_index=True, default='waiting', max_length=20,
                )),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_attempt', models.DateTimeField(blank=True, null=True)),
                ('celery_task_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='queue_entry', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'Notification Queue Entry',
                'verbose_name_plural': 'Notification Queue Entries',
                'ordering': ['-priority', 'scheduled_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='notificationqueue',
            index=models.Index(fields=['status', '-priority', 'scheduled_at'], name='notif_queue_status_pri_idx'),
        ),

        # ================================================================
        # schedule.py — NotificationRetry
        # ================================================================
        migrations.CreateModel(
            name='NotificationRetry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('attempt_number', models.PositiveSmallIntegerField(default=1)),
                ('max_attempts', models.PositiveSmallIntegerField(default=3)),
                ('status', models.CharField(
                    choices=[
                        ('scheduled', 'Scheduled'), ('processing', 'Processing'),
                        ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('abandoned', 'Abandoned'),
                    ],
                    db_index=True, default='scheduled', max_length=20,
                )),
                ('error_from_previous', models.TextField(blank=True)),
                ('error', models.TextField(blank=True)),
                ('retry_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('attempted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notification', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retry_attempts', to='notifications.notification',
                )),
            ],
            options={
                'verbose_name': 'Notification Retry',
                'verbose_name_plural': 'Notification Retries',
                'ordering': ['notification', 'attempt_number'],
                'unique_together': {('notification', 'attempt_number')},
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='notificationretry',
            index=models.Index(fields=['status', 'retry_at'], name='notif_retry_status_retrytime_idx'),
        ),

        # ================================================================
        # campaign.py — CampaignSegment
        # ================================================================
        migrations.CreateModel(
            name='CampaignSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('segment_type', models.CharField(
                    choices=[
                        ('all', 'All Users'), ('tier', 'By Membership Tier'),
                        ('geo', 'By Geography'), ('inactive', 'Inactive Users'),
                        ('new', 'New Users (< 30 days)'), ('high_value', 'High-Value Users'),
                        ('custom', 'Custom Conditions'),
                    ],
                    default='all', max_length=20,
                )),
                ('conditions', models.JSONField(blank=True, default=dict)),
                ('estimated_size', models.PositiveIntegerField(default=0)),
                ('last_evaluated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_segments', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Campaign Segment',
                'verbose_name_plural': 'Campaign Segments',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # campaign.py — NewNotificationCampaign (separate from legacy one)
        # ================================================================
        migrations.CreateModel(
            name='NewNotificationCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'), ('scheduled', 'Scheduled'), ('running', 'Running'),
                        ('paused', 'Paused'), ('completed', 'Completed'),
                        ('cancelled', 'Cancelled'), ('failed', 'Failed'),
                    ],
                    db_index=True, default='draft', max_length=20,
                )),
                ('send_at', models.DateTimeField(blank=True, null=True)),
                ('total_users', models.PositiveIntegerField(default=0)),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('context', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('celery_task_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='new_created_campaigns', to=settings.AUTH_USER_MODEL,
                )),
                ('segment', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='primary_campaigns', to='notifications.campaignsegment',
                )),
                ('template', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='new_campaigns', to='notifications.notificationtemplate',
                )),
            ],
            options={
                'verbose_name': 'Notification Campaign (New)',
                'verbose_name_plural': 'Notification Campaigns (New)',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),

        # Add campaign FK to CampaignSegment (after NewNotificationCampaign is created)
        migrations.AddField(
            model_name='campaignsegment',
            name='campaign',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='segments', to='notifications.newnotificationcampaign',
            ),
        ),

        # Add batch → segment FK (after CampaignSegment is created)
        migrations.AddField(
            model_name='notificationbatch',
            name='segment',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='batches', to='notifications.campaignsegment',
            ),
        ),

        # ================================================================
        # campaign.py — CampaignABTest
        # ================================================================
        migrations.CreateModel(
            name='CampaignABTest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('split_pct', models.PositiveSmallIntegerField(
                    default=50,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(99),
                    ],
                )),
                ('winning_metric', models.CharField(
                    choices=[
                        ('open_rate', 'Open Rate'), ('click_rate', 'Click-Through Rate'),
                        ('conversion_rate', 'Conversion Rate'), ('delivery_rate', 'Delivery Rate'),
                    ],
                    default='open_rate', max_length=20,
                )),
                ('winner', models.CharField(
                    choices=[
                        ('none', 'No Winner Yet'), ('a', 'Variant A'),
                        ('b', 'Variant B'), ('tie', 'Tie'),
                    ],
                    default='none', max_length=10,
                )),
                ('variant_a_stats', models.JSONField(blank=True, default=dict)),
                ('variant_b_stats', models.JSONField(blank=True, default=dict)),
                ('winner_declared_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ab_test', to='notifications.newnotificationcampaign',
                )),
                ('variant_a', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ab_test_variant_a', to='notifications.notificationtemplate',
                )),
                ('variant_b', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ab_test_variant_b', to='notifications.notificationtemplate',
                )),
            ],
            options={
                'verbose_name': 'Campaign A/B Test',
                'verbose_name_plural': 'Campaign A/B Tests',
                'ordering': ['-created_at'],
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # campaign.py — CampaignResult
        # ================================================================
        migrations.CreateModel(
            name='CampaignResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('sent', models.PositiveIntegerField(default=0)),
                ('delivered', models.PositiveIntegerField(default=0)),
                ('failed', models.PositiveIntegerField(default=0)),
                ('opened', models.PositiveIntegerField(default=0)),
                ('clicked', models.PositiveIntegerField(default=0)),
                ('converted', models.PositiveIntegerField(default=0)),
                ('unsubscribed', models.PositiveIntegerField(default=0)),
                ('delivery_rate', models.FloatField(default=0.0)),
                ('open_rate', models.FloatField(default=0.0)),
                ('click_rate', models.FloatField(default=0.0)),
                ('conversion_rate', models.FloatField(default=0.0)),
                ('total_cost', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('cost_currency', models.CharField(default='USD', max_length=10)),
                ('calculated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='result', to='notifications.newnotificationcampaign',
                )),
            ],
            options={
                'verbose_name': 'Campaign Result',
                'verbose_name_plural': 'Campaign Results',
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # analytics.py — NotificationInsight
        # ================================================================
        migrations.CreateModel(
            name='NotificationInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('date', models.DateField(db_index=True)),
                ('channel', models.CharField(
                    choices=[
                        ('in_app', 'In-App'), ('push', 'Push'), ('email', 'Email'),
                        ('sms', 'SMS'), ('telegram', 'Telegram'), ('whatsapp', 'WhatsApp'),
                        ('browser', 'Browser Push'), ('all', 'All Channels'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('sent', models.PositiveIntegerField(default=0)),
                ('delivered', models.PositiveIntegerField(default=0)),
                ('failed', models.PositiveIntegerField(default=0)),
                ('opened', models.PositiveIntegerField(default=0)),
                ('clicked', models.PositiveIntegerField(default=0)),
                ('unsubscribed', models.PositiveIntegerField(default=0)),
                ('unique_users_reached', models.PositiveIntegerField(default=0)),
                ('total_cost', models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ('cost_currency', models.CharField(default='USD', max_length=10)),
                ('breakdown', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Notification Insight',
                'verbose_name_plural': 'Notification Insights',
                'ordering': ['-date', 'channel'],
                'unique_together': {('date', 'channel')},
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # analytics.py — DeliveryRate
        # ================================================================
        migrations.CreateModel(
            name='DeliveryRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('date', models.DateField(db_index=True)),
                ('channel', models.CharField(db_index=True, max_length=20)),
                ('delivery_pct', models.FloatField(default=0.0)),
                ('open_pct', models.FloatField(default=0.0)),
                ('click_pct', models.FloatField(default=0.0)),
                ('sample_size', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Delivery Rate',
                'verbose_name_plural': 'Delivery Rates',
                'ordering': ['-date', 'channel'],
                'unique_together': {('date', 'channel')},
                'app_label': 'notifications',
            },
        ),

        # ================================================================
        # analytics.py — OptOutTracking
        # ================================================================
        migrations.CreateModel(
            name='OptOutTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('channel', models.CharField(db_index=True, max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('reason', models.CharField(
                    choices=[
                        ('too_many', 'Too Many Notifications'), ('not_relevant', 'Not Relevant'),
                        ('privacy', 'Privacy Concern'), ('spam', 'Marked as Spam'),
                        ('user_request', 'User Request'), ('admin_action', 'Admin Action'),
                        ('system', 'System / Automatic'), ('other', 'Other'),
                    ],
                    default='user_request', max_length=30,
                )),
                ('notes', models.TextField(blank=True)),
                ('opted_out_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('opted_in_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actioned_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='actioned_opt_outs', to=settings.AUTH_USER_MODEL,
                )),
                ('triggered_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='triggered_opt_outs', to='notifications.notification',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='opt_out_records', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Opt-Out Record',
                'verbose_name_plural': 'Opt-Out Records',
                'ordering': ['-opted_out_at'],
                'app_label': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='optouttracking',
            index=models.Index(fields=['user', 'channel', 'is_active'], name='notif_optout_user_chan_idx'),
        ),

        # ================================================================
        # analytics.py — NotificationFatigue
        # ================================================================
        migrations.CreateModel(
            name='NotificationFatigue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('sent_today', models.PositiveSmallIntegerField(default=0)),
                ('sent_this_week', models.PositiveSmallIntegerField(default=0)),
                ('sent_this_month', models.PositiveIntegerField(default=0)),
                ('daily_limit', models.PositiveSmallIntegerField(default=0)),
                ('weekly_limit', models.PositiveSmallIntegerField(default=0)),
                ('is_fatigued', models.BooleanField(db_index=True, default=False)),
                ('last_evaluated_at', models.DateTimeField(blank=True, null=True)),
                ('daily_reset_at', models.DateTimeField(blank=True, null=True)),
                ('weekly_reset_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_fatigue', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Notification Fatigue',
                'verbose_name_plural': 'Notification Fatigue Records',
                'ordering': ['-updated_at'],
                'app_label': 'notifications',
            },
        ),

        # Add new rich media fields to existing Notification table
        migrations.AddField(
            model_name='notification',
            name='video_url',
            field=models.URLField(blank=True, help_text='Video URL for rich push notifications'),
        ),
        migrations.AddField(
            model_name='notification',
            name='gif_url',
            field=models.URLField(blank=True, help_text='GIF URL for animated rich notifications'),
        ),
        migrations.AddField(
            model_name='notification',
            name='offer_id',
            field=models.CharField(blank=True, max_length=100, help_text='CPAlead offer ID reference'),
        ),
        migrations.AddField(
            model_name='notification',
            name='affiliate_id',
            field=models.CharField(blank=True, max_length=100, help_text='Affiliate/publisher ID reference'),
        ),
        migrations.AddField(
            model_name='notification',
            name='conversion_value',
            field=models.DecimalField(blank=True, decimal_places=4, default=0, max_digits=10, help_text='Conversion value in USD for CPA tracking'),
        ),
    ]