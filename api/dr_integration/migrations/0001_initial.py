# Generated migration for DR Integration models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DRSystemStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('overall_health', models.CharField(default='unknown', max_length=20)),
                ('last_backup_at', models.DateTimeField(blank=True, null=True)),
                ('last_failover_at', models.DateTimeField(blank=True, null=True)),
                ('replication_lag_seconds', models.FloatField(blank=True, null=True)),
                ('active_incidents', models.IntegerField(default=0)),
                ('active_alerts', models.IntegerField(default=0)),
                ('rto_achieved_seconds', models.FloatField(blank=True, null=True)),
                ('rpo_achieved_seconds', models.FloatField(blank=True, null=True)),
                ('raw_status', models.JSONField(default=dict)),
                ('synced_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='DRBackupRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('dr_job_id', models.CharField(max_length=100, unique=True)),
                ('backup_type', models.CharField(choices=[('full','Full'),('incremental','Incremental'),('differential','Differential')], max_length=20)),
                ('status', models.CharField(choices=[('pending','Pending'),('running','Running'),('completed','Completed'),('failed','Failed'),('verified','Verified')], default='pending', max_length=20)),
                ('source_size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('compressed_size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('storage_path', models.TextField(blank=True)),
                ('checksum', models.CharField(blank=True, max_length=64)),
                ('is_verified', models.BooleanField(default=False)),
                ('encryption_enabled', models.BooleanField(default=True)),
                ('compression_enabled', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(default=dict)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
                ('triggered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DRRestoreRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('dr_request_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('restore_type', models.CharField(choices=[('full','Full'),('partial','Partial'),('table','Table'),('point_in_time','Point In Time')], max_length=20)),
                ('status', models.CharField(choices=[('pending','Pending'),('approved','Approved'),('running','Running'),('completed','Completed'),('failed','Failed'),('rolled_back','Rolled Back')], default='pending', max_length=20)),
                ('target_database', models.CharField(max_length=100)),
                ('point_in_time', models.DateTimeField(blank=True, null=True)),
                ('approval_status', models.CharField(default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dr_restore_approvals', to=settings.AUTH_USER_MODEL)),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dr_restore_requests', to=settings.AUTH_USER_MODEL)),
                ('source_backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='dr_integration.drbackuprecord')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DRFailoverEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('dr_failover_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('failover_type', models.CharField(choices=[('automatic','Automatic'),('manual','Manual'),('scheduled','Scheduled'),('drill','Drill')], max_length=20)),
                ('status', models.CharField(choices=[('initiated','Initiated'),('in_progress','In Progress'),('completed','Completed'),('failed','Failed'),('rolled_back','Rolled Back')], max_length=20)),
                ('primary_node', models.CharField(max_length=200)),
                ('secondary_node', models.CharField(max_length=200)),
                ('trigger_reason', models.TextField()),
                ('rto_achieved_seconds', models.FloatField(blank=True, null=True)),
                ('is_drill', models.BooleanField(default=False)),
                ('initiated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
                ('triggered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-initiated_at']},
        ),
        migrations.CreateModel(
            name='DRAlert',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('dr_alert_id', models.CharField(blank=True, max_length=100)),
                ('rule_name', models.CharField(max_length=200)),
                ('severity', models.CharField(choices=[('info','Info'),('warning','Warning'),('error','Error'),('critical','Critical')], max_length=20)),
                ('message', models.TextField()),
                ('metric', models.CharField(blank=True, max_length=100)),
                ('metric_value', models.FloatField(blank=True, null=True)),
                ('threshold', models.FloatField(blank=True, null=True)),
                ('is_acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('fired_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tenants.tenant')),
            ],
            options={'ordering': ['-fired_at']},
        ),
        migrations.CreateModel(
            name='DRDrillRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('dr_drill_id', models.CharField(blank=True, max_length=100)),
                ('name', models.CharField(max_length=200)),
                ('scenario_type', models.CharField(max_length=50)),
                ('status', models.CharField(choices=[('scheduled','Scheduled'),('running','Running'),('completed','Completed'),('failed','Failed'),('cancelled','Cancelled')], default='scheduled', max_length=20)),
                ('passed', models.BooleanField(null=True)),
                ('scheduled_at', models.DateTimeField()),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('achieved_rto_seconds', models.FloatField(blank=True, null=True)),
                ('target_rto_seconds', models.IntegerField(blank=True, null=True)),
                ('achieved_rpo_seconds', models.FloatField(blank=True, null=True)),
                ('target_rpo_seconds', models.IntegerField(blank=True, null=True)),
                ('participants', models.JSONField(default=list)),
                ('lessons_learned', models.TextField(blank=True)),
                ('planned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-scheduled_at']},
        ),
        migrations.AddIndex(
            model_name='drbackuprecord',
            index=models.Index(fields=['status', 'created_at'], name='dr_backup_status_idx'),
        ),
        migrations.AddIndex(
            model_name='drbackuprecord',
            index=models.Index(fields=['tenant', 'status'], name='dr_backup_tenant_idx'),
        ),
    ]
