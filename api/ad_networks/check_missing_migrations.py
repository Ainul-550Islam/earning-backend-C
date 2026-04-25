"""
api/ad_networks/check_missing_migrations.py
Script to identify models that need migrations
"""

import os
import sys
import inspect
import importlib
from typing import List, Dict, Set

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_models_from_file() -> Set[str]:
    """Extract model names from models.py"""
    models = set()
    
    try:
        # Import the models module
        from api.ad_networks import models as ad_networks_models
        
        # Get all classes that inherit from models.Model
        for name, obj in inspect.getmembers(ad_networks_models):
            if inspect.isclass(obj) and hasattr(obj, '_meta'):
                if hasattr(obj._meta, 'app_label') and obj._meta.app_label == 'ad_networks':
                    models.add(name)
                    
    except ImportError as e:
        print(f"Error importing models: {e}")
        return set()
    
    return models

def get_models_from_migrations() -> Set[str]:
    """Extract model names from existing migrations"""
    migration_models = set()
    
    # Read migration files
    migration_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    
    for filename in os.listdir(migration_dir):
        if filename.startswith('000') and filename.endswith('.py') and filename != '__init__.py':
            filepath = os.path.join(migration_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Look for model creation patterns
                import re
                
                # Find migrations.CreateModel calls
                create_model_pattern = r'migrations\.CreateModel\(\s*name=[\'"]([^\'"]+)[\'"]'
                matches = re.findall(create_model_pattern, content)
                migration_models.update(matches)
                
                # Find field additions that might be for new models
                # This is a simplified check - in reality you'd need to parse the migration structure
                
            except Exception as e:
                print(f"Error reading migration file {filename}: {e}")
    
    return migration_models

def analyze_model_definitions():
    """Analyze model definitions to identify potential issues"""
    issues = []
    
    try:
        from api.ad_networks import models as ad_networks_models
        
        # Check each model
        for name, obj in inspect.getmembers(ad_networks_models):
            if inspect.isclass(obj) and hasattr(obj, '_meta'):
                if hasattr(obj._meta, 'app_label') and obj._meta.app_label == 'ad_networks':
                    
                    # Check if model has tenant_id field
                    fields = [f.name for f in obj._meta.get_fields()]
                    if 'tenant_id' not in fields and name not in ['OfferCategory']:  # OfferCategory might not need tenant_id
                        issues.append(f"Model {name} missing tenant_id field")
                    
                    # Check for proper abstract base classes
                    bases = [base.__name__ for base in obj.__bases__ if hasattr(base, '__name__')]
                    if 'TenantModel' not in bases and 'TenantModelMixin' not in bases and name not in ['OfferCategory']:
                        issues.append(f"Model {name} not inheriting from TenantModel")
                        
    except ImportError as e:
        print(f"Error importing models for analysis: {e}")
        return []
    
    return issues

def main():
    """Main function to check for missing migrations"""
    print("=== Ad Networks Migration Check ===\n")
    
    # Get models from models.py
    print("1. Analyzing models.py...")
    models_in_code = get_models_from_file()
    print(f"Found {len(models_in_code)} models in models.py:")
    for model in sorted(models_in_code):
        print(f"  - {model}")
    
    print()
    
    # Get models from migrations
    print("2. Analyzing existing migrations...")
    models_in_migrations = get_models_from_migrations()
    print(f"Found {len(models_in_migrations)} models in migrations:")
    for model in sorted(models_in_migrations):
        print(f"  - {model}")
    
    print()
    
    # Find missing models
    print("3. Checking for missing migrations...")
    missing_models = models_in_code - models_in_migrations
    
    if missing_models:
        print(f"Models needing migrations ({len(missing_models)}):")
        for model in sorted(missing_models):
            print(f"  - {model}")
    else:
        print("All models have migrations!")
    
    print()
    
    # Analyze model definitions
    print("4. Analyzing model definitions...")
    issues = analyze_model_definitions()
    
    if issues:
        print(f"Model definition issues ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("All model definitions look good!")
    
    print()
    
    # Summary
    print("=== Summary ===")
    print(f"Total models in code: {len(models_in_code)}")
    print(f"Total models in migrations: {len(models_in_migrations)}")
    print(f"Models needing migrations: {len(missing_models)}")
    print(f"Model definition issues: {len(issues)}")
    
    if missing_models or issues:
        print("\nRecommendation: Run 'python manage.py makemigrations ad_networks'")
    else:
        print("\nAll migrations are up to date!")

if __name__ == '__main__':
    main()
