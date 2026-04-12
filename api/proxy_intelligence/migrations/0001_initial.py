"""
Initial Migration — proxy_intelligence  (COMPLETE - ALL 24 MODELS)
===================================================================
Run:
  python manage.py makemigrations api.proxy_intelligence
  python manage.py migrate

This file is the auto-generated template. If using Django's own
makemigrations the output will be more complete; this file bootstraps
the module so it can be migrated immediately.
"""
import django.db.models.deletion
import django.utils.timezone
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── ThreatFeedProvider (no FK deps) ──────────────────────────────
        migrations.CreateModel(
            name='ThreatFeedProvider',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('display_name', models.CharField(max_length=255)),
                ('api_endpoint', models.URLField(blank=True)),
                ('api_key_env', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=1)),
                ('last_sync', models.DateTimeField(blank=True, null=True)),
                ('total_entries', models.BigIntegerField(default=0)),
                ('daily_quota', models.IntegerField(default=1000)),
                ('used_today', models.IntegerField(default=0)),
                ('config', models.JSONField(blank=True, default=dict)),
            ],
            options={'verbose_name': 'Threat Feed Provider', 'ordering': ['priority']},
        ),

        # ── MLModelMetadata (no FK deps) ──────────────────────────────────
        migrations.CreateModel(
            name='MLModelMetadata',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('version', models.CharField(max_length=20)),
                ('model_type', models.CharField(max_length=50, choices=[
                    ('risk_scoring','Risk Scoring Model'),('anomaly_detection','Anomaly Detection'),
                    ('vpn_detection','VPN Detection'),('bot_detection','Bot Detection'),
                    ('fraud_classification','Fraud Classification'),
                ])),
                ('is_active', models.BooleanField(db_index=True, default=False)),
                ('is_default', models.BooleanField(default=False)),
                ('accuracy', models.FloatField(blank=True, null=True)),
                ('precision', models.FloatField(blank=True, null=True)),
                ('recall', models.FloatField(blank=True, null=True)),
                ('f1_score', models.FloatField(blank=True, null=True)),
                ('auc_roc', models.FloatField(blank=True, null=True)),
                ('false_positive_rate', models.FloatField(blank=True, null=True)),
                ('training_data_size', models.BigIntegerField(default=0)),
                ('training_duration_seconds', models.FloatField(blank=True, null=True)),
                ('trained_at', models.DateTimeField(blank=True, null=True)),
                ('model_file_path', models.CharField(blank=True, max_length=500)),
                ('features', models.JSONField(blank=True, default=list)),
                ('hyperparameters', models.JSONField(blank=True, default=dict)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={'verbose_name': 'ML Model Metadata', 'ordering': ['-trained_at'],
                     'unique_together': {('name', 'version')}},
        ),

        # ── TorExitNode ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='TorExitNode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True, unique=True)),
                ('fingerprint', models.CharField(blank=True, max_length=40)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('first_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('exit_policy', models.TextField(blank=True)),
                ('bandwidth', models.BigIntegerField(blank=True, null=True)),
            ],
            options={'verbose_name': 'Tor Exit Node', 'ordering': ['-last_seen']},
        ),

        # ── DatacenterIPRange ──────────────────────────────────────────────
        migrations.CreateModel(
            name='DatacenterIPRange',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cidr', models.CharField(max_length=50, unique=True)),
                ('provider_name', models.CharField(max_length=255)),
                ('asn', models.CharField(blank=True, max_length=20)),
                ('country_code', models.CharField(blank=True, max_length=2)),
                ('is_active', models.BooleanField(default=True)),
                ('source', models.CharField(blank=True, max_length=100)),
                ('last_updated', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'verbose_name': 'Datacenter IP Range', 'ordering': ['provider_name']},
        ),

        # ── PerformanceMetric ─────────────────────────────────────────────
        migrations.CreateModel(
            name='PerformanceMetric',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('metric_type', models.CharField(max_length=50, choices=[
                    ('detection_latency','Detection Latency'),('api_response_time','API Response Time'),
                    ('cache_hit_rate','Cache Hit Rate'),('detection_accuracy','Detection Accuracy'),
                    ('throughput','Throughput (req/sec)'),
                ])),
                ('engine_name', models.CharField(max_length=100)),
                ('value', models.FloatField()),
                ('unit', models.CharField(blank=True, max_length=20)),
                ('recorded_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={'verbose_name': 'Performance Metric', 'ordering': ['-recorded_at']},
        ),

        # ── IPIntelligence ────────────────────────────────────────────────
        migrations.CreateModel(
            name='IPIntelligence',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('ip_version', models.CharField(choices=[('ipv4','IPv4'),('ipv6','IPv6')], default='ipv4', max_length=4)),
                ('asn', models.CharField(blank=True, max_length=20)),
                ('asn_name', models.CharField(blank=True, max_length=255)),
                ('isp', models.CharField(blank=True, max_length=255)),
                ('organization', models.CharField(blank=True, max_length=255)),
                ('country_code', models.CharField(blank=True, max_length=2)),
                ('country_name', models.CharField(blank=True, max_length=100)),
                ('region', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('timezone', models.CharField(blank=True, max_length=50)),
                ('is_vpn', models.BooleanField(db_index=True, default=False)),
                ('is_proxy', models.BooleanField(db_index=True, default=False)),
                ('is_tor', models.BooleanField(db_index=True, default=False)),
                ('is_datacenter', models.BooleanField(db_index=True, default=False)),
                ('is_residential', models.BooleanField(default=False)),
                ('is_mobile', models.BooleanField(default=False)),
                ('is_hosting', models.BooleanField(default=False)),
                ('is_crawler', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(db_index=True, default=0)),
                ('risk_level', models.CharField(
                    choices=[('very_low','Very Low (0-20)'),('low','Low (21-40)'),
                             ('medium','Medium (41-60)'),('high','High (61-80)'),
                             ('critical','Critical (81-100)')],
                    default='very_low', max_length=20)),
                ('fraud_score', models.IntegerField(default=0)),
                ('abuse_confidence_score', models.IntegerField(default=0)),
                ('last_checked', models.DateTimeField(default=django.utils.timezone.now)),
                ('check_count', models.IntegerField(default=1)),
                ('raw_data', models.JSONField(blank=True, default=dict)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ip_intelligences', to='tenants.tenant')),
            ],
            options={'verbose_name': 'IP Intelligence', 'ordering': ['-last_checked']},
        ),
        migrations.AddIndex(
            model_name='ipintelligence',
            index=models.Index(fields=['ip_address', 'tenant'], name='pi_intel_ip_tenant_idx'),
        ),
        migrations.AddIndex(
            model_name='ipintelligence',
            index=models.Index(fields=['risk_score'], name='pi_intel_risk_idx'),
        ),
        migrations.AddIndex(
            model_name='ipintelligence',
            index=models.Index(fields=['is_vpn', 'is_proxy', 'is_tor'], name='pi_intel_flags_idx'),
        ),

        # ── IPBlacklist ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='IPBlacklist',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('cidr', models.CharField(blank=True, max_length=50)),
                ('reason', models.CharField(max_length=50, choices=[
                    ('fraud','Fraud Detected'),('abuse','Abuse Reported'),('spam','Spam Activity'),
                    ('bot','Bot Activity'),('scraping','Scraping'),('manual','Manual Block'),
                    ('threat_feed','Threat Feed'),('rate_limit','Rate Limit Exceeded'),
                ])),
                ('description', models.TextField(blank=True)),
                ('is_permanent', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('source', models.CharField(blank=True, max_length=100)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_ip_blacklists', to='tenants.tenant')),
                ('blocked_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_blacklisted_ips',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'IP Blacklist', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='ipblacklist',
            index=models.Index(fields=['ip_address', 'is_active'], name='pi_bl_ip_active_idx'),
        ),

        # ── IPWhitelist ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='IPWhitelist',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('cidr', models.CharField(blank=True, max_length=50)),
                ('label', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_ip_whitelists', to='tenants.tenant')),
                ('added_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_whitelisted_ips',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'IP Whitelist', 'ordering': ['label']},
        ),

        # ── MaliciousIPDatabase ────────────────────────────────────────────
        migrations.CreateModel(
            name='MaliciousIPDatabase',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('threat_type', models.CharField(max_length=30, choices=[
                    ('malware','Malware'),('botnet','Botnet'),('spam','Spam'),
                    ('phishing','Phishing'),('scanner','Scanner'),('brute_force','Brute Force'),
                    ('ddos','DDoS'),('tor','Tor'),('vpn','VPN'),('proxy','Proxy'),
                ])),
                ('confidence_score', models.FloatField(default=0.0)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('first_reported', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_reported', models.DateTimeField(default=django.utils.timezone.now)),
                ('report_count', models.IntegerField(default=1)),
                ('additional_data', models.JSONField(blank=True, default=dict)),
                ('threat_feed', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='malicious_ips', to='proxy_intelligence.threatfeedprovider')),
            ],
            options={'verbose_name': 'Malicious IP', 'ordering': ['-last_reported'],
                     'unique_together': {('ip_address', 'threat_type', 'threat_feed')}},
        ),

        # ── VPNDetectionLog ────────────────────────────────────────────────
        migrations.CreateModel(
            name='VPNDetectionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('vpn_provider', models.CharField(blank=True, max_length=255)),
                ('vpn_protocol', models.CharField(blank=True, max_length=50)),
                ('confidence_score', models.FloatField(default=0.0)),
                ('detection_method', models.CharField(blank=True, max_length=100)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('action_taken', models.CharField(blank=True, max_length=50)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vpn_detection_logs', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='vpn_detections', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'VPN Detection Log', 'ordering': ['-created_at']},
        ),

        # ── ProxyDetectionLog ──────────────────────────────────────────────
        migrations.CreateModel(
            name='ProxyDetectionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('proxy_type', models.CharField(max_length=30, choices=[
                    ('residential','Residential Proxy'),('datacenter','Datacenter Proxy'),
                    ('mobile','Mobile Proxy'),('socks4','SOCKS4'),('socks5','SOCKS5'),
                    ('http','HTTP Proxy'),('https','HTTPS Proxy'),('tor','Tor Exit Node'),
                    ('unknown','Unknown'),
                ])),
                ('proxy_port', models.IntegerField(blank=True, null=True)),
                ('proxy_provider', models.CharField(blank=True, max_length=255)),
                ('confidence_score', models.FloatField(default=0.0)),
                ('is_anonymous', models.BooleanField(default=True)),
                ('is_elite', models.BooleanField(default=False)),
                ('headers_detected', models.JSONField(blank=True, default=list)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='proxy_detection_logs', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='proxy_detections', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Proxy Detection Log', 'ordering': ['-created_at']},
        ),

        # ── DeviceFingerprint ──────────────────────────────────────────────
        migrations.CreateModel(
            name='DeviceFingerprint',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fingerprint_hash', models.CharField(db_index=True, max_length=64)),
                ('user_agent', models.TextField(blank=True)),
                ('browser_name', models.CharField(blank=True, max_length=50)),
                ('browser_version', models.CharField(blank=True, max_length=20)),
                ('os_name', models.CharField(blank=True, max_length=50)),
                ('os_version', models.CharField(blank=True, max_length=20)),
                ('device_type', models.CharField(blank=True, max_length=30)),
                ('canvas_hash', models.CharField(blank=True, max_length=64)),
                ('webgl_hash', models.CharField(blank=True, max_length=64)),
                ('audio_hash', models.CharField(blank=True, max_length=64)),
                ('ip_addresses', models.JSONField(blank=True, default=list)),
                ('screen_resolution', models.CharField(blank=True, max_length=20)),
                ('timezone', models.CharField(blank=True, max_length=50)),
                ('language', models.CharField(blank=True, max_length=10)),
                ('plugins', models.JSONField(blank=True, default=list)),
                ('fonts', models.JSONField(blank=True, default=list)),
                ('first_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('visit_count', models.IntegerField(default=1)),
                ('is_suspicious', models.BooleanField(default=False)),
                ('spoofing_detected', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_device_fingerprints', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_device_fingerprints', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Device Fingerprint', 'ordering': ['-last_seen']},
        ),

        # ── UserRiskProfile ────────────────────────────────────────────────
        migrations.CreateModel(
            name='UserRiskProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('overall_risk_score', models.IntegerField(default=0)),
                ('risk_level', models.CharField(
                    choices=[('very_low','Very Low (0-20)'),('low','Low (21-40)'),
                             ('medium','Medium (41-60)'),('high','High (61-80)'),
                             ('critical','Critical (81-100)')],
                    default='very_low', max_length=20)),
                ('ip_risk_score', models.IntegerField(default=0)),
                ('behavior_risk_score', models.IntegerField(default=0)),
                ('device_risk_score', models.IntegerField(default=0)),
                ('transaction_risk_score', models.IntegerField(default=0)),
                ('identity_risk_score', models.IntegerField(default=0)),
                ('is_high_risk', models.BooleanField(db_index=True, default=False)),
                ('is_under_review', models.BooleanField(default=False)),
                ('vpn_usage_detected', models.BooleanField(default=False)),
                ('multi_account_detected', models.BooleanField(default=False)),
                ('fraud_attempts_count', models.IntegerField(default=0)),
                ('successful_fraud_count', models.IntegerField(default=0)),
                ('flagged_transactions', models.IntegerField(default=0)),
                ('last_assessed', models.DateTimeField(default=django.utils.timezone.now)),
                ('assessment_notes', models.JSONField(blank=True, default=list)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_user_risk_profiles', to='tenants.tenant')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_risk_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'User Risk Profile', 'ordering': ['-overall_risk_score']},
        ),

        # ── RiskScoreHistory ───────────────────────────────────────────────
        migrations.CreateModel(
            name='RiskScoreHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(blank=True)),
                ('previous_score', models.IntegerField(default=0)),
                ('new_score', models.IntegerField(default=0)),
                ('change_reason', models.CharField(blank=True, max_length=255)),
                ('triggered_by', models.CharField(blank=True, max_length=50)),
                ('score_delta', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='risk_score_histories', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='risk_score_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Risk Score History', 'ordering': ['-created_at']},
        ),

        # ── FraudAttempt ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='FraudAttempt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('fraud_type', models.CharField(db_index=True, max_length=50, choices=[
                    ('click_fraud','Click Fraud'),('account_fraud','Account Fraud'),
                    ('payment_fraud','Payment Fraud'),('referral_fraud','Referral Fraud'),
                    ('offer_fraud','Offer Fraud'),('identity_fraud','Identity Fraud'),
                    ('bot_activity','Bot Activity'),
                ])),
                ('status', models.CharField(db_index=True, default='detected', max_length=30, choices=[
                    ('detected','Detected'),('investigating','Under Investigation'),
                    ('confirmed','Confirmed Fraud'),('false_positive','False Positive'),
                    ('resolved','Resolved'),
                ])),
                ('risk_score', models.IntegerField(default=0)),
                ('description', models.TextField(blank=True)),
                ('evidence', models.JSONField(blank=True, default=dict)),
                ('flags', models.JSONField(blank=True, default=list)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolution_notes', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_fraud_attempts', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_fraud_attempts', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_resolved_frauds', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Fraud Attempt', 'ordering': ['-created_at']},
        ),

        # ── ClickFraudRecord ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ClickFraudRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('target_url', models.URLField(blank=True)),
                ('click_source', models.CharField(blank=True, max_length=100)),
                ('is_bot', models.BooleanField(default=False)),
                ('is_duplicate', models.BooleanField(default=False)),
                ('click_frequency', models.IntegerField(default=1)),
                ('time_on_page', models.FloatField(blank=True, null=True)),
                ('conversion', models.BooleanField(default=False)),
                ('fraud_score', models.IntegerField(default=0)),
                ('user_agent', models.TextField(blank=True)),
                ('referrer', models.URLField(blank=True)),
                ('session_id', models.CharField(blank=True, max_length=100)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='click_fraud_records', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='click_frauds', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Click Fraud Record', 'ordering': ['-created_at']},
        ),

        # ── MultiAccountLink ────────────────────────────────────────────────
        migrations.CreateModel(
            name='MultiAccountLink',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('link_type', models.CharField(max_length=30, choices=[
                    ('same_ip','Same IP Address'),('same_device','Same Device Fingerprint'),
                    ('same_email_domain','Same Email Domain'),('same_phone','Same Phone Number'),
                    ('similar_behavior','Similar Behavior Pattern'),
                ])),
                ('shared_identifier', models.CharField(blank=True, max_length=255)),
                ('confidence_score', models.FloatField(default=0.0)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('is_suspicious', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='multi_account_links', to='tenants.tenant')),
                ('primary_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='primary_account_links', to=settings.AUTH_USER_MODEL)),
                ('linked_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='linked_account_links', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Multi-Account Link', 'ordering': ['-created_at'],
                     'unique_together': {('primary_user', 'linked_user', 'link_type')}},
        ),

        # ── VelocityMetric ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='VelocityMetric',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('action_type', models.CharField(db_index=True, max_length=50)),
                ('window_seconds', models.IntegerField(default=60)),
                ('request_count', models.IntegerField(default=1)),
                ('threshold', models.IntegerField(default=60)),
                ('exceeded', models.BooleanField(db_index=True, default=False)),
                ('window_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='velocity_metrics', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='velocity_metrics', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Velocity Metric', 'ordering': ['-created_at']},
        ),

        # ── AnomalyDetectionLog ────────────────────────────────────────────
        migrations.CreateModel(
            name='AnomalyDetectionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(blank=True)),
                ('anomaly_type', models.CharField(max_length=50, choices=[
                    ('velocity_spike','Velocity Spike'),('geo_jump','Geographic Jump'),
                    ('time_anomaly','Time-based Anomaly'),('pattern_deviation','Pattern Deviation'),
                    ('unusual_volume','Unusual Volume'),('device_change','Device Change'),
                ])),
                ('description', models.TextField(blank=True)),
                ('anomaly_score', models.FloatField(default=0.0)),
                ('is_investigated', models.BooleanField(default=False)),
                ('evidence', models.JSONField(blank=True, default=dict)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='anomaly_logs', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='anomaly_logs', to=settings.AUTH_USER_MODEL)),
                ('detected_by_model', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='anomaly_detections',
                    to='proxy_intelligence.mlmodelmetadata')),
            ],
            options={'verbose_name': 'Anomaly Detection Log', 'ordering': ['-created_at']},
        ),

        # ── FraudRule ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FraudRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('rule_code', models.CharField(max_length=50, unique=True)),
                ('condition_type', models.CharField(max_length=50)),
                ('condition_value', models.JSONField(blank=True, default=dict)),
                ('action', models.CharField(max_length=30)),
                ('priority', models.IntegerField(default=10)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('trigger_count', models.BigIntegerField(default=0)),
                ('last_triggered', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_fraud_rules', to='tenants.tenant')),
            ],
            options={'verbose_name': 'PI Fraud Rule', 'ordering': ['priority', 'name']},
        ),

        # ── AlertConfiguration ─────────────────────────────────────────────
        migrations.CreateModel(
            name='AlertConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('trigger', models.CharField(max_length=50)),
                ('channel', models.CharField(max_length=20)),
                ('recipients', models.JSONField(blank=True, default=list)),
                ('webhook_url', models.URLField(blank=True)),
                ('threshold_score', models.IntegerField(default=80)),
                ('is_active', models.BooleanField(default=True)),
                ('cooldown_minutes', models.IntegerField(default=60)),
                ('last_sent', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_alert_configs', to='tenants.tenant')),
            ],
            options={'verbose_name': 'Alert Configuration', 'ordering': ['name']},
        ),

        # ── IntegrationCredential ──────────────────────────────────────────
        migrations.CreateModel(
            name='IntegrationCredential',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('service', models.CharField(max_length=50, choices=[
                    ('maxmind','MaxMind GeoIP2'),('ipqualityscore','IPQualityScore'),
                    ('abuseipdb','AbuseIPDB'),('virustotal','VirusTotal'),
                    ('shodan','Shodan'),('alienvault','AlienVault OTX'),
                    ('crowdsec','CrowdSec'),('fraudlabspro','FraudLabsPro'),
                    ('abstractapi','AbstractAPI'),
                ])),
                ('api_key', models.CharField(max_length=500)),
                ('account_id', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('daily_limit', models.IntegerField(default=1000)),
                ('used_today', models.IntegerField(default=0)),
                ('last_reset', models.DateField(blank=True, null=True)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_integration_credentials', to='tenants.tenant')),
            ],
            options={'verbose_name': 'Integration Credential',
                     'unique_together': {('tenant', 'service')}},
        ),

        # ── APIRequestLog ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='APIRequestLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('endpoint', models.CharField(db_index=True, max_length=255)),
                ('method', models.CharField(max_length=10)),
                ('status_code', models.IntegerField()),
                ('response_time_ms', models.FloatField(blank=True, null=True)),
                ('request_body', models.JSONField(blank=True, default=dict)),
                ('response_summary', models.JSONField(blank=True, default=dict)),
                ('user_agent', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_api_logs', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_api_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'API Request Log', 'ordering': ['-created_at']},
        ),

        # ── SystemAuditTrail ───────────────────────────────────────────────
        migrations.CreateModel(
            name='SystemAuditTrail',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('action', models.CharField(max_length=30, choices=[
                    ('create','Created'),('update','Updated'),('delete','Deleted'),
                    ('blacklist','Added to Blacklist'),('whitelist','Added to Whitelist'),
                    ('rule_change','Rule Changed'),('config_change','Configuration Changed'),
                    ('manual_override','Manual Override'),
                ])),
                ('model_name', models.CharField(max_length=100)),
                ('object_id', models.CharField(blank=True, max_length=100)),
                ('object_repr', models.CharField(blank=True, max_length=500)),
                ('before_state', models.JSONField(blank=True, default=dict)),
                ('after_state', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pi_audit_trails', to='tenants.tenant')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pi_audit_trails', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'System Audit Trail', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='systemaudittrail',
            index=models.Index(fields=['user', 'action', 'created_at'],
                               name='pi_audit_user_action_idx'),
        ),
        migrations.AddIndex(
            model_name='systemaudittrail',
            index=models.Index(fields=['model_name', 'object_id'],
                               name='pi_audit_model_obj_idx'),
        ),
    ]
