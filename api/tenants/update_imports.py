"""
Update Imports Script for Tenant System

This script updates all import references in improved files to use
the correct model references and fix circular dependencies.
"""

import os
import re
from pathlib import Path

def update_file_imports(file_path, old_imports, new_imports):
    """Update imports in a specific file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update imports
        for old_import, new_import in zip(old_imports, new_imports):
            content = content.replace(old_import, new_import)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Updated imports in: {file_path}")
        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def update_all_imports():
    """Update imports in all improved tenant files."""
    tenant_dir = Path(__file__).parent
    
    # Files to update
    files_to_update = [
        'serializers_improved.py',
        'views_improved.py', 
        'permissions_improved.py',
        'services_improved.py',
        'middleware_improved.py',
        'admin_improved.py',
        'apps_improved.py',
        'signals_improved.py',
        'consumers.py',
        'decorators.py',
        'filters.py',
        'managers.py',
        'receivers.py',
        'routing.py',
        'tasks_improved.py',
        'attachment_upload_view.py',
        'celery_beat_config.py',
    ]
    
    # Import mappings
    import_mappings = {
        # Model imports
        'from .models_improved import': 'from .models import',
        'from .models_improved import (': 'from .models import (',
        'models_improved import': 'models import',
        
        # Service imports
        'from .services_improved import': 'from .services import',
        'services_improved import': 'services import',
        
        # Permission imports  
        'from .permissions_improved import': 'from .permissions import',
        'permissions_improved import': 'permissions import',
        
        # Serializer imports
        'from .serializers_improved import': 'from .serializers import',
        'serializers_improved import': 'serializers import',
        
        # View imports
        'from .views_improved import': 'from .views import',
        'views_improved import': 'views import',
    }
    
    # Update each file
    updated_files = 0
    for filename in files_to_update:
        file_path = tenant_dir / filename
        if file_path.exists():
            old_imports = list(import_mappings.keys())
            new_imports = list(import_mappings.values())
            
            if update_file_imports(file_path, old_imports, new_imports):
                updated_files += 1
    
    print(f"Updated imports in {updated_files} files")

def create_compatibility_imports():
    """Create compatibility import files."""
    tenant_dir = Path(__file__).parent
    
    # Create models compatibility
    models_content = '''
"""
Models Compatibility Layer

This file provides backward compatibility for model imports.
"""

try:
    from .models_improved import *
except ImportError:
    from .models import *
    
    # Create aliases for improved model features
    if 'TenantAuditLog' not in globals():
        class TenantAuditLog:
            """Placeholder for TenantAuditLog if not available."""
            pass
'''
    
    with open(tenant_dir / 'models.py', 'w') as f:
        f.write(models_content)
    
    # Create services compatibility
    services_content = '''
"""
Services Compatibility Layer

This file provides backward compatibility for service imports.
"""

try:
    from .services_improved import *
except ImportError:
    # Create placeholder services
    class TenantService:
        pass
    
    class TenantSettingsService:
        pass
    
    class TenantBillingService:
        pass
    
    class TenantSecurityService:
        pass
'''
    
    with open(tenant_dir / 'services.py', 'w') as f:
        f.write(services_content)
    
    print("Created compatibility import files")

def fix_circular_imports():
    """Fix circular import issues by using lazy imports."""
    tenant_dir = Path(__file__).parent
    
    # Files with circular imports
    circular_files = [
        'signals_improved.py',
        'receivers.py',
        'middleware_improved.py'
    ]
    
    for filename in circular_files:
        file_path = tenant_dir / filename
        if not file_path.exists():
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace direct imports with lazy imports
        content = re.sub(
            r'from \.models_improved import',
            'from .imports_fix import get_tenant_models',
            content
        )
        
        content = re.sub(
            r'from \.services_improved import',
            'from .imports_fix import get_tenant_services', 
            content
        )
        
        # Add lazy import usage
        if 'get_tenant_models' in content:
            content = '''
from .imports_fix import get_tenant_models
from .imports_fix import get_tenant_services

# Get models with lazy loading
Tenant, TenantSettings, TenantBilling, TenantInvoice, TenantAuditLog = get_tenant_models()
TenantService, TenantSettingsService, TenantBillingService, TenantSecurityService = get_tenant_services()
''' + content
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Fixed circular imports in: {filename}")

def create_migration_fix():
    """Create a migration fix script."""
    tenant_dir = Path(__file__).parent
    
    migration_fix = '''
"""
Migration Fix Script

This script helps fix migration issues for the improved tenant models.
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

def run_migrations():
    """Run the tenant migrations."""
    from django.core.management import call_command
    
    try:
        print("Running tenant migrations...")
        call_command('migrate', 'tenants', verbosity=2)
        print("Migrations completed successfully!")
    except Exception as e:
        print(f"Migration error: {e}")
        print("You may need to run migrations manually:")
        print("python manage.py migrate tenants")

def check_model_status():
    """Check model status after migration."""
    try:
        from tenants.models import Tenant, TenantSettings, TenantBilling, TenantInvoice
        
        print(f"Tenant count: {Tenant.objects.count()}")
        print(f"TenantSettings count: {TenantSettings.objects.count()}")
        print(f"TenantBilling count: {TenantBilling.objects.count()}")
        print(f"TenantInvoice count: {TenantInvoice.objects.count()}")
        
        # Check if improved fields exist
        sample_tenant = Tenant.objects.first()
        if sample_tenant:
            print(f"Sample tenant fields: {[f.name for f in sample_tenant._meta.fields]}")
        
    except Exception as e:
        print(f"Model check error: {e}")

if __name__ == '__main__':
    run_migrations()
    check_model_status()
'''
    
    with open(tenant_dir / 'run_migrations.py', 'w') as f:
        f.write(migration_fix)
    
    print("Created migration fix script")

def main():
    """Main function to run all import fixes."""
    print("Starting tenant system import fixes...")
    
    # Update all imports
    update_all_imports()
    
    # Create compatibility imports
    create_compatibility_imports()
    
    # Fix circular imports
    fix_circular_imports()
    
    # Create migration fix
    create_migration_fix()
    
    print("Import fixes completed!")
    print("\nNext steps:")
    print("1. Run: python manage.py migrate tenants")
    print("2. Test the tenant system")
    print("3. Check for any remaining import errors")

if __name__ == '__main__':
    main()
