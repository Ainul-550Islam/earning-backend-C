"""
Migration utilities for alerts app - Database migration helpers
"""
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.management import call_command
from django.db import connection
import logging
import json
import os
import time

logger = logging.getLogger(__name__)


class MigrationHelper:
    """Helper class for database migrations"""
    
    def __init__(self, app_name: str = 'alerts'):
        self.app_name = app_name
        self.migrations_dir = os.path.join(settings.BASE_DIR, app_name, 'migrations')
        
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migrations"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT name FROM django_migrations 
                    WHERE app = %s 
                    ORDER BY applied
                """, [self.app_name])
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting applied migrations: {e}")
            return []
    
    def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations"""
        try:
            migration_files = []
            
            if os.path.exists(self.migrations_dir):
                for filename in os.listdir(self.migrations_dir):
                    if filename.endswith('.py') and filename != '__init__.py':
                        migration_name = filename[:-3]  # Remove .py extension
                        migration_files.append(migration_name)
            
            applied_migrations = self.get_applied_migrations()
            pending_migrations = [
                f for f in migration_files 
                if f not in applied_migrations
            ]
            
            return sorted(pending_migrations)
        except Exception as e:
            logger.error(f"Error getting pending migrations: {e}")
            return []
    
    def run_migrations(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run pending migrations"""
        try:
            pending_migrations = self.get_pending_migrations()
            
            if not pending_migrations:
                return {
                    'success': True,
                    'message': 'No pending migrations',
                    'migrations_run': []
                }
            
            if dry_run:
                return {
                    'success': True,
                    'message': f'Dry run: {len(pending_migrations)} pending migrations',
                    'pending_migrations': pending_migrations,
                    'migrations_run': []
                }
            
            migrations_run = []
            
            for migration in pending_migrations:
                try:
                    # Run migration command
                    call_command('migrate', self.app_name, migration, verbosity=0)
                    migrations_run.append(migration)
                    logger.info(f"Applied migration: {migration}")
                    
                    time.sleep(0.1)  # Small delay between migrations
                    
                except Exception as e:
                    logger.error(f"Error applying migration {migration}: {e}")
                    return {
                        'success': False,
                        'error': 'Operation failed',
                        'migrations_run': migrations_run
                    }
            
            return {
                'success': True,
                'message': f'Successfully applied {len(migrations_run)} migrations',
                'migrations_run': migrations_run
            }
            
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return {
                'success': False,
                'error': 'Operation failed',
                'migrations_run': []
            }
    
    def rollback_migration(self, migration_name: str) -> Dict[str, Any]:
        """Rollback a specific migration"""
        try:
            call_command('migrate', self.app_name, migration_name, '--fake', verbosity=0)
            logger.info(f"Rolled back migration: {migration_name}")
            
            return {
                'success': True,
                'message': f'Successfully rolled back migration: {migration_name}'
            }
            
        except Exception as e:
            logger.error(f"Error rolling back migration {migration_name}: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status"""
        try:
            applied_migrations = self.get_applied_migrations()
            pending_migrations = self.get_pending_migrations()
            
            return {
                'app_name': self.app_name,
                'total_migrations': len(applied_migrations) + len(pending_migrations),
                'applied_migrations': applied_migrations,
                'pending_migrations': pending_migrations,
                'migration_count': len(applied_migrations),
                'pending_count': len(pending_migrations),
                'last_applied': applied_migrations[-1] if applied_migrations else None,
                'next_pending': pending_migrations[0] if pending_migrations else None,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': timezone.now().isoformat()
            }


class MigrationValidator:
    """Validator for migration files"""
    
    def __init__(self, migrations_dir: str):
        self.migrations_dir = migrations_dir
        
    def validate_migration_file(self, migration_file: str) -> Dict[str, Any]:
        """Validate a single migration file"""
        try:
            file_path = os.path.join(self.migrations_dir, migration_file)
            
            if not os.path.exists(file_path):
                return {
                    'valid': False,
                    'error': f'File {migration_file} not found'
                }
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Basic validation checks
            issues = []
            
            # Check for required imports
            if 'from django.db import migrations' not in content:
                issues.append('Missing required import: from django.db import migrations')
            
            if 'class Migration' not in content:
                issues.append('Missing Migration class')
            
            if 'dependencies = []' not in content:
                issues.append('Missing dependencies list')
            
            if 'operations = []' not in content:
                issues.append('Missing operations list')
            
            # Check for common issues
            if 'migrations.CreateModel' in content and 'name=' not in content:
                issues.append('CreateModel operation missing name parameter')
            
            if 'migrations.AddField' in content and 'model_name=' not in content:
                issues.append('AddField operation missing model_name parameter')
            
            # Check for naming conventions
            if not migration_file.startswith('0') or len(migration_file) != 4:
                issues.append('Migration file should follow naming convention: 000X_name.py')
            
            return {
                'valid': len(issues) == 0,
                'file': migration_file,
                'issues': issues,
                'warnings': []
            }
            
        except Exception as e:
            logger.error(f"Error validating migration file {migration_file}: {e}")
            return {
                'valid': False,
                'error': 'Operation failed'
            }
    
    def validate_all_migrations(self) -> Dict[str, Any]:
        """Validate all migration files"""
        try:
            if not os.path.exists(self.migrations_dir):
                return {
                    'valid': False,
                    'error': f'Migrations directory {self.migrations_dir} not found'
                }
            
            migration_files = [
                f for f in os.listdir(self.migrations_dir)
                if f.endswith('.py') and f != '__init__.py'
            ]
            
            validation_results = []
            total_issues = 0
            
            for migration_file in sorted(migration_files):
                result = self.validate_migration_file(migration_file)
                validation_results.append(result)
                total_issues += len(result.get('issues', []))
            
            return {
                'valid': total_issues == 0,
                'total_files': len(migration_files),
                'files_with_issues': len([r for r in validation_results if not r['valid']]),
                'total_issues': total_issues,
                'results': validation_results
            }
            
        except Exception as e:
            logger.error(f"Error validating migrations: {e}")
            return {
                'valid': False,
                'error': 'Operation failed'
            }


class MigrationGenerator:
    """Generator for new migration files"""
    
    def __init__(self, app_name: str = 'alerts'):
        self.app_name = app_name
        self.migrations_dir = os.path.join(settings.BASE_DIR, app_name, 'migrations')
        
    def generate_migration_template(self, migration_name: str, description: str) -> str:
        """Generate migration template"""
        template = f'''"""
Generated by Django 4.2 on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

{description}
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # Add dependencies here
    ]

    operations = [
        # Add operations here
    ]
'''
        return template
    
    def create_model_migration(self, model_name: str, fields: List[Dict[str, Any]], 
                           table_name: str = None, dependencies: List[str] = None) -> str:
        """Create a migration for adding a model"""
        if table_name is None:
            table_name = f'alerts_{model_name.lower()}'
        
        if dependencies is None:
            dependencies = []
        
        # Generate field definitions
        field_definitions = []
        for field in fields:
            field_def = f"                ('{field['name']}', models.{field['type']}("
            
            # Add field parameters
            if 'max_length' in field:
                field_def += f"max_length={field['max_length']}"
            
            if 'primary_key' in field and field['primary_key']:
                field_def += ", primary_key=True"
            
            if 'auto_created' in field and field['auto_created']:
                field_def += ", auto_created=True"
            
            if 'serialize' in field and field['serialize']:
                field_def += ", serialize=False"
            
            if 'default' in field:
                field_def += f", default={field['default']}"
            
            if 'null' in field and field['null']:
                field_def += ", null=True"
            
            if 'blank' in field and field['blank']:
                field_def += ", blank=True"
            
            if 'related_name' in field:
                field_def += f", related_name='{field['related_name']}'"
            
            if 'on_delete' in field:
                field_def += f", on_delete={field['on_delete']}"
            
            field_def += ")),"
            field_definitions.append(field_def)
        
        migration_content = f'''"""
Generated by Django 4.2 on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

Create {model_name} model
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
{self._format_dependencies(dependencies)}
    ]

    operations = [
        migrations.CreateModel(
            name='{model_name}',
            fields=[
{chr(10).join(field_definitions)}
            ],
            options={{
                'verbose_name': '{model_name}',
                'verbose_name_plural': '{model_name}s',
                'db_table': '{table_name}',
                'indexes': [
                    # Add indexes here
                ],
            }},
        ),
    ]
'''
        return migration_content
    
    def create_field_migration(self, model_name: str, field_name: str, 
                          field_type: str, field_params: Dict[str, Any] = None) -> str:
        """Create a migration for adding a field to an existing model"""
        if field_params is None:
            field_params = {}
        
        # Build field definition
        field_def = f"                ('{field_name}', models.{field_type}("
        
        # Add field parameters
        if 'max_length' in field_params:
            field_def += f"max_length={field_params['max_length']}"
        
        if 'default' in field_params:
            field_def += f", default={field_params['default']}"
        
        if 'null' in field_params:
            field_def += f", null={field_params['null']}"
        
        if 'blank' in field_params:
            field_def += f", blank={field_params['blank']}"
        
        field_def += ")),"
        
        migration_content = f'''"""
Generated by Django 4.2 on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

Add {field_name} field to {model_name}
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0006_add_scheduler_system'),
    ]

    operations = [
        migrations.AddField(
            model_name='{model_name}',
            name='{field_name}',
            field=models.{field_type}({field_def[2:]}),
        ),
    ]
'''
        return migration_content
    
    def _format_dependencies(self, dependencies: List[str]) -> str:
        """Format dependencies list"""
        if not dependencies:
            return "        # Add dependencies here"
        
        formatted_deps = []
        for dep in dependencies:
            formatted_deps.append(f"        ('{dep}',)")
        
        return ',\n'.join(formatted_deps)
    
    def save_migration_file(self, migration_name: str, content: str) -> str:
        """Save migration to file"""
        try:
            # Find next migration number
            existing_migrations = [
                f for f in os.listdir(self.migrations_dir)
                if f.endswith('.py') and f != '__init__.py'
            ]
            
            if existing_migrations:
                # Get the highest number
                numbers = []
                for f in existing_migrations:
                    if f.startswith('0') and len(f) >= 5:
                        try:
                            num = int(f[:4])
                            numbers.append(num)
                        except ValueError:
                            pass
                
                next_number = max(numbers) + 1 if numbers else 1
            else:
                next_number = 1
            
            # Format migration filename
            migration_filename = f"{next_number:04d}_{migration_name}.py"
            migration_path = os.path.join(self.migrations_dir, migration_filename)
            
            # Write migration file
            with open(migration_path, 'w') as f:
                f.write(content)
            
            logger.info(f"Created migration file: {migration_filename}")
            return migration_filename
            
        except Exception as e:
            logger.error(f"Error saving migration file: {e}")
            return None


# Global migration helper
migration_helper = None


def get_migration_helper() -> Optional[MigrationHelper]:
    """Get the global migration helper"""
    return migration_helper


def initialize_migration_helper():
    """Initialize migration helper"""
    global migration_helper
    
    try:
        migration_helper = MigrationHelper()
        logger.info("Migration helper initialized")
    except Exception as e:
        logger.error(f"Error initializing migration helper: {e}")


# Initialize on module import
try:
    initialize_migration_helper()
except Exception as e:
    logger.error(f"Error initializing migration helper: {e}")
