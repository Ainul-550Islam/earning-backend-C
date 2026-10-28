# analytics_warehouse/migrations/0001_initial.py
"""
Initial migration for analytics_warehouse app.

চালানোর কমান্ড:
  python manage.py migrate analytics_warehouse --database=analytics

settings.py-তে নিশ্চিত করো:
  INSTALLED_APPS  += ['analytics_warehouse']
  DATABASE_ROUTERS = ['analytics_warehouse.db_router.AnalyticsRouter']
  DATABASES['analytics'] = { 'ENGINE': '...postgresql', 'NAME': 'analytics_warehouse', ... }
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('publisher_tools', '0007_abtest_abtestVariant'),
        ('tenants', '__first__'),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # Shared mixin fields helper
    # ─────────────────────────────────────────────────────────────────────────
    _MIXIN_FIELDS = [
        ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('created_at',   models.DateTimeField(auto_now_add=True)),
        ('updated_at',   models.DateTimeField(auto_now=True)),
        ('record_date',  models.DateField(db_index=True)),
        ('record_hour',  models.IntegerField(blank=True, null=True)),
        ('data',         models.JSONField(blank=True, default=dict, verbose_name='Record Data')),
        ('summary',      models.JSONField(blank=True, default=dict, verbose_name='Summary Metrics')),
        ('source',       models.CharField(default='api', max_length=50, verbose_name='Data Source')),
        ('is_processed', models.BooleanField(db_index=True, default=False)),
        ('processed_at', models.DateTimeField(blank=True, null=True)),
        ('checksum',     models.CharField(blank=True, max_length=64)),
    ]
    _TENANT_FK = ('tenant', models.ForeignKey(
        blank=True, null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name='+', to='tenants.tenant',
    ))
    _PUB_FK = ('publisher', models.ForeignKey(
        db_index=True,
        on_delete=django.db.models.deletion.CASCADE,
        to='publisher_tools.publisher',
    ))

    operations = [

        # ── 1. PublisherRecord ────────────────────────────────────────────────
        migrations.CreateModel(
            name='PublisherRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
            ],
            options={
                'verbose_name':        'Publisher Record',
                'verbose_name_plural': 'Publisher Records',
                'db_table':            'aw_publisher_records',
                'ordering':            ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('PublisherRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_pub_date_01')),
        migrations.AddIndex('PublisherRecord', models.Index(fields=['is_processed'],             name='aw_idx_pub_proc_02')),

        # ── 2. SiteRecord ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='SiteRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('site', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.site',
                )),
            ],
            options={
                'verbose_name': 'Site Record', 'verbose_name_plural': 'Site Records',
                'db_table': 'aw_site_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('SiteRecord', models.Index(fields=['site', 'record_date'], name='aw_idx_site_date_03')),
        migrations.AddIndex('SiteRecord', models.Index(fields=['is_processed'],        name='aw_idx_site_proc_04')),

        # ── 3. AppRecord ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AppRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('app', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.app',
                )),
            ],
            options={
                'verbose_name': 'App Record', 'verbose_name_plural': 'App Records',
                'db_table': 'aw_app_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('AppRecord', models.Index(fields=['app', 'record_date'], name='aw_idx_app_date_05')),
        migrations.AddIndex('AppRecord', models.Index(fields=['is_processed'],       name='aw_idx_app_proc_06')),

        # ── 4. AdUnitRecord ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='AdUnitRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('ad_unit', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.adunit',
                )),
            ],
            options={
                'verbose_name': 'Ad Unit Record', 'verbose_name_plural': 'Ad Unit Records',
                'db_table': 'aw_ad_unit_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('AdUnitRecord', models.Index(fields=['ad_unit', 'record_date'], name='aw_idx_adunit_date_07')),
        migrations.AddIndex('AdUnitRecord', models.Index(fields=['is_processed'],           name='aw_idx_adunit_proc_08')),

        # ── 5. ImpressionRecord ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ImpressionRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('ad_unit', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='impression_records',
                    to='publisher_tools.adunit',
                )),
                ('impressions', models.BigIntegerField(default=0)),
                ('fill_rate',   models.DecimalField(decimal_places=4, default=0, max_digits=6)),
                ('viewability', models.DecimalField(decimal_places=4, default=0, max_digits=6)),
            ],
            options={
                'verbose_name': 'Impression Record', 'verbose_name_plural': 'Impression Records',
                'db_table': 'aw_impression_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('ImpressionRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_imp_date_09')),
        migrations.AddIndex('ImpressionRecord', models.Index(fields=['is_processed'],             name='aw_idx_imp_proc_10')),

        # ── 6. ClickRecord ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ClickRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('ad_unit', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='click_records',
                    to='publisher_tools.adunit',
                )),
                ('clicks', models.BigIntegerField(default=0)),
                ('ctr',    models.DecimalField(decimal_places=4, default=0, max_digits=6)),
            ],
            options={
                'verbose_name': 'Click Record', 'verbose_name_plural': 'Click Records',
                'db_table': 'aw_click_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('ClickRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_click_date_11')),
        migrations.AddIndex('ClickRecord', models.Index(fields=['is_processed'],             name='aw_idx_click_proc_12')),

        # ── 7. RevenueRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='RevenueRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('gross_revenue', models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ('net_revenue',   models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ('ecpm',          models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('currency',      models.CharField(default='USD', max_length=3)),
            ],
            options={
                'verbose_name': 'Revenue Record', 'verbose_name_plural': 'Revenue Records',
                'db_table': 'aw_revenue_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('RevenueRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_rev_date_13')),
        migrations.AddIndex('RevenueRecord', models.Index(fields=['is_processed'],             name='aw_idx_rev_proc_14')),

        # ── 8. InvoiceRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='InvoiceRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('invoice', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.publisherinvoice',
                )),
                ('amount',   models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('status',   models.CharField(db_index=True, default='pending', max_digits=20 if False else None, max_length=20)),
            ],
            options={
                'verbose_name': 'Invoice Record', 'verbose_name_plural': 'Invoice Records',
                'db_table': 'aw_invoice_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('InvoiceRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_inv_date_15')),
        migrations.AddIndex('InvoiceRecord', models.Index(fields=['status'],                   name='aw_idx_inv_status_16')),

        # ── 9. PaymentRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='PaymentRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('amount',   models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('method',   models.CharField(blank=True, max_length=50)),
                ('status',   models.CharField(db_index=True, default='pending', max_length=20)),
            ],
            options={
                'verbose_name': 'Payment Record', 'verbose_name_plural': 'Payment Records',
                'db_table': 'aw_payment_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('PaymentRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_pay_date_17')),
        migrations.AddIndex('PaymentRecord', models.Index(fields=['status'],                   name='aw_idx_pay_status_18')),

        # ── 10. FraudLogRecord ────────────────────────────────────────────────
        migrations.CreateModel(
            name='FraudLogRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('fraud_type',  models.CharField(db_index=True, max_length=50)),
                ('fraud_score', models.IntegerField(default=0)),
                ('ip_address',  models.GenericIPAddressField(blank=True, null=True)),
                ('action',      models.CharField(blank=True, max_length=50)),
                ('resolved',    models.BooleanField(db_index=True, default=False)),
            ],
            options={
                'verbose_name': 'Fraud Log Record', 'verbose_name_plural': 'Fraud Log Records',
                'db_table': 'aw_fraud_log_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('FraudLogRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_fraud_date_19')),
        migrations.AddIndex('FraudLogRecord', models.Index(fields=['fraud_type'],               name='aw_idx_fraud_type_20')),
        migrations.AddIndex('FraudLogRecord', models.Index(fields=['resolved'],                 name='aw_idx_fraud_res_21')),

        # ── 11. AuditLogRecord ────────────────────────────────────────────────
        migrations.CreateModel(
            name='AuditLogRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('action',      models.CharField(db_index=True, max_length=100)),
                ('actor_id',    models.CharField(blank=True, max_length=50)),
                ('object_type', models.CharField(blank=True, max_length=100)),
                ('object_id',   models.CharField(blank=True, max_length=50)),
                ('ip_address',  models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Audit Log Record', 'verbose_name_plural': 'Audit Log Records',
                'db_table': 'aw_audit_log_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('AuditLogRecord', models.Index(fields=['action'],                   name='aw_idx_audit_action_22')),
        migrations.AddIndex('AuditLogRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_audit_date_23')),

        # ── 12. AdPlacementRecord ─────────────────────────────────────────────
        migrations.CreateModel(
            name='AdPlacementRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('placement', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.adplacement',
                )),
                ('impressions', models.BigIntegerField(default=0)),
                ('revenue',     models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ('viewability', models.DecimalField(decimal_places=4, default=0, max_digits=6)),
            ],
            options={
                'verbose_name': 'Placement Record', 'verbose_name_plural': 'Placement Records',
                'db_table': 'aw_placement_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('AdPlacementRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_place_date_24')),
        migrations.AddIndex('AdPlacementRecord', models.Index(fields=['placement'],               name='aw_idx_place_id_25')),

        # ── 13. ReportRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='ReportRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('report_type', models.CharField(db_index=True, max_length=50)),
                ('report_name', models.CharField(blank=True, max_length=200)),
                ('period',      models.CharField(blank=True, max_length=20)),
                ('file_url',    models.URLField(blank=True)),
                ('status',      models.CharField(db_index=True, default='pending', max_length=20)),
            ],
            options={
                'verbose_name': 'Report Record', 'verbose_name_plural': 'Report Records',
                'db_table': 'aw_report_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('ReportRecord', models.Index(fields=['publisher', 'report_type'], name='aw_idx_rpt_type_26')),
        migrations.AddIndex('ReportRecord', models.Index(fields=['status'],                   name='aw_idx_rpt_status_27')),

        # ── 14. AlertRecord ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='AlertRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('alert_type',  models.CharField(db_index=True, max_length=50)),
                ('severity',    models.CharField(db_index=True, default='info', max_length=20)),
                ('message',     models.TextField(blank=True)),
                ('resolved',    models.BooleanField(db_index=True, default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Alert Record', 'verbose_name_plural': 'Alert Records',
                'db_table': 'aw_alert_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('AlertRecord', models.Index(fields=['publisher', 'alert_type'], name='aw_idx_alert_type_28')),
        migrations.AddIndex('AlertRecord', models.Index(fields=['severity', 'resolved'],    name='aw_idx_alert_sev_29')),

        # ── 15. WebhookLogRecord ──────────────────────────────────────────────
        migrations.CreateModel(
            name='WebhookLogRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('event_type',    models.CharField(db_index=True, max_length=100)),
                ('endpoint_url',  models.URLField(blank=True)),
                ('status',        models.CharField(db_index=True, default='pending', max_length=20)),
                ('response_code', models.IntegerField(blank=True, null=True)),
                ('attempt',       models.IntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Webhook Log Record', 'verbose_name_plural': 'Webhook Log Records',
                'db_table': 'aw_webhook_log_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('WebhookLogRecord', models.Index(fields=['publisher', 'event_type'], name='aw_idx_wh_event_30')),
        migrations.AddIndex('WebhookLogRecord', models.Index(fields=['status'],                  name='aw_idx_wh_status_31')),

        # ── 16. NotificationRecord ────────────────────────────────────────────
        migrations.CreateModel(
            name='NotificationRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('notification_type', models.CharField(db_index=True, max_length=50)),
                ('title',             models.CharField(blank=True, max_length=200)),
                ('is_read',           models.BooleanField(db_index=True, default=False)),
                ('read_at',           models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Notification Record', 'verbose_name_plural': 'Notification Records',
                'db_table': 'aw_notification_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('NotificationRecord', models.Index(fields=['publisher', 'is_read'],    name='aw_idx_notif_read_32')),
        migrations.AddIndex('NotificationRecord', models.Index(fields=['notification_type'],       name='aw_idx_notif_type_33')),

        # ── 17. SettingRecord ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='SettingRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('setting_key',   models.CharField(db_index=True, max_length=200)),
                ('setting_value', models.JSONField(blank=True, default=dict)),
                ('changed_by',    models.CharField(blank=True, max_length=50)),
            ],
            options={
                'verbose_name': 'Setting Record', 'verbose_name_plural': 'Setting Records',
                'db_table': 'aw_setting_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('SettingRecord', models.Index(fields=['publisher', 'setting_key'], name='aw_idx_setting_key_34')),

        # ── 18. APIKeyLogRecord ───────────────────────────────────────────────
        migrations.CreateModel(
            name='APIKeyLogRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('api_key_prefix', models.CharField(db_index=True, max_length=20)),
                ('endpoint',       models.CharField(blank=True, max_length=200)),
                ('method',         models.CharField(default='GET', max_length=10)),
                ('response_code',  models.IntegerField(blank=True, null=True)),
                ('requests_count', models.BigIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'API Key Log Record', 'verbose_name_plural': 'API Key Log Records',
                'db_table': 'aw_api_key_log_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('APIKeyLogRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_apilog_date_35')),
        migrations.AddIndex('APIKeyLogRecord', models.Index(fields=['api_key_prefix'],           name='aw_idx_apilog_key_36')),

        # ── 19. OptimizationLogRecord ─────────────────────────────────────────
        migrations.CreateModel(
            name='OptimizationLogRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('optimization_type', models.CharField(db_index=True, max_length=50)),
                ('target_id',         models.CharField(blank=True, max_length=50)),
                ('before_value',      models.JSONField(blank=True, default=dict)),
                ('after_value',       models.JSONField(blank=True, default=dict)),
                ('uplift_pct',        models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('applied',           models.BooleanField(db_index=True, default=False)),
            ],
            options={
                'verbose_name': 'Optimization Log Record', 'verbose_name_plural': 'Optimization Log Records',
                'db_table': 'aw_optimization_log_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('OptimizationLogRecord', models.Index(fields=['publisher', 'optimization_type'], name='aw_idx_optlog_type_37')),
        migrations.AddIndex('OptimizationLogRecord', models.Index(fields=['applied'],                        name='aw_idx_optlog_applied_38')),

        # ── 20. ABTestRecord ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='ABTestRecord',
            fields=[
                *_MIXIN_FIELDS,
                _TENANT_FK,
                _PUB_FK,
                ('ab_test', models.ForeignKey(
                    blank=True, null=True, db_index=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warehouse_records',
                    to='publisher_tools.abtest',
                )),
                ('test_type',        models.CharField(blank=True, db_index=True, max_length=20)),
                ('variant_name',     models.CharField(blank=True, max_length=100)),
                ('is_control',       models.BooleanField(default=False)),
                ('impressions',      models.BigIntegerField(default=0)),
                ('revenue',          models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ('ecpm',             models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('confidence_level', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
            ],
            options={
                'verbose_name': 'A/B Test Record', 'verbose_name_plural': 'A/B Test Records',
                'db_table': 'aw_ab_test_records', 'ordering': ['-record_date', '-created_at'],
            },
        ),
        migrations.AddIndex('ABTestRecord', models.Index(fields=['publisher', 'record_date'], name='aw_idx_abtest_date_39')),
        migrations.AddIndex('ABTestRecord', models.Index(fields=['test_type'],               name='aw_idx_abtest_type_40')),
    ]
