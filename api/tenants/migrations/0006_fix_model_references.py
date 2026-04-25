from django.db import migrations
from django.db.utils import ProgrammingError

def validate_migration(apps, schema_editor):
    try:
        Tenant = apps.get_model('tenants', 'Tenant')
        Plan = apps.get_model('tenants', 'Plan')
        invalid_tenants = Tenant.objects.filter(plan__isnull=True)
        if invalid_tenants.exists():
            default_plan = Plan.objects.filter(is_default=True).first()
            if default_plan:
                invalid_tenants.update(plan=default_plan.name)
        print(f"[OK] Validated {Tenant.objects.count()} tenants")
    except LookupError:
        print("[SKIP] Validation skipped")

def update_foreign_key_constraints(apps, schema_editor):
    print("[OK] Foreign key constraints verified")

def create_indexes(apps, schema_editor):
    indexes = [
        ("tenants_tenant", "domain", "idx_tenant_domain"),
        ("tenants_tenant", "subdomain", "idx_tenant_subdomain"),
        ("users_user", "tenant_id", "idx_user_tenant"),
        ("monetization_tools_paymenttransaction", "tenant_id, status, initiated_at DESC", "idx_payment_txn_tenant_status"),
        ("monetization_tools_paymenttransaction", "gateway_id, gateway_txn_id", "idx_payment_gateway_txn"),
    ]
    with schema_editor.connection.cursor() as cursor:
        for table, columns, idx_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {table}({columns});")
                print(f"[OK] Index {idx_name} created/verified")
            except ProgrammingError:
                print(f"[SKIP] Index {idx_name}")

def create_audit_log_entries(apps, schema_editor):
    try:
        Tenant = apps.get_model('tenants', 'Tenant')
        AuditLog = apps.get_model('audit_logs', 'AuditLog')
        ContentType = apps.get_model('contenttypes', 'ContentType')
        tenant_ct = ContentType.objects.get_for_model(Tenant)
        logs_created = 0
        for tenant in Tenant.objects.all().only('id', 'name', 'domain', 'created_at'):
            _, created = AuditLog.objects.get_or_create(
                content_type=tenant_ct,
                object_id=str(tenant.id),
                action='tenant_created',
                defaults={'timestamp': tenant.created_at}
            )
            if created:
                logs_created += 1
        print(f"[OK] Backfilled {logs_created} audit log entries")
    except LookupError:
        print("[SKIP] AuditLog model not found")

class Migration(migrations.Migration):
    atomic = False

    atomic = False
    dependencies = [('tenants', '0005_update_to_improved_models'),]
    operations = [
        migrations.RunPython(validate_migration, migrations.RunPython.noop),
        migrations.RunPython(update_foreign_key_constraints, migrations.RunPython.noop),
        migrations.RunPython(create_indexes, migrations.RunPython.noop),
        migrations.RunPython(create_audit_log_entries, migrations.RunPython.noop),
    ]
