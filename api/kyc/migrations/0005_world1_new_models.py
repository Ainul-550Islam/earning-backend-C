# kyc/migrations/0005_world1_new_models.py
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0004_kycsubmission'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # KYCBlacklist
        migrations.CreateModel(
            name='KYCBlacklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('phone','Phone Number'),('document','Document Number'),('ip','IP Address'),('email','Email'),('nid','NID Number')], db_index=True, max_length=20)),
                ('value', models.CharField(db_index=True, max_length=255)),
                ('reason', models.TextField(blank=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_blacklist', 'verbose_name': 'KYC Blacklist Entry'},
        ),
        migrations.AlterUniqueTogether(name='kycblacklist', unique_together={('type', 'value')}),

        # KYCRiskProfile
        migrations.CreateModel(
            name='KYCRiskProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('risk_level', models.CharField(choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], db_index=True, default='low', max_length=10)),
                ('overall_score', models.IntegerField(default=0)),
                ('name_match_score', models.FloatField(default=0.0)),
                ('face_match_score', models.FloatField(default=0.0)),
                ('document_clarity_score', models.FloatField(default=0.0)),
                ('ocr_confidence_score', models.FloatField(default=0.0)),
                ('duplicate_flag', models.BooleanField(default=False)),
                ('age_flag', models.BooleanField(default=False)),
                ('blacklist_flag', models.BooleanField(default=False)),
                ('vpn_flag', models.BooleanField(default=False)),
                ('multiple_attempts_flag', models.BooleanField(default=False)),
                ('factors', models.JSONField(default=list)),
                ('computed_at', models.DateTimeField(auto_now=True)),
                ('requires_manual_review', models.BooleanField(db_index=True, default=False)),
                ('notes', models.TextField(blank=True)),
                ('kyc', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='risk_profile', to='kyc.kyc')),
            ],
            options={'db_table': 'kyc_risk_profiles', 'verbose_name': 'KYC Risk Profile'},
        ),

        # KYCOCRResult
        migrations.CreateModel(
            name='KYCOCRResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='tesseract', max_length=50)),
                ('document_side', models.CharField(choices=[('front','Front'),('back','Back')], default='front', max_length=10)),
                ('raw_text', models.TextField(blank=True)),
                ('extracted_name', models.CharField(blank=True, max_length=200)),
                ('extracted_dob', models.CharField(blank=True, max_length=30)),
                ('extracted_nid', models.CharField(blank=True, max_length=50)),
                ('extracted_address', models.TextField(blank=True)),
                ('extracted_father_name', models.CharField(blank=True, max_length=200)),
                ('extracted_mother_name', models.CharField(blank=True, max_length=200)),
                ('confidence', models.FloatField(default=0.0)),
                ('language', models.CharField(default='eng', max_length=10)),
                ('processing_time_ms', models.IntegerField(default=0)),
                ('error', models.TextField(blank=True)),
                ('is_successful', models.BooleanField(default=False)),
                ('raw_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('kyc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ocr_results', to='kyc.kyc')),
            ],
            options={'db_table': 'kyc_ocr_results', 'verbose_name': 'OCR Result', 'ordering': ['-created_at']},
        ),

        # KYCFaceMatchResult
        migrations.CreateModel(
            name='KYCFaceMatchResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='deepface', max_length=50)),
                ('match_confidence', models.FloatField(default=0.0)),
                ('liveness_score', models.FloatField(default=0.0)),
                ('is_matched', models.BooleanField(default=False)),
                ('is_liveness_pass', models.BooleanField(default=False)),
                ('face_detected_selfie', models.BooleanField(default=False)),
                ('face_detected_doc', models.BooleanField(default=False)),
                ('multiple_faces', models.BooleanField(default=False)),
                ('spoofing_detected', models.BooleanField(default=False)),
                ('processing_time_ms', models.IntegerField(default=0)),
                ('error', models.TextField(blank=True)),
                ('raw_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('kyc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_match_results', to='kyc.kyc')),
            ],
            options={'db_table': 'kyc_face_match_results', 'verbose_name': 'Face Match Result', 'ordering': ['-created_at']},
        ),

        # KYCWebhookEndpoint
        migrations.CreateModel(
            name='KYCWebhookEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('url', models.URLField(max_length=500)),
                ('secret_key', models.CharField(blank=True, max_length=256)),
                ('events', models.JSONField(default=list)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('timeout_sec', models.IntegerField(default=10)),
                ('retry_count', models.IntegerField(default=3)),
                ('headers', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_webhooks', to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_webhook_endpoints', 'verbose_name': 'Webhook Endpoint'},
        ),

        # KYCWebhookDeliveryLog
        migrations.CreateModel(
            name='KYCWebhookDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(max_length=100)),
                ('payload', models.JSONField(default=dict)),
                ('response_code', models.IntegerField(blank=True, null=True)),
                ('response_body', models.TextField(blank=True)),
                ('is_success', models.BooleanField(db_index=True, default=False)),
                ('attempt_count', models.IntegerField(default=1)),
                ('duration_ms', models.IntegerField(default=0)),
                ('error', models.TextField(blank=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_logs', to='kyc.kycwebhookendpoint')),
            ],
            options={'db_table': 'kyc_webhook_delivery_logs', 'verbose_name': 'Webhook Delivery Log', 'ordering': ['-sent_at']},
        ),

        # KYCExportJob
        migrations.CreateModel(
            name='KYCExportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('format', models.CharField(choices=[('csv','CSV'),('excel','Excel'),('pdf','PDF'),('json','JSON')], max_length=10)),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('pending','Pending'),('processing','Processing'),('done','Done'),('failed','Failed')], db_index=True, default='pending', max_length=15)),
                ('file', models.FileField(blank=True, null=True, upload_to='kyc/exports/')),
                ('row_count', models.IntegerField(default=0)),
                ('error', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_export_jobs', 'verbose_name': 'Export Job', 'ordering': ['-created_at']},
        ),

        # KYCBulkActionLog
        migrations.CreateModel(
            name='KYCBulkActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('verified','Verified'),('rejected','Rejected'),('pending','Pending'),('reset','Reset'),('export','Export'),('delete','Delete')], max_length=20)),
                ('kyc_ids', models.JSONField(default=list)),
                ('total_affected', models.IntegerField(default=0)),
                ('success_count', models.IntegerField(default=0)),
                ('failure_count', models.IntegerField(default=0)),
                ('reason', models.TextField(blank=True)),
                ('errors', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_bulk_action_logs', 'verbose_name': 'Bulk Action Log', 'ordering': ['-created_at']},
        ),

        # KYCAdminNote
        migrations.CreateModel(
            name='KYCAdminNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note_type', models.CharField(choices=[('general','General'),('warning','Warning'),('fraud_alert','Fraud Alert'),('follow_up','Follow Up'),('approved','Approval Note'),('rejection','Rejection Note')], default='general', max_length=20)),
                ('content', models.TextField()),
                ('is_internal', models.BooleanField(default=True)),
                ('is_pinned', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kyc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='admin_note_list', to='kyc.kyc')),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_admin_notes', 'verbose_name': 'Admin Note', 'ordering': ['-is_pinned', '-created_at']},
        ),

        # KYCRejectionTemplate
        migrations.CreateModel(
            name='KYCRejectionTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('body', models.TextField()),
                ('category', models.CharField(blank=True, max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('usage_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_rejection_templates', 'verbose_name': 'Rejection Template', 'ordering': ['-usage_count', 'title']},
        ),

        # KYCAnalyticsSnapshot
        migrations.CreateModel(
            name='KYCAnalyticsSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.CharField(choices=[('hourly','Hourly'),('daily','Daily'),('weekly','Weekly'),('monthly','Monthly')], db_index=True, max_length=10)),
                ('period_start', models.DateTimeField(db_index=True)),
                ('period_end', models.DateTimeField()),
                ('total_submitted', models.IntegerField(default=0)),
                ('total_verified', models.IntegerField(default=0)),
                ('total_rejected', models.IntegerField(default=0)),
                ('total_pending', models.IntegerField(default=0)),
                ('total_expired', models.IntegerField(default=0)),
                ('avg_risk_score', models.FloatField(default=0.0)),
                ('high_risk_count', models.IntegerField(default=0)),
                ('duplicate_count', models.IntegerField(default=0)),
                ('avg_processing_hours', models.FloatField(default=0.0)),
                ('verification_rate', models.FloatField(default=0.0)),
                ('rejection_rate', models.FloatField(default=0.0)),
                ('snapshot_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_analytics_snapshots', 'verbose_name': 'Analytics Snapshot', 'ordering': ['-period_start']},
        ),
        migrations.AlterUniqueTogether(name='kycanalyticssnapshot', unique_together={('tenant', 'period', 'period_start')}),

        # KYCIPTracker
        migrations.CreateModel(
            name='KYCIPTracker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('action', models.CharField(max_length=50)),
                ('user_agent', models.TextField(blank=True)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('is_vpn', models.BooleanField(db_index=True, default=False)),
                ('is_proxy', models.BooleanField(default=False)),
                ('is_tor', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('kyc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ip_logs', to='kyc.kyc')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_ip_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_ip_tracker', 'verbose_name': 'IP Tracker Entry', 'ordering': ['-created_at']},
        ),

        # KYCDeviceFingerprint
        migrations.CreateModel(
            name='KYCDeviceFingerprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.CharField(db_index=True, max_length=512)),
                ('device_type', models.CharField(blank=True, max_length=50)),
                ('os', models.CharField(blank=True, max_length=100)),
                ('browser', models.CharField(blank=True, max_length=100)),
                ('screen_res', models.CharField(blank=True, max_length=20)),
                ('timezone', models.CharField(blank=True, max_length=100)),
                ('language', models.CharField(blank=True, max_length=20)),
                ('canvas_hash', models.CharField(blank=True, max_length=64)),
                ('webgl_hash', models.CharField(blank=True, max_length=64)),
                ('is_suspicious', models.BooleanField(db_index=True, default=False)),
                ('seen_count', models.IntegerField(default=1)),
                ('first_seen', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_device_fingerprints', 'verbose_name': 'Device Fingerprint'},
        ),
        migrations.AlterUniqueTogether(name='kycdevicefingerprint', unique_together={('user', 'fingerprint')}),

        # KYCVerificationStep
        migrations.CreateModel(
            name='KYCVerificationStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('step', models.CharField(choices=[('personal_info','Personal Info'),('document_upload','Document Upload'),('ocr_check','OCR Check'),('face_check','Face Check'),('fraud_check','Fraud Check'),('admin_review','Admin Review'),('final','Final Decision')], max_length=30)),
                ('status', models.CharField(choices=[('pending','Pending'),('in_progress','In Progress'),('done','Done'),('failed','Failed'),('skipped','Skipped')], default='pending', max_length=15)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.IntegerField(default=0)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('error', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('order', models.IntegerField(default=0)),
                ('kyc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verification_steps', to='kyc.kyc')),
            ],
            options={'db_table': 'kyc_verification_steps', 'verbose_name': 'Verification Step', 'ordering': ['order']},
        ),
        migrations.AlterUniqueTogether(name='kycverificationstep', unique_together={('kyc', 'step')}),

        # KYCOTPLog
        migrations.CreateModel(
            name='KYCOTPLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=20)),
                ('purpose', models.CharField(choices=[('phone_verify','Phone Verification'),('resubmit','Resubmit Verification'),('admin_action','Admin Action OTP')], max_length=20)),
                ('otp_hash', models.CharField(max_length=128)),
                ('is_used', models.BooleanField(default=False)),
                ('is_verified', models.BooleanField(default=False)),
                ('attempt_count', models.IntegerField(default=0)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
                ('kyc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='kyc.kyc')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_otp_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_otp_logs', 'verbose_name': 'OTP Log', 'ordering': ['-sent_at']},
        ),

        # KYCTenantConfig
        migrations.CreateModel(
            name='KYCTenantConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kyc_required', models.BooleanField(default=True)),
                ('allowed_document_types', models.JSONField(default=list)),
                ('min_age', models.IntegerField(default=18)),
                ('auto_approve_threshold', models.IntegerField(default=0)),
                ('auto_reject_threshold', models.IntegerField(default=90)),
                ('kyc_expiry_days', models.IntegerField(default=365)),
                ('require_selfie', models.BooleanField(default=True)),
                ('require_face_match', models.BooleanField(default=True)),
                ('require_ocr', models.BooleanField(default=True)),
                ('require_phone_verify', models.BooleanField(default=True)),
                ('max_submissions_per_user', models.IntegerField(default=5)),
                ('submission_cooldown_hours', models.IntegerField(default=24)),
                ('notification_enabled', models.BooleanField(default=True)),
                ('webhook_enabled', models.BooleanField(default=True)),
                ('custom_rejection_messages', models.JSONField(blank=True, default=dict)),
                ('extra_config', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_config', to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_tenant_configs', 'verbose_name': 'KYC Tenant Config'},
        ),

        # KYCAuditTrail
        migrations.CreateModel(
            name='KYCAuditTrail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actor_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('actor_agent', models.TextField(blank=True)),
                ('entity_type', models.CharField(choices=[('kyc','KYC'),('kyc_submission','KYC Submission'),('blacklist','Blacklist'),('config','Tenant Config'),('webhook','Webhook'),('export','Export'),('bulk_action','Bulk Action')], db_index=True, max_length=30)),
                ('entity_id', models.CharField(db_index=True, max_length=50)),
                ('action', models.CharField(db_index=True, max_length=100)),
                ('before_state', models.JSONField(blank=True, default=dict)),
                ('after_state', models.JSONField(blank=True, default=dict)),
                ('diff', models.JSONField(blank=True, default=dict)),
                ('description', models.TextField(blank=True)),
                ('severity', models.CharField(choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='low', max_length=10)),
                ('session_id', models.CharField(blank=True, max_length=100)),
                ('request_id', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'db_table': 'kyc_audit_trail', 'verbose_name': 'Audit Trail', 'ordering': ['-created_at']},
        ),

        # KYCDuplicateGroup
        migrations.CreateModel(
            name='KYCDuplicateGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('match_type', models.CharField(choices=[('document','Document Number'),('phone','Phone Number'),('face','Face Match'),('name_dob','Name + DOB')], max_length=20)),
                ('match_value', models.CharField(db_index=True, max_length=255)),
                ('is_resolved', models.BooleanField(db_index=True, default=False)),
                ('resolution_note', models.TextField(blank=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('kyc_records', models.ManyToManyField(related_name='duplicate_groups', to='kyc.kyc')),
                ('primary_kyc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='primary_duplicate_group', to='kyc.kyc')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_duplicate_groups', 'verbose_name': 'Duplicate Group'},
        ),

        # KYCNotificationLog
        migrations.CreateModel(
            name='KYCNotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('push','Push'),('sms','SMS'),('email','Email'),('in_app','In-App')], max_length=10)),
                ('event_type', models.CharField(max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('is_sent', models.BooleanField(db_index=True, default=False)),
                ('is_read', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('kyc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='kyc.kyc')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_notification_logs', 'verbose_name': 'Notification Log', 'ordering': ['-created_at']},
        ),

        # KYCFeatureFlag
        migrations.CreateModel(
            name='KYCFeatureFlag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=100)),
                ('is_enabled', models.BooleanField(db_index=True, default=False)),
                ('value', models.JSONField(blank=True, default=dict)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_feature_flags', 'verbose_name': 'Feature Flag'},
        ),
        migrations.AlterUniqueTogether(name='kycfeatureflag', unique_together={('tenant', 'key')}),
    ]
