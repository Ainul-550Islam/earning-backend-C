# =============================================================================
# INTEGRATION_SYSTEM/migrations/0002_add_indexes.py
# =============================================================================
"""
Add performance indexes for Integration System models.

Adds additional database indexes to optimize query performance
for high-volume integration operations and reporting.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('INTEGRATION_SYSTEM', '0001_initial'),
    ]

    operations = [
        # Additional indexes for Integration model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integration_name_trigram "
            "ON integration_system_integrations USING gin (name gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS idx_integration_name_trigram;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integration_config_gin "
            "ON integration_system_integrations USING gin (config);",
            reverse_sql="DROP INDEX IF EXISTS idx_integration_config_gin;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integration_metadata_gin "
            "ON integration_system_integrations USING gin (metadata);",
            reverse_sql="DROP INDEX IF EXISTS idx_integration_metadata_gin;"
        ),
        
        # Performance indexes for IntegrationLog model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationlog_integration_created_success "
            "ON integration_system_logs (integration_id, created_at, success);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationlog_integration_created_success;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationlog_operation_type_status "
            "ON integration_system_logs (operation_type, status_code);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationlog_operation_type_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationlog_execution_time "
            "ON integration_system_logs (execution_time_ms) WHERE execution_time_ms IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationlog_execution_time;"
        ),
        
        # Indexes for WebhookConfiguration model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookconfig_active_created "
            "ON integration_system_webhooks (active, created_at);",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookconfig_active_created;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookconfig_events_gin "
            "ON integration_system_webhooks USING gin (events);",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookconfig_events_gin;"
        ),
        
        # Indexes for WebhookDelivery model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookdelivery_status_created "
            "ON integration_system_webhook_deliveries (status, created_at);",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookdelivery_status_created;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookdelivery_event_type_status "
            "ON integration_system_webhook_deliveries (event_type, status);",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookdelivery_event_type_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookdelivery_next_retry "
            "ON integration_system_webhook_deliveries (next_retry_at) WHERE next_retry_at IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookdelivery_next_retry;"
        ),
        
        # Indexes for CircuitBreakerState model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_circuitbreaker_state_failure_rate "
            "ON integration_system_circuit_breakers (state, failure_count, total_requests);",
            reverse_sql="DROP INDEX IF EXISTS idx_circuitbreaker_state_failure_rate;"
        ),
        
        # Indexes for IntegrationMetric model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationmetric_name_timestamp "
            "ON integration_system_metrics (metric_name, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationmetric_name_timestamp;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationmetric_integration_period "
            "ON integration_system_metrics (integration_id, period_start, period_end);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationmetric_integration_period;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationmetric_labels_gin "
            "ON integration_system_metrics USING gin (labels);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationmetric_labels_gin;"
        ),
        
        # Indexes for IntegrationAuditLog model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_integration_timestamp_level "
            "ON integration_system_audit_logs (integration_id, timestamp DESC, level);",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_integration_timestamp_level;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_user_timestamp "
            "ON integration_system_audit_logs (user_id, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_user_timestamp;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_action_category "
            "ON integration_system_audit_logs (action_type, category);",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_action_category;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_details_gin "
            "ON integration_system_audit_logs USING gin (details);",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_details_gin;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_correlation_id "
            "ON integration_system_audit_logs (correlation_id) WHERE correlation_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_correlation_id;"
        ),
        
        # Indexes for DataSyncOperation model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncoperation_status_created "
            "ON integration_system_sync_operations (status, created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_syncoperation_status_created;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncoperation_systems_type "
            "ON integration_system_sync_operations (source_system, target_system, operation_type);",
            reverse_sql="DROP INDEX IF EXISTS idx_syncoperation_systems_type;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncoperation_performance "
            "ON integration_system_sync_operations (processed_records, total_records) WHERE total_records > 0;",
            reverse_sql="DROP INDEX IF EXISTS idx_syncoperation_performance;"
        ),
        
        # Indexes for DataSyncConflict model
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncconflict_type_status_detected "
            "ON integration_system_sync_conflicts (conflict_type, resolution_status, detected_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_syncconflict_type_status_detected;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncconflict_source_target "
            "ON integration_system_sync_conflicts (source_record_id, target_record_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_syncconflict_source_target;"
        ),
        
        # Partial indexes for better performance
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integration_active_only "
            "ON integration_system_integrations (name, created_at) WHERE status = 'active';",
            reverse_sql="DROP INDEX IF EXISTS idx_integration_active_only;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationlog_failed_only "
            "ON integration_system_logs (integration_id, created_at) WHERE success = false;",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationlog_failed_only;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookdelivery_pending_retry "
            "ON integration_system_webhook_deliveries (webhook_id, next_retry_at) WHERE status = 'pending';",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookdelivery_pending_retry;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auditlog_security_only "
            "ON integration_system_audit_logs (timestamp, user_id) WHERE level = 'security';",
            reverse_sql="DROP INDEX IF EXISTS idx_auditlog_security_only;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_syncoperation_failed_only "
            "ON integration_system_sync_operations (created_at, error_message) WHERE status = 'failed';",
            reverse_sql="DROP INDEX IF EXISTS idx_syncoperation_failed_only;"
        ),
        
        # Composite indexes for common query patterns
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integration_type_status_health "
            "ON integration_system_integrations (integration_type, status, health_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_integration_type_status_health;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_integrationlog_user_integration_timestamp "
            "ON integration_system_logs (user_id, integration_id, created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_integrationlog_user_integration_timestamp;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhookdelivery_webhook_event_status "
            "ON integration_system_webhook_deliveries (webhook_id, event_type, status, created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_webhookdelivery_webhook_event_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metric_integration_name_period_timestamp "
            "ON integration_system_metrics (integration_id, metric_name, period_start, timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_metric_integration_name_period_timestamp;"
        ),
        
        # Update table statistics for better query planning
        migrations.RunSQL(
            "ANALYZE integration_system_integrations;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_logs;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_webhooks;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_webhook_deliveries;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_circuit_breakers;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_metrics;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_audit_logs;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_sync_operations;",
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            "ANALYZE integration_system_sync_conflicts;",
            reverse_sql=""
        ),
    ]
