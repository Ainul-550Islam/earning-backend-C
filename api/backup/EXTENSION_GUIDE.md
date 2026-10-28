# 📚 Backup System Extension Guide

> **"এক কাজের জন্য একটাই মালিক"** — এই guide অনুসরণ করলে **core backup code কখনো touch করতে হবে না।**

## 🎯 উদ্দেশ্য

এই guide টি আপনাকে নতুন features যোগ করার জন্য step-by-step instructions দেবে, যেন core backup system কে modify করতে না হয়। এটি একটি **plug-and-play architecture** যেখানে আপনি নিজের features গুলি যোগ করতে পারবেন existing system এর সাথে conflict ছাড়াই।

---

## 🏗️ Architecture Overview

```
api/backup/
├── 📁 EXTENSIONS/           # 👈 এখানে আপনার সব features রাখবেন
│   ├── 📁 custom_storage/   # Custom storage providers
│   ├── 📁 custom_validators/ # Custom validation rules
│   ├── 📁 custom_services/  # Custom business logic
│   └── 📁 custom_hooks/     # Custom event handlers
├── 📁 INTEGRATION_SYSTEM/   # 🔧 Core integration framework
├── 📁 services/            # 🚫 Core services (touch করবেন না)
├── 📁 models.py            # 🚫 Core models (touch করবেন না)
└── 📁 management/          # 🚫 Core commands (touch করবেন না)
```

---

## 🚀 Quick Start: 5 Minutes to Add Your First Feature

### Step 1: Create Your Extension Directory

```bash
mkdir api/backup/EXTENSIONS/my_feature
cd api/backup/EXTENSIONS/my_feature
```

### Step 2: Create Extension Manifest

```python
# __init__.py
EXTENSION_INFO = {
    "name": "my_feature",
    "version": "1.0.0",
    "description": "My custom backup feature",
    "author": "Your Name",
    "dependencies": [],
    "hooks": ["backup_pre_create", "backup_post_create"],
    "permissions": ["can_use_my_feature"]
}
```

### Step 3: Implement Your Feature

```python
# feature.py
from api.backup.INTEGRATION_SYSTEM.integ_signals import backup_pre_create
from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry

@backup_pre_create.connect
def my_custom_backup_handler(sender, **kwargs):
    """Custom backup logic"""
    backup_config = kwargs.get('backup_config')
    # Your custom logic here
    print(f"Processing backup: {backup_config.name}")

def register_extension():
    """Register this extension"""
    registry = get_integration_registry()
    registry.register_extension('my_feature', {
        'handler': my_custom_backup_handler,
        'config_schema': {
            'custom_setting': {'type': 'string', 'required': False}
        }
    })
```

### Step 4: Enable Your Extension

```python
# api/backup/settings_extensions.py
EXTENSIONS_ENABLED = [
    'my_feature',
    # ... other extensions
]
```

---

## 🔧 Extension Types & Examples

### 1. 🗄️ Custom Storage Providers

**Directory:** `EXTENSIONS/custom_storage/`

**Example: Google Drive Storage**

```python
# google_drive_storage.py
from api.backup.services.BaseBackup import BaseBackupService
from api.backup.INTEGRATION_SYSTEM.integ_adapter import BaseIntegrationAdapter

class GoogleDriveStorageAdapter(BaseIntegrationAdapter):
    """Google Drive storage adapter"""
    
    def __init__(self, config):
        super().__init__(config)
        self.drive_service = self._init_drive_service()
    
    def _init_drive_service(self):
        """Initialize Google Drive service"""
        # Google Drive API initialization
        pass
    
    async def save_backup(self, backup_data, metadata):
        """Save backup to Google Drive"""
        # Upload to Google Drive
        file_id = await self.drive_service.upload_file(
            backup_data, metadata['name']
        )
        return {'file_id': file_id, 'provider': 'google_drive'}
    
    async def list_backups(self, filters=None):
        """List backups from Google Drive"""
        # List files from Google Drive
        pass
    
    async def delete_backup(self, backup_id):
        """Delete backup from Google Drive"""
        # Delete file from Google Drive
        pass

# Register the adapter
def register_google_drive_storage():
    from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
    registry = get_integration_registry()
    registry.register_adapter('google_drive', GoogleDriveStorageAdapter)
```

### 2. ✅ Custom Validation Rules

**Directory:** `EXTENSIONS/custom_validators/`

**Example: HIPAA Compliance Validator**

```python
# hipaa_validator.py
from api.backup.INTEGRATION_SYSTEM.data_validator import BaseValidator
from api.backup.INTEGRATION_SYSTEM.integ_exceptions import ValidationException

class HIPAAComplianceValidator(BaseValidator):
    """HIPAA compliance validator"""
    
    def __init__(self):
        super().__init__()
        self.sensitive_fields = [
            'ssn', 'medical_record', 'patient_name', 'diagnosis'
        ]
    
    async def validate_data(self, data, context=None):
        """Validate HIPAA compliance"""
        errors = []
        
        # Check for unencrypted sensitive data
        for field in self.sensitive_fields:
            if field in data and not self._is_encrypted(data[field]):
                errors.append(f"Sensitive field '{field}' is not encrypted")
        
        # Check for audit trail
        if not context or 'audit_id' not in context:
            errors.append("Missing audit trail for HIPAA compliance")
        
        if errors:
            raise ValidationException("HIPAA compliance failed", errors)
        
        return True, "HIPAA compliance validated"
    
    def _is_encrypted(self, value):
        """Check if value is encrypted"""
        # Encryption detection logic
        return isinstance(value, str) and value.startswith('encrypted:')

# Register validator
def register_hipaa_validator():
    from api.backup.INTEGRATION_SYSTEM.data_validator import get_data_validator
    validator = get_data_validator()
    validator.register_validator('hipaa_compliance', HIPAAComplianceValidator())
```

### 3. 🎣 Custom Event Hooks

**Directory:** `EXTENSIONS/custom_hooks/`

**Example: Slack Notification Hook**

```python
# slack_notifier.py
from api.backup.INTEGRATION_SYSTEM.integ_signals import (
    backup_post_create, backup_failed, restore_completed
)
from api.backup.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_logger
import requests
import json

class SlackNotificationHook:
    """Slack notification hook"""
    
    def __init__(self, webhook_url, channel="#backup-alerts"):
        self.webhook_url = webhook_url
        self.channel = channel
    
    def send_slack_message(self, message, color="good"):
        """Send message to Slack"""
        payload = {
            "channel": self.channel,
            "attachments": [{
                "color": color,
                "text": message,
                "title": "Backup System Alert"
            }]
        }
        
        try:
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    
    def on_backup_success(self, sender, **kwargs):
        """Handle backup success"""
        backup = kwargs.get('backup')
        message = f"✅ Backup successful: {backup.name} ({backup.backup_id})"
        self.send_slack_message(message, "good")
    
    def on_backup_failure(self, sender, **kwargs):
        """Handle backup failure"""
        backup = kwargs.get('backup')
        error = kwargs.get('error', 'Unknown error')
        message = f"❌ Backup failed: {backup.name} - {error}"
        self.send_slack_message(message, "danger")
    
    def on_restore_complete(self, sender, **kwargs):
        """Handle restore completion"""
        restoration = kwargs.get('restoration')
        message = f"🔄 Restore completed: {restoration.backup_id}"
        self.send_slack_message(message, "warning")

# Register hooks
def register_slack_hooks():
    slack_hook = SlackNotificationHook(
        webhook_url="YOUR_SLACK_WEBHOOK_URL"
    )
    
    backup_post_create.connect(slack_hook.on_backup_success)
    backup_failed.connect(slack_hook.on_backup_failure)
    restore_completed.connect(slack_hook.on_restore_complete)
```

### 4. 📊 Custom Analytics & Reporting

**Directory:** `EXTENSIONS/custom_analytics/`

**Example: Cost Analysis Reporter**

```python
# cost_analyzer.py
from api.backup.INTEGRATION_SYSTEM.integ_signals import backup_post_create
from api.backup.models import Backup, BackupStorageLocation
from django.db.models import Sum, Count
from datetime import datetime, timedelta
import json

class CostAnalysisReporter:
    """Backup cost analysis reporter"""
    
    def __init__(self):
        self.storage_costs = {
            's3': 0.023,  # $0.023 per GB
            'azure': 0.018,
            'gcp': 0.020,
            'local': 0.001
        }
    
    def calculate_monthly_cost(self, year, month):
        """Calculate monthly backup costs"""
        from django.db.models import F
        
        # Get all backups for the month
        backups = Backup.objects.filter(
            created_at__year=year,
            created_at__month=month
        ).annotate(
            storage_type=F('storage_location__storage_type')
        )
        
        total_cost = 0
        cost_breakdown = {}
        
        for backup in backups:
            size_gb = backup.file_size / (1024 * 1024 * 1024)  # Convert to GB
            storage_type = backup.storage_type or 'local'
            cost_per_gb = self.storage_costs.get(storage_type, 0.01)
            backup_cost = size_gb * cost_per_gb
            
            total_cost += backup_cost
            
            if storage_type not in cost_breakdown:
                cost_breakdown[storage_type] = 0
            cost_breakdown[storage_type] += backup_cost
        
        return {
            'total_cost': total_cost,
            'breakdown': cost_breakdown,
            'backup_count': backups.count(),
            'total_size_gb': sum(b.file_size for b in backups) / (1024 * 1024 * 1024)
        }
    
    def generate_cost_report(self, format='json'):
        """Generate cost report"""
        current_date = datetime.now()
        
        # Last 6 months
        reports = []
        for i in range(6):
            month_date = current_date - timedelta(days=30 * i)
            cost_data = self.calculate_monthly_cost(
                month_date.year, month_date.month
            )
            cost_data['month'] = month_date.strftime('%Y-%m')
            reports.append(cost_data)
        
        if format == 'json':
            return json.dumps(reports, indent=2)
        elif format == 'csv':
            # Generate CSV format
            pass
        
        return reports

# Register analytics
def register_cost_analytics():
    from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
    registry = get_integration_registry()
    registry.register_analytics('cost_analysis', CostAnalysisReporter())
```

---

## 🔌 Extension Registration System

### Automatic Registration

```python
# api/backup/extension_loader.py
import importlib
import os
from django.conf import settings

class ExtensionLoader:
    """Load and register all extensions"""
    
    def __init__(self):
        self.extensions_dir = os.path.join(
            os.path.dirname(__file__), 'EXTENSIONS'
        )
    
    def load_all_extensions(self):
        """Load all enabled extensions"""
        enabled_extensions = getattr(settings, 'EXTENSIONS_ENABLED', [])
        
        for ext_name in enabled_extensions:
            try:
                self.load_extension(ext_name)
                print(f"✅ Loaded extension: {ext_name}")
            except Exception as e:
                print(f"❌ Failed to load extension {ext_name}: {e}")
    
    def load_extension(self, ext_name):
        """Load a specific extension"""
        ext_path = os.path.join(self.extensions_dir, ext_name)
        
        if not os.path.exists(ext_path):
            raise FileNotFoundError(f"Extension directory not found: {ext_path}")
        
        # Import extension module
        module_path = f"api.backup.EXTENSIONS.{ext_name}.feature"
        module = importlib.import_module(module_path)
        
        # Register extension if it has register function
        if hasattr(module, 'register_extension'):
            module.register_extension()

# Auto-load extensions on Django startup
def load_extensions():
    loader = ExtensionLoader()
    loader.load_all_extensions()
```

### Extension Configuration

```python
# settings.py
EXTENSIONS_CONFIG = {
    'my_feature': {
        'enabled': True,
        'settings': {
            'custom_param': 'value',
            'api_endpoint': 'https://api.example.com'
        }
    },
    'slack_notifications': {
        'enabled': True,
        'settings': {
            'webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
            'channel': '#backup-alerts'
        }
    }
}

EXTENSIONS_ENABLED = [
    'my_feature',
    'slack_notifications',
    'google_drive_storage',
    'hipaa_validator'
]
```

---

## 🛡️ Best Practices & Guidelines

### ✅ DO's

1. **Use Extension Directories Only**
   - সবসময় `EXTENSIONS/` directory তে কাজ করুন
   - Core files কখনো modify করবেন না

2. **Follow Naming Conventions**
   ```python
   # ✅ Good
   EXTENSIONS/my_feature/
   ├── __init__.py
   ├── feature.py
   ├── models.py  # Extension-specific models only
   └── tests.py
   ```

3. **Use Signals for Integration**
   ```python
   # ✅ Use signals instead of direct modification
   from api.backup.INTEGRATION_SYSTEM.integ_signals import backup_pre_create
   
   @backup_pre_create.connect
   def my_handler(sender, **kwargs):
       # Your logic here
       pass
   ```

4. **Register Extensions Properly**
   ```python
   # ✅ Always provide registration function
   def register_my_extension():
       registry = get_integration_registry()
       registry.register_extension('my_feature', handler)
   ```

### ❌ DON'Ts

1. **Don't Modify Core Files**
   ```python
   # ❌ NEVER do this
   # from api.backup.models import Backup
   # Backup.add_to_class('custom_field', models.CharField(...))
   ```

2. **Don't Access Private Methods**
   ```python
   # ❌ Avoid private methods
   # backup_service._private_method()
   ```

3. **Don't Create Circular Dependencies**
   ```python
   # ❌ Avoid circular imports
   # from api.backup.services import BackupService
   # from api.backup.EXTENSIONS.my_feature import MyFeature
   ```

---

## 🧪 Testing Your Extensions

### Extension Test Structure

```python
# EXTENSIONS/my_feature/tests.py
import unittest
from django.test import TestCase
from api.backup.EXTENSIONS.my_feature.feature import my_custom_handler

class MyFeatureTest(TestCase):
    """Test cases for my feature"""
    
    def setUp(self):
        """Setup test data"""
        self.test_config = {
            'name': 'test_backup',
            'storage_type': 'local'
        }
    
    def test_custom_handler(self):
        """Test custom backup handler"""
        # Test your feature logic
        result = my_custom_handler(None, backup_config=self.test_config)
        self.assertIsNotNone(result)
    
    def test_extension_registration(self):
        """Test extension registration"""
        from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
        registry = get_integration_registry()
        
        # Check if extension is registered
        self.assertIn('my_feature', registry.extensions)
```

### Running Extension Tests

```bash
# Run specific extension tests
python manage.py test api.backup.EXTENSIONS.my_feature

# Run all extension tests
python manage.py test api.backup.EXTENSIONS --pattern="tests.py"
```

---

## 📦 Extension Templates

### Storage Provider Template

```python
# EXTENSIONS/template_storage/storage_provider.py
from api.backup.INTEGRATION_SYSTEM.integ_adapter import BaseIntegrationAdapter

class TemplateStorageAdapter(BaseIntegrationAdapter):
    """Template for custom storage providers"""
    
    def __init__(self, config):
        super().__init__(config)
        # Initialize your storage client
    
    async def save_backup(self, backup_data, metadata):
        """Save backup to your storage"""
        # Implement save logic
        pass
    
    async def list_backups(self, filters=None):
        """List backups from your storage"""
        # Implement list logic
        pass
    
    async def delete_backup(self, backup_id):
        """Delete backup from your storage"""
        # Implement delete logic
        pass
    
    async def download_backup(self, backup_id):
        """Download backup from your storage"""
        # Implement download logic
        pass

def register_template_storage():
    """Register this storage provider"""
    from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
    registry = get_integration_registry()
    registry.register_adapter('template_storage', TemplateStorageAdapter)
```

### Validator Template

```python
# EXTENSIONS/template_validator/validator.py
from api.backup.INTEGRATION_SYSTEM.data_validator import BaseValidator
from api.backup.INTEGRATION_SYSTEM.integ_exceptions import ValidationException

class TemplateValidator(BaseValidator):
    """Template for custom validators"""
    
    async def validate_data(self, data, context=None):
        """Validate data according to your rules"""
        errors = []
        
        # Implement your validation logic
        # if not valid:
        #     errors.append("Validation error message")
        
        if errors:
            raise ValidationException("Validation failed", errors)
        
        return True, "Validation passed"

def register_template_validator():
    """Register this validator"""
    from api.backup.INTEGRATION_SYSTEM.data_validator import get_data_validator
    validator = get_data_validator()
    validator.register_validator('template_validator', TemplateValidator())
```

---

## 🔍 Debugging Extensions

### Extension Debug Mode

```python
# settings.py
EXTENSIONS_DEBUG = True  # Enable extension debugging
```

### Logging Extension Events

```python
# In your extension
import logging

logger = logging.getLogger('backup.extensions.my_feature')

def my_handler(sender, **kwargs):
    logger.info(f"My feature triggered by: {sender}")
    logger.debug(f"Handler kwargs: {kwargs}")
    
    try:
        # Your logic here
        logger.info("My feature executed successfully")
    except Exception as e:
        logger.error(f"My feature failed: {e}", exc_info=True)
        raise
```

### Extension Status Check

```python
# management command: check_extensions.py
from django.core.management.base import BaseCommand
from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry

class Command(BaseCommand):
    help = 'Check status of all extensions'
    
    def handle(self, *args, **options):
        registry = get_integration_registry()
        
        self.stdout.write("Extension Status:")
        for name, info in registry.extensions.items():
            status = "✅ Active" if info.get('active') else "❌ Inactive"
            self.stdout.write(f"  {name}: {status}")
```

---

## 📚 Reference Documentation

### Available Signals

```python
# Core backup signals
from api.backup.INTEGRATION_SYSTEM.integ_signals import (
    backup_pre_create,           # Before backup creation
    backup_post_create,          # After backup creation
    backup_failed,              # When backup fails
    backup_pre_restore,          # Before restore
    backup_post_restore,         # After restore
    backup_pre_verify,           # Before verification
    backup_post_verify,          # After verification
    storage_pre_upload,          # Before file upload
    storage_post_upload,         # After file upload
    system_health_check,         # System health checks
    performance_alert,           # Performance alerts
    security_event,             # Security events
)
```

### Registry Methods

```python
from api.backup.INTEGRATION_SYSTEM.integ_registry import get_integration_registry

registry = get_integration_registry()

# Register components
registry.register_adapter('name', adapter_class)
registry.register_validator('name', validator_class)
registry.register_extension('name', extension_config)
registry.register_analytics('name', analytics_class)

# Get components
adapter = registry.get_adapter('storage_type')
validator = registry.get_validator('validator_name')
extension = registry.get_extension('extension_name')
```

### Configuration Access

```python
from django.conf import settings

# Get extension config
extension_config = getattr(settings, 'EXTENSIONS_CONFIG', {})
my_config = extension_config.get('my_feature', {})

# Get extension settings
my_settings = my_config.get('settings', {})
```

---

## 🚨 Troubleshooting

### Common Issues & Solutions

1. **Extension Not Loading**
   ```python
   # Check if extension is in EXTENSIONS_ENABLED
   # Verify __init__.py exists
   # Check for syntax errors in feature.py
   ```

2. **Signal Not Triggering**
   ```python
   # Ensure signal is imported correctly
   # Check if handler is registered
   # Verify sender matches expected sender
   ```

3. **Import Errors**
   ```python
   # Use absolute imports
   from api.backup.INTEGRATION_SYSTEM.integ_signals import backup_pre_create
   # Not relative imports
   # from ..integ_signals import backup_pre_create
   ```

4. **Permission Issues**
   ```python
   # Add permissions to EXTENSIONS_CONFIG
   EXTENSIONS_CONFIG = {
       'my_feature': {
           'permissions': ['can_use_my_feature']
       }
   }
   ```

---

## 🎉 Success Stories

### Example 1: Custom Email Notifications

```python
# EXTENSIONS/email_notifier/feature.py
from api.backup.INTEGRATION_SYSTEM.integ_signals import backup_post_create
from django.core.mail import send_mail

@backup_post_create.connect
def send_backup_email(sender, **kwargs):
    backup = kwargs.get('backup')
    send_mail(
        'Backup Completed',
        f'Backup {backup.name} completed successfully',
        'admin@example.com',
        ['team@example.com'],
        fail_silently=False,
    )
```

### Example 2: Custom Storage Compression

```python
# EXTENSIONS/compression_storage/feature.py
from api.backup.INTEGRATION_SYSTEM.integ_adapter import BaseIntegrationAdapter
import gzip

class CompressedStorageAdapter(BaseIntegrationAdapter):
    async def save_backup(self, backup_data, metadata):
        # Compress before saving
        compressed_data = gzip.compress(backup_data)
        return await super().save_backup(compressed_data, metadata)
```

---

## 📞 Support & Community

### Getting Help

1. **Check Extension Logs**
   ```bash
   tail -f logs/backup_extensions.log
   ```

2. **Test Extension Isolation**
   ```python
   # Disable all extensions except yours
   EXTENSIONS_ENABLED = ['my_feature_only']
   ```

3. **Validate Extension Structure**
   ```bash
   python manage.py validate_extensions
   ```

### Contributing Extensions

1. Follow the template structure
2. Include comprehensive tests
3. Document your extension
4. Submit for review

---

## 🏁 Conclusion

এই EXTENSION_GUIDE.md অনুসরণ করে আপনি যেকোনো custom feature যোগ করতে পারবেন core backup system modify না করেই। এটি একটি **future-proof architecture** যা maintainable, scalable, এবং conflict-free।

**Remember:** "এক কাজের জন্য একটাই মালিক" - আপনার feature আপনার directory তে, core system core directory তে।

---

*Last Updated: April 2026*  
*Version: 1.0.0*  
*Compatible with: Backup System v2.0+*
