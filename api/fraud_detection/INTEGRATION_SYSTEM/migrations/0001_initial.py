# =============================================================================
# INTEGRATION_SYSTEM/migrations/0001_initial.py
# =============================================================================
"""
Initial migration for Integration System models.

Creates the database tables for the integration system
including integrations, logs, webhooks, circuit breakers,
metrics, versions, audit logs, and sync operations.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Integration model
        migrations.CreateModel(
            name='Integration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('name', models.CharField(db_index=True, max_length=200, unique=True)),
                ('display_name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('integration_type', models.CharField(choices=[
                    ('api', 'API'),
                    ('webhook', 'Webhook'),
                    ('database', 'Database'),
                    ('message_queue', 'MessageQueue'),
                    ('file', 'File'),
                    ('custom', 'Custom')
                ], db_index=True, max_length=50)),
                ('authentication_type', models.CharField(choices=[
                    ('none', 'None'),
                    ('api_key', 'APIKey'),
                    ('oauth', 'OAuth'),
                    ('jwt', 'JWT'),
                    ('basic', 'Basic'),
                    ('bearer', 'Bearer')
                ], default='none', max_length=50)),
                ('base_url', models.URLField(blank=True, max_length=500)),
                ('endpoint', models.CharField(blank=True, max_length=500)),
                ('timeout', models.IntegerField(default=30)),
                ('retry_attempts', models.IntegerField(default=3)),
                ('retry_delay', models.IntegerField(default=5)),
                ('status', models.CharField(choices=[
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                    ('error', 'Error'),
                    ('maintenance', 'Maintenance')
                ], db_index=True, default='inactive', max_length=50)),
                ('health_status', models.CharField(db_index=True, default='unknown', max_length=50)),
                ('last_health_check', models.DateTimeField(blank=True, null=True)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('credentials', models.JSONField(blank=True, default=dict)),
                ('rate_limit_per_minute', models.IntegerField(default=60)),
                ('rate_limit_per_hour', models.IntegerField(default=1000)),
                ('rate_limit_per_day', models.IntegerField(default=10000)),
                ('version', models.CharField(default='1.0.0', max_length=50)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_integrations', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_integrations', to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'integration_system_integrations',
                'indexes': [
                    models.Index(fields=['name']),
                    models.Index(fields=['integration_type']),
                    models.Index(fields=['status']),
                    models.Index(fields=['health_status']),
                    models.Index(fields=['created_at']),
                    models.Index(fields=['integration_type', 'status']),
                ],
                'ordering': ['-created_at'],
            },
        ),
        
        # IntegrationLog model
        migrations.CreateModel(
            name='IntegrationLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('operation_type', models.CharField(db_index=True, max_length=100)),
                ('method', models.CharField(blank=True, max_length=10)),
                ('endpoint', models.CharField(blank=True, max_length=500)),
                ('request_data', models.JSONField(blank=True, default=dict)),
                ('response_data', models.JSONField(blank=True, default=dict)),
                ('headers', models.JSONField(blank=True, default=dict)),
                ('status_code', models.IntegerField(blank=True, null=True)),
                ('success', models.BooleanField(db_index=True, default=True)),
                ('error_message', models.TextField(blank=True)),
                ('execution_time_ms', models.IntegerField(blank=True, null=True)),
                ('request_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('correlation_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('user_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('integration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_logs',
                'indexes': [
                    models.Index(fields=['integration', 'created_at']),
                    models.Index(fields=['operation_type']),
                    models.Index(fields=['success']),
                    models.Index(fields=['request_id']),
                    models.Index(fields=['correlation_id']),
                    models.Index(fields=['user_id']),
                    models.Index(fields=['created_at']),
                    models.Index(fields=['integration', 'success', 'created_at']),
                ],
                'ordering': ['-created_at'],
            },
        ),
        
        # WebhookConfiguration model
        migrations.CreateModel(
            name='WebhookConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('url', models.URLField(max_length=500)),
                ('secret', models.CharField(blank=True, max_length=255)),
                ('events', models.JSONField(blank=True, default=list)),
                ('event_filters', models.JSONField(blank=True, default=dict)),
                ('timeout', models.IntegerField(default=30)),
                ('retry_attempts', models.IntegerField(default=3)),
                ('retry_delay', models.IntegerField(default=5)),
                ('signature_header', models.CharField(default='X-Webhook-Signature', max_length=100)),
                ('signature_algorithm', models.CharField(default='sha256', max_length=50)),
                ('active', models.BooleanField(db_index=True, default=True)),
                ('last_delivery', models.DateTimeField(blank=True, null=True)),
                ('delivery_count', models.IntegerField(default=0)),
                ('failure_count', models.IntegerField(default=0)),
                ('headers', models.JSONField(blank=True, default=dict)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('integration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webhooks', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_webhooks',
                'indexes': [
                    models.Index(fields=['integration', 'active']),
                    models.Index(fields=['url']),
                    models.Index(fields=['active']),
                    models.Index(fields=['last_delivery']),
                ],
                'ordering': ['-created_at'],
            },
        ),
        
        # WebhookDelivery model
        migrations.CreateModel(
            name='WebhookDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('event_id', models.CharField(db_index=True, max_length=100)),
                ('event_type', models.CharField(db_index=True, max_length=100)),
                ('event_data', models.JSONField(blank=True, default=dict)),
                ('delivery_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('attempt_count', models.IntegerField(default=1)),
                ('status', models.CharField(db_index=True, default='pending', max_length=50)),
                ('status_code', models.IntegerField(blank=True, null=True)),
                ('response_body', models.TextField(blank=True)),
                ('response_headers', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('last_error', models.TextField(blank=True)),
                ('webhook', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='INTEGRATION_SYSTEM.webhookconfiguration')),
            ],
            options={
                'db_table': 'integration_system_webhook_deliveries',
                'indexes': [
                    models.Index(fields=['webhook', 'status']),
                    models.Index(fields=['event_id']),
                    models.Index(fields=['event_type']),
                    models.Index(fields=['delivery_id']),
                    models.Index(fields=['status', 'created_at']),
                    models.Index(fields=['next_retry_at']),
                ],
                'ordering': ['-created_at'],
            },
        ),
        
        # CircuitBreakerState model
        migrations.CreateModel(
            name='CircuitBreakerState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('state', models.CharField(choices=[
                    ('closed', 'Closed'),
                    ('open', 'Open'),
                    ('half_open', 'HalfOpen')
                ], db_index=True, default='closed', max_length=50)),
                ('failure_threshold', models.IntegerField(default=5)),
                ('recovery_timeout', models.IntegerField(default=60)),
                ('success_threshold', models.IntegerField(default=3)),
                ('failure_count', models.IntegerField(default=0)),
                ('success_count', models.IntegerField(default=0)),
                ('total_requests', models.IntegerField(default=0)),
                ('last_failure_time', models.DateTimeField(blank=True, null=True)),
                ('last_success_time', models.DateTimeField(blank=True, null=True)),
                ('last_state_change', models.DateTimeField(auto_now=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('integration', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='circuit_breaker', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_circuit_breakers',
                'indexes': [
                    models.Index(fields=['integration']),
                    models.Index(fields=['state']),
                    models.Index(fields=['last_state_change']),
                ],
            },
        ),
        
        # IntegrationMetric model
        migrations.CreateModel(
            name='IntegrationMetric',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('metric_name', models.CharField(db_index=True, max_length=100)),
                ('metric_type', models.CharField(max_length=50)),
                ('value', models.DecimalField(decimal_places=6, max_digits=20)),
                ('unit', models.CharField(blank=True, max_length=50)),
                ('labels', models.JSONField(blank=True, default=dict)),
                ('dimensions', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('period_start', models.DateTimeField()),
                ('period_end', models.DateTimeField()),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('integration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_metrics',
                'indexes': [
                    models.Index(fields=['integration', 'metric_name']),
                    models.Index(fields=['metric_name']),
                    models.Index(fields=['timestamp']),
                    models.Index(fields=['period_start', 'period_end']),
                    models.Index(fields=['integration', 'timestamp']),
                ],
                'ordering': ['-timestamp'],
            },
        ),
        
        # IntegrationVersion model
        migrations.CreateModel(
            name='IntegrationVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('version', models.CharField(db_index=True, max_length=50)),
                ('version_number', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(db_index=True, default=False)),
                ('config_snapshot', models.JSONField(blank=True, default=dict)),
                ('schema_version', models.CharField(blank=True, max_length=50)),
                ('compatible_from_version', models.CharField(blank=True, max_length=50)),
                ('compatible_to_version', models.CharField(blank=True, max_length=50)),
                ('deprecated_at', models.DateTimeField(blank=True, null=True)),
                ('migration_required', models.BooleanField(default=False)),
                ('migration_script', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_integration_versions', to=settings.AUTH_USER_MODEL)),
                ('integration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_versions',
                'indexes': [
                    models.Index(fields=['integration', 'version']),
                    models.Index(fields=['version_number']),
                    models.Index(fields=['is_active']),
                    models.Index(fields=['deprecated_at']),
                ],
                'ordering': ['-created_at'],
                'unique_together': {('integration', 'version')},
            },
        ),
        
        # IntegrationAuditLog model
        migrations.CreateModel(
            name='IntegrationAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('action', models.CharField(db_index=True, max_length=100)),
                ('action_type', models.CharField(db_index=True, max_length=50)),
                ('resource_type', models.CharField(db_index=True, max_length=50)),
                ('resource_id', models.CharField(blank=True, max_length=100)),
                ('user_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('username', models.CharField(blank=True, max_length=255)),
                ('session_id', models.CharField(blank=True, max_length=255)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('message', models.TextField()),
                ('details', models.JSONField(blank=True, default=dict)),
                ('old_values', models.JSONField(blank=True, default=dict)),
                ('new_values', models.JSONField(blank=True, default=dict)),
                ('level', models.CharField(choices=[
                    ('debug', 'Debug'),
                    ('info', 'Info'),
                    ('warning', 'Warning'),
                    ('error', 'Error'),
                    ('critical', 'Critical'),
                    ('security', 'Security')
                ], db_index=True, default='info', max_length=20)),
                ('category', models.CharField(blank=True, db_index=True, max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('correlation_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('integration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='INTEGRATION_SYSTEM.integration')),
            ],
            options={
                'db_table': 'integration_system_audit_logs',
                'indexes': [
                    models.Index(fields=['integration', 'timestamp']),
                    models.Index(fields=['action_type']),
                    models.Index(fields=['resource_type']),
                    models.Index(fields=['user_id']),
                    models.Index(fields=['level']),
                    models.Index(fields=['category']),
                    models.Index(fields=['timestamp']),
                    models.Index(fields=['correlation_id']),
                    models.Index(fields=['integration', 'action_type', 'timestamp']),
                ],
                'ordering': ['-timestamp'],
            },
        ),
        
        # DataSyncOperation model
        migrations.CreateModel(
            name='DataSyncOperation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('sync_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('source_system', models.CharField(db_index=True, max_length=100)),
                ('target_system', models.CharField(db_index=True, max_length=100)),
                ('operation_type', models.CharField(db_index=True, max_length=100)),
                ('status', models.CharField(db_index=True, default='pending', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('total_records', models.IntegerField(default=0)),
                ('processed_records', models.IntegerField(default=0)),
                ('failed_records', models.IntegerField(default=0)),
                ('conflict_records', models.IntegerField(default=0)),
                ('resolution_strategy', models.CharField(blank=True, max_length=50)),
                ('batch_size', models.IntegerField(default=100)),
                ('error_message', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'db_table': 'integration_system_sync_operations',
                'indexes': [
                    models.Index(fields=['sync_id']),
                    models.Index(fields=['source_system', 'target_system']),
                    models.Index(fields=['status']),
                    models.Index(fields=['created_at']),
                    models.Index(fields=['operation_type']),
                ],
                'ordering': ['-created_at'],
            },
        ),
        
        # DataSyncConflict model
        migrations.CreateModel(
            name='DataSyncConflict',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('conflict_id', models.CharField(db_index=True, max_length=100)),
                ('conflict_type', models.CharField(db_index=True, max_length=50)),
                ('field_name', models.CharField(blank=True, max_length=100)),
                ('source_record_id', models.CharField(db_index=True, max_length=100)),
                ('target_record_id', models.CharField(blank=True, max_length=100)),
                ('source_data', models.JSONField(blank=True, default=dict)),
                ('target_data', models.JSONField(blank=True, default=dict)),
                ('resolution_status', models.CharField(db_index=True, default='pending', max_length=50)),
                ('resolution_strategy', models.CharField(blank=True, max_length=50)),
                ('resolved_data', models.JSONField(blank=True, default=dict)),
                ('description', models.TextField()),
                ('detected_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('sync_operation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conflicts', to='INTEGRATION_SYSTEM.datasyncoperation')),
            ],
            options={
                'db_table': 'integration_system_sync_conflicts',
                'indexes': [
                    models.Index(fields=['sync_operation', 'conflict_type']),
                    models.Index(fields=['conflict_id']),
                    models.Index(fields=['source_record_id']),
                    models.Index(fields=['resolution_status']),
                    models.Index(fields=['detected_at']),
                ],
                'ordering': ['-detected_at'],
            },
        ),
    ]
