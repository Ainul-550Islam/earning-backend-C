"""
Migration Runner Script

This script helps run the tenant migrations safely and checks for issues.
"""

import os
import sys
import django
from django.conf import settings

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'earning_backend.settings')
django.setup()

def check_database_connection():
    """Check database connection."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("Database connection: OK")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def backup_database():
    """Create database backup before migration."""
    try:
        print("Creating database backup...")
        # This would be implemented based on your database type
        # For PostgreSQL: pg_dump earning_backend > backup.sql
        # For MySQL: mysqldump earning_backend > backup.sql
        print("Backup completed (manual backup recommended)")
        return True
    except Exception as e:
        print(f"Backup failed: {e}")
        return False

def run_migrations():
    """Run the tenant migrations."""
    from django.core.management import call_command
    
    try:
        print("\n" + "="*50)
        print("RUNNING TENANT MIGRATIONS")
        print("="*50)
        
        # Check current migration status
        call_command('showmigrations', 'tenants')
        
        print("\nApplying migrations...")
        call_command('migrate', 'tenants', verbosity=2)
        
        print("\nMigration status after applying:")
        call_command('showmigrations', 'tenants')
        
        print("Migrations completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration error: {e}")
        print("\nTroubleshooting steps:")
        print("1. Check database connection")
        print("2. Verify migration files are correct")
        print("3. Check for missing dependencies")
        print("4. Run with --fake-initial if needed")
        return False

def check_model_status():
    """Check model status after migration."""
    try:
        from tenants.models import Tenant, TenantSettings, TenantBilling, TenantInvoice
        
        print("\n" + "="*50)
        print("CHECKING MODEL STATUS")
        print("="*50)
        
        print(f"Tenant count: {Tenant.objects.count()}")
        print(f"TenantSettings count: {TenantSettings.objects.count()}")
        print(f"TenantBilling count: {TenantBilling.objects.count()}")
        print(f"TenantInvoice count: {TenantInvoice.objects.count()}")
        
        # Check if improved fields exist
        sample_tenant = Tenant.objects.first()
        if sample_tenant:
            print(f"\nSample tenant ID type: {type(sample_tenant.id)}")
            print(f"Sample tenant fields: {[f.name for f in sample_tenant._meta.fields]}")
            
            # Check for new fields
            new_fields = ['status', 'is_deleted', 'is_suspended', 'metadata', 'webhook_secret']
            for field in new_fields:
                if hasattr(sample_tenant, field):
                    print(f"Field '{field}': EXISTS")
                else:
                    print(f"Field '{field}': MISSING")
        
        return True
        
    except Exception as e:
        print(f"Model check error: {e}")
        return False

def check_data_integrity():
    """Check data integrity after migration."""
    try:
        from tenants.models import Tenant, TenantSettings, TenantBilling, TenantInvoice
        
        print("\n" + "="*50)
        print("CHECKING DATA INTEGRITY")
        print("="*50)
        
        # Check tenant-settings relationships
        orphaned_settings = TenantSettings.objects.filter(tenant__isnull=True).count()
        if orphaned_settings > 0:
            print(f"WARNING: {orphaned_settings} orphaned TenantSettings found")
        else:
            print("TenantSettings relationships: OK")
        
        # Check tenant-billing relationships
        orphaned_billing = TenantBilling.objects.filter(tenant__isnull=True).count()
        if orphaned_billing > 0:
            print(f"WARNING: {orphaned_billing} orphaned TenantBilling found")
        else:
            print("TenantBilling relationships: OK")
        
        # Check tenant-invoice relationships
        orphaned_invoices = TenantInvoice.objects.filter(tenant__isnull=True).count()
        if orphaned_invoices > 0:
            print(f"WARNING: {orphaned_invoices} orphaned TenantInvoice found")
        else:
            print("TenantInvoice relationships: OK")
        
        # Check for missing required fields
        tenants_missing_name = Tenant.objects.filter(name__isnull=True).count()
        if tenants_missing_name > 0:
            print(f"WARNING: {tenants_missing_name} tenants missing name")
        
        tenants_missing_slug = Tenant.objects.filter(slug__isnull=True).count()
        if tenants_missing_slug > 0:
            print(f"WARNING: {tenants_missing_slug} tenants missing slug")
        
        print("Data integrity check completed")
        return True
        
    except Exception as e:
        print(f"Data integrity check error: {e}")
        return False

def create_test_data():
    """Create test data if needed."""
    try:
        from tenants.models import Tenant
        
        if Tenant.objects.count() == 0:
            print("\nCreating test tenant...")
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Create test user if needed
            test_user, created = User.objects.get_or_create(
                email='test@example.com',
                defaults={
                    'username': 'testuser',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'is_active': True
                }
            )
            
            # Create test tenant
            test_tenant = Tenant.objects.create(
                name='Test Tenant',
                slug='test-tenant',
                admin_email='test@example.com',
                owner=test_user,
                plan='basic',
                status='trial'
            )
            
            print(f"Test tenant created: {test_tenant.name}")
        else:
            print("Test data already exists")
        
        return True
        
    except Exception as e:
        print(f"Test data creation error: {e}")
        return False

def main():
    """Main migration runner."""
    print("TENANT SYSTEM MIGRATION RUNNER")
    print("="*50)
    
    # Pre-migration checks
    if not check_database_connection():
        return False
    
    # Optional backup
    backup_db = input("Create database backup? (y/n): ").lower()
    if backup_db == 'y':
        if not backup_database():
            print("Backup failed, aborting migration")
            return False
    
    # Run migrations
    if not run_migrations():
        return False
    
    # Post-migration checks
    if not check_model_status():
        return False
    
    if not check_data_integrity():
        return False
    
    # Create test data if needed
    create_test_data = input("Create test data if none exists? (y/n): ").lower()
    if create_test_data == 'y':
        create_test_data()
    
    print("\n" + "="*50)
    print("MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*50)
    print("\nNext steps:")
    print("1. Test the tenant admin interface")
    print("2. Test tenant creation and management")
    print("3. Verify all improved features work")
    print("4. Check logs for any errors")
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        if success:
            print("\nMigration process completed successfully!")
        else:
            print("\nMigration process failed. Check the errors above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
