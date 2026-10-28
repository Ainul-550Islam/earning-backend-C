# গ্যামিফিকেশন সিস্টেম এক্সটেনশন গাইড

> **"এক কাজের জন্য একটাই মালিক"** — এই guide অনুসরণ করলে **core api/gamification code কখনো touch করতে হবে না।**

## 📋 সূচিপত্র

1. [ভূমিকা](#ভূমিকা)
2. [আর্কিটেকচার ওভারভিউ](#আর্কিটেকচার-ওভারভিউ)
3. [নতুন ফিচার যোগ করার পদ্ধতি](#নতুন-ফিচার-যোগ-করার-পদ্ধতি)
4. [এক্সটেনশন প্যাটার্নস](#এক্সটেনশন-প্যাটার্নস)
5. [বেস্ট প্র্যাকটিস](#বেস্ট-প্র্যাকটিস)
6. [উদাহরণ](#উদাহরণ)
7. [টেস্টিং](#টেস্টিং)
8. [ডিপ্লয়মেন্ট](#ডিপ্লয়মেন্ট)

---

## ভূমিকা

এই গাইডটি গ্যামিফিকেশন সিস্টেমে নতুন ফিচার যোগ করার জন্য একটি সম্পূর্ণ নির্দেশিকা। এখানে বর্ণিত পদ্ধতি অনুসরণ করলে core API code পরিবর্তন করতে হবে না, যা সিস্টেমের স্থিতিশীলতা এবং maintainability নিশ্চিত করে।

### 🎯 মূল লক্ষ্য

- **Zero Core Modification**: Core API কখনোই পরিবর্তন করা যাবে না
- **Plug-and-Play Extension**: নতুন ফিচার সহজেই যোগ করা যাবে
- **Backward Compatibility**: বিদ্যমান ফিচার কোনো প্রভাব পড়বে না
- **Clean Separation**: Core এবং extension এর মধ্যে clear separation

---

## আর্কিটেকচার ওভারভিউ

```
api/gamification/
├── core/                          # Core API (পরিবর্তন নিষিদ্ধ)
│   ├── models.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── ...
├── extensions/                    # Extension Directory (নতুন ফিচার)
│   ├── loyalty_points/
│   ├── achievements_plus/
│   ├── tournaments/
│   └── custom_rewards/
├── plugins/                       # Plugin System
│   ├── registry.py
│   ├── loader.py
│   └── hooks.py
└── INTEGRATION_SYSTEM/           # Integration Layer
    ├── plugin_manager.py
    └── extension_bridge.py
```

### 🏗️ Core Components

1. **Core API**: মূল gamification সিস্টেম (পরিবর্তন নিষিদ্ধ)
2. **Extension Framework**: নতুন ফিচার যোগ করার infrastructure
3. **Plugin Manager**: Extension loading এবং management
4. **Integration Bridge**: Core এবং extension এর মধ্যে communication

---

## নতুন ফিচার যোগ করার পদ্ধতি

### ধাপ ১: Extension Structure তৈরি

```bash
# নতুন extension directory তৈরি
mkdir -p api/gamification/extensions/your_feature_name

# Extension structure
api/gamification/extensions/your_feature_name/
├── __init__.py
├── models.py          # Extension-specific models
├── services.py        # Extension business logic
├── views.py           # Extension views
├── serializers.py     # Extension serializers
├── admin.py           # Extension admin
├── urls.py            # Extension URLs
├── migrations/        # Extension migrations
├── tests/             # Extension tests
├── static/            # Extension static files
├── templates/         # Extension templates
├── config.py          # Extension configuration
└── plugin.py          # Plugin registration
```

### ধাপ ২: Plugin Registration

```python
# api/gamification/extensions/your_feature_name/plugin.py

from api.gamification.plugins.registry import PluginRegistry
from api.gamification.plugins.base import BasePlugin

class YourFeaturePlugin(BasePlugin):
    """
    Your Feature Plugin Implementation
    """
    
    name = "your_feature_name"
    version = "1.0.0"
    description = "Description of your feature"
    author = "Your Name"
    
    def __init__(self):
        super().__init__()
        self.register_hooks()
        self.register_models()
        self.register_urls()
    
    def register_hooks(self):
        """Register hooks for core integration"""
        self.register_hook('before_contest_cycle_save', self.before_contest_save)
        self.register_hook('after_user_achievement', self.after_achievement)
    
    def register_models(self):
        """Register extension models"""
        from .models import YourExtensionModel
        self.register_model(YourExtensionModel)
    
    def register_urls(self):
        """Register extension URLs"""
        from .urls import urlpatterns
        self.register_urls(urlpatterns)
    
    def before_contest_save(self, contest, **kwargs):
        """Hook called before contest cycle save"""
        # Your logic here
        pass
    
    def after_achievement(self, achievement, **kwargs):
        """Hook called after user achievement"""
        # Your logic here
        pass

# Register plugin
PluginRegistry.register(YourFeaturePlugin)
```

### ধাপ ৩: Extension Configuration

```python
# api/gamification/extensions/your_feature_name/config.py

from api.gamification.plugins.config import ExtensionConfig

class YourFeatureConfig(ExtensionConfig):
    """
    Extension Configuration
    """
    
    # Extension settings
    ENABLED = True
    DEBUG = False
    
    # Feature-specific settings
    MAX_POINTS_PER_DAY = 1000
    BONUS_MULTIPLIER = 1.5
    
    # Integration settings
    CORE_HOOKS = [
        'before_contest_cycle_save',
        'after_user_achievement',
        'on_user_points_update'
    ]
    
    # Dependencies
    DEPENDENCIES = [
        'api.gamification.core.services',
        'api.gamification.INTEGRATION_SYSTEM.audit_logger'
    ]
    
    @classmethod
    def get_settings(cls):
        """Get extension settings"""
        return {
            'enabled': cls.ENABLED,
            'debug': cls.DEBUG,
            'max_points_per_day': cls.MAX_POINTS_PER_DAY,
            'bonus_multiplier': cls.BONUS_MULTIPLIER,
            'hooks': cls.CORE_HOOKS,
            'dependencies': cls.DEPENDENCIES
        }
```

### ধাপ ৪: Extension Models

```python
# api/gamification/extensions/your_feature_name/models.py

from django.db import models
from api.gamification.extensions.base import ExtensionModel
from api.gamification.models import ContestCycle, User

class YourExtensionModel(ExtensionModel):
    """
    Extension-specific model
    """
    
    # Core relationships (no modification to core models)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest_cycle = models.ForeignKey(
        ContestCycle, 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Extension-specific fields
    custom_field = models.CharField(max_length=255)
    points_earned = models.IntegerField(default=0)
    bonus_applied = models.BooleanField(default=False)
    
    # Integration fields
    extension_data = models.JSONField(default=dict)
    checksum = models.CharField(max_length=64, blank=True)
    
    class Meta:
        app_label = 'gamification_extensions'
        verbose_name = "Your Extension Model"
        verbose_name_plural = "Your Extension Models"
    
    def save(self, *args, **kwargs):
        # Generate checksum for integrity
        self.checksum = self.calculate_checksum()
        super().save(*args, **kwargs)
        
        # Trigger extension hooks
        self.trigger_hook('after_extension_model_save', instance=self)
    
    def calculate_checksum(self):
        """Calculate SHA-256 checksum"""
        import hashlib
        import json
        
        data = {
            'user_id': str(self.user_id),
            'custom_field': self.custom_field,
            'points_earned': self.points_earned,
            'bonus_applied': self.bonus_applied
        }
        
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
```

### ধাপ ৫: Extension Services

```python
# api/gamification/extensions/your_feature_name/services.py

from api.gamification.extensions.base import ExtensionService
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from .models import YourExtensionModel

class YourFeatureService(ExtensionService):
    """
    Extension-specific business logic
    """
    
    def __init__(self):
        super().__init__()
        self.audit_logger = audit_logger
        self.performance_monitor = performance_monitor
    
    def create_extension_record(self, user_id, custom_data, **kwargs):
        """
        Create extension record with full integration
        """
        start_time = timezone.now()
        
        try:
            # Log creation attempt
            self.audit_logger.log_audit(
                action='CREATE',
                description=f"Creating extension record for user {user_id}",
                resource_type='EXTENSION',
                details={'custom_data': custom_data}
            )
            
            # Create record
            record = YourExtensionModel.objects.create(
                user_id=user_id,
                custom_field=custom_data.get('field_name', ''),
                points_earned=custom_data.get('points', 0),
                extension_data=custom_data
            )
            
            # Record metrics
            duration = (timezone.now() - start_time).total_seconds()
            self.performance_monitor.record_metric(
                'extension_record_creation_duration',
                duration
            )
            
            # Log success
            self.audit_logger.log_audit(
                action='CREATE',
                description=f"Extension record created successfully",
                resource_type='EXTENSION',
                resource_id=str(record.id),
                details={'duration': duration, 'checksum': record.checksum}
            )
            
            return record
            
        except Exception as exc:
            # Log error
            self.audit_logger.log_audit(
                action='ERROR',
                description=f"Failed to create extension record: {exc}",
                resource_type='EXTENSION',
                error=str(exc)
            )
            
            self.performance_monitor.record_metric(
                'extension_record_creation_error',
                1.0
            )
            
            raise exc
    
    def calculate_bonus_points(self, user_id, base_points, **kwargs):
        """
        Calculate bonus points with integration
        """
        from .config import YourFeatureConfig
        
        multiplier = YourFeatureConfig.BONUS_MULTIPLIER
        bonus_points = int(base_points * multiplier)
        
        # Log calculation
        self.audit_logger.log_audit(
            action='CALCULATE',
            description=f"Bonus points calculated for user {user_id}",
            resource_type='EXTENSION',
            details={
                'base_points': base_points,
                'multiplier': multiplier,
                'bonus_points': bonus_points
            }
        )
        
        return bonus_points
```

---

## এক্সটেনশন প্যাটার্নস

### ১. Hook Pattern

Core API এর events ধরে extension logic execute করার জন্য:

```python
# Hook registration
self.register_hook('event_name', callback_function)

# Hook implementation
def callback_function(self, *args, **kwargs):
    # Your extension logic
    pass
```

### ২. Decorator Pattern

Core functionality কে extend করার জন্য:

```python
from api.gamification.extensions.decorators import extension_hook

@extension_hook('before_contest_save')
def enhance_contest_data(contest, **kwargs):
    # Add extension data
    contest.extension_data['your_feature'] = 'value'
    return contest
```

### ৩. Observer Pattern

Core events listen করার জন্য:

```python
from api.gamification.extensions.observers import ExtensionObserver

class YourObserver(ExtensionObserver):
    def on_contest_cycle_created(self, contest):
        # Handle contest creation
        pass
    
    def on_user_points_updated(self, user, old_points, new_points):
        # Handle points update
        pass
```

### ৪. Strategy Pattern

Different strategies implement করার জন্য:

```python
from api.gamification.extensions.strategies import BaseStrategy

class YourPointStrategy(BaseStrategy):
    def calculate_points(self, user, action, **kwargs):
        # Custom point calculation
        return custom_points

# Register strategy
StrategyRegistry.register('your_points', YourPointStrategy())
```

---

## বেস্ট প্র্যাকটিস

### ✅ Do's

1. **Always use extension framework**
2. **Follow naming conventions**
3. **Implement proper error handling**
4. **Add comprehensive logging**
5. **Write tests for extensions**
6. **Document your extension**
7. **Use dependency injection**
8. **Implement proper validation**

### ❌ Don'ts

1. **Never modify core models directly**
2. **Don't bypass extension framework**
3. **Avoid hard-coded dependencies**
4. **Don't create circular imports**
5. **Never override core methods**
6. **Don't access private core attributes**
7. **Avoid direct database queries on core tables**
8. **Don't break backward compatibility**

### 🔧 Configuration Management

```python
# Use environment variables
import os
from django.conf import settings

EXTENSION_SETTINGS = {
    'ENABLED': os.getenv('YOUR_FEATURE_ENABLED', 'True').lower() == 'true',
    'DEBUG': os.getenv('YOUR_FEATURE_DEBUG', 'False').lower() == 'true',
    'API_KEY': os.getenv('YOUR_FEATURE_API_KEY', ''),
}
```

### 📝 Logging Standards

```python
# Use structured logging
logger.info(
    "Extension operation completed",
    extra={
        'extension': 'your_feature',
        'operation': 'create_record',
        'user_id': user_id,
        'duration': duration,
        'success': True
    }
)
```

---

## উদাহরণ

### উদাহরণ ১: Loyalty Points Extension

```python
# api/gamification/extensions/loyalty_points/plugin.py

class LoyaltyPointsPlugin(BasePlugin):
    name = "loyalty_points"
    version = "1.0.0"
    
    def register_hooks(self):
        self.register_hook('after_user_achievement', self.award_loyalty_points)
        self.register_hook('on_contest_cycle_complete', self.calculate_bonus)
    
    def award_loyalty_points(self, achievement, **kwargs):
        """Award loyalty points for achievements"""
        from .services import LoyaltyPointsService
        
        service = LoyaltyPointsService()
        service.award_points(
            user_id=achievement.user_id,
            points=achievement.points_awarded * 0.1,  # 10% bonus
            source='achievement',
            reference_id=str(achievement.id)
        )
```

### উদাহরণ ২: Tournament Extension

```python
# api/gamification/extensions/tournaments/models.py

class Tournament(ExtensionModel):
    """Tournament model without touching core"""
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    prize_pool = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Reference to core (no modification)
    contest_cycles = models.ManyToManyField(
        'gamification.ContestCycle',
        related_name='tournaments'
    )
    
    participants = models.ManyToManyField(
        'auth.User',
        related_name='tournament_participations'
    )
```

### উদাহরণ ৩: Custom Rewards Extension

```python
# api/gamification/extensions/custom_rewards/services.py

class CustomRewardService(ExtensionService):
    
    def create_custom_reward(self, user_id, reward_type, reward_data, **kwargs):
        """Create custom reward with full integration"""
        
        # Validate against core achievement system
        from api.gamification.services import AchievementService
        
        core_service = AchievementService()
        user_achievements = core_service.get_user_achievements(user_id)
        
        # Apply business logic
        if self.is_eligible_for_reward(user_achievements, reward_type):
            return self._create_reward_record(user_id, reward_type, reward_data)
        
        raise ValueError("User not eligible for this reward")
```

---

## টেস্টিং

### Extension Testing Structure

```python
# api/gamification/extensions/your_feature_name/tests/

├── __init__.py
├── test_models.py
├── test_services.py
├── test_views.py
├── test_integrations.py
└── test_performance.py
```

### Test Example

```python
# api/gamification/extensions/your_feature_name/tests/test_services.py

from django.test import TestCase
from api.gamification.extensions.your_feature_name.services import YourFeatureService

class YourFeatureServiceTest(TestCase):
    
    def setUp(self):
        self.service = YourFeatureService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_extension_record(self):
        """Test extension record creation"""
        record = self.service.create_extension_record(
            user_id=self.user.id,
            custom_data={'field_name': 'test', 'points': 100}
        )
        
        self.assertIsNotNone(record)
        self.assertEqual(record.user_id, self.user.id)
        self.assertEqual(record.custom_field, 'test')
        self.assertEqual(record.points_earned, 100)
        self.assertIsNotNone(record.checksum)
    
    def test_calculate_bonus_points(self):
        """Test bonus points calculation"""
        bonus = self.service.calculate_bonus_points(
            user_id=self.user.id,
            base_points=100
        )
        
        self.assertEqual(bonus, 150)  # 100 * 1.5
```

### Integration Testing

```python
# api/gamification/extensions/your_feature_name/tests/test_integrations.py

from django.test import TestCase
from unittest.mock import patch, MagicMock
from api.gamification.extensions.your_feature_name.plugin import YourFeaturePlugin

class ExtensionIntegrationTest(TestCase):
    
    @patch('api.gamification.INTEGRATION_SYSTEM.audit_logger.log_audit')
    def test_core_integration(self, mock_audit):
        """Test integration with core system"""
        plugin = YourFeaturePlugin()
        
        # Test hook execution
        from api.gamification.models import ContestCycle
        contest = ContestCycle.objects.create(name='Test Contest')
        
        # Trigger hook
        plugin.before_contest_save(contest)
        
        # Verify audit log was called
        mock_audit.assert_called()
```

---

## ডিপ্লয়মেন্ট

### Extension Installation

```bash
# ১. Extension directory তৈরি
mkdir api/gamification/extensions/your_feature

# ২. Extension files তৈরি
# (উপরের structure অনুসরণ করুন)

# ৩. Migration তৈরি
python manage.py makemigrations gamification_extensions

# ৪. Migration apply
python manage.py migrate gamification_extensions

# ৫. Extension register
python manage.py register_extension your_feature
```

### Extension Configuration

```python
# settings.py

INSTALLED_APPS += [
    'api.gamification.extensions.your_feature',
]

# Extension settings
GAMIFICATION_EXTENSIONS = {
    'your_feature': {
        'ENABLED': True,
        'DEBUG': False,
        'CONFIG_FILE': 'your_feature_config.json',
    }
}
```

### Extension Management Commands

```python
# api/gamification/extensions/your_feature_name/management/commands/

├── __init__.py
├── enable_extension.py
├── disable_extension.py
├── extension_status.py
└── extension_health_check.py
```

### Monitoring and Health Checks

```python
# Extension health check endpoint
@extension_health_check
def check_extension_health():
    """Check extension health status"""
    
    checks = {
        'database_connection': check_db_connection(),
        'core_integration': check_core_integration(),
        'performance_metrics': check_performance_metrics(),
        'configuration': check_configuration(),
    }
    
    return {
        'status': 'healthy' if all(checks.values()) else 'unhealthy',
        'checks': checks,
        'timestamp': timezone.now().isoformat()
    }
```

---

## 🔧 Troubleshooting

### Common Issues

1. **Extension not loading**
   - Check plugin registration
   - Verify import paths
   - Check configuration

2. **Core integration failing**
   - Verify hook registration
   - Check dependency injection
   - Review error logs

3. **Performance issues**
   - Profile extension code
   - Check database queries
   - Monitor memory usage

### Debug Mode

```python
# Enable debug mode
DEBUG_EXTENSIONS = True

# Debug logging
import logging
logging.getLogger('gamification.extensions').setLevel(logging.DEBUG)
```

---

## 📚 রেফারেন্স

### Core API Documentation
- [Core Models](./core/models.md)
- [Core Services](./core/services.md)
- [Integration System](./INTEGRATION_SYSTEM/README.md)

### Extension Framework
- [Plugin System](./plugins/README.md)
- [Hook Documentation](./plugins/hooks.md)
- [Extension Base Classes](./extensions/base.md)

### Best Practices
- [Coding Standards](./docs/coding_standards.md)
- [Testing Guidelines](./docs/testing.md)
- [Performance Guidelines](./docs/performance.md)

---

## 🤝 সহায়তা

### সাপোর্ট
- Email: support@gamification.com
- Slack: #gamification-extensions
- Documentation: https://docs.gamification.com/extensions

### কন্ট্রিবিউশন
- GitHub: https://github.com/gamification/extensions
- Contributing Guide: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Code Review Process: [REVIEW_GUIDE.md](./docs/review_guide.md)

---

## 📝 চেকলিস্ট

### Extension Development Checklist

- [ ] Extension structure created
- [ ] Plugin registration implemented
- [ ] Configuration defined
- [ ] Models created (if needed)
- [ ] Services implemented
- [ ] Views and serializers added
- [ ] Admin configuration
- [ ] URL routing
- [ ] Tests written
- [ ] Documentation updated
- [ ] Migration files created
- [ ] Integration tests passed
- [ ] Performance tests passed
- [ ] Security review completed
- [ ] Deployment guide updated

### Production Deployment Checklist

- [ ] Extension enabled in production
- [ ] Migrations applied
- [ ] Configuration verified
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rollback plan ready
- [ ] Documentation updated
- [ ] Team training completed

---

**🎉 Congratulations!** এই guide অনুসরণ করে আপনি সফলভাবে নতুন ফিচার যোগ করতে পারবেন core API touch না করেই!

---

*এই guide সম্পর্কে কোনো প্রশ্ন থাকলে অথবা উন্নতির পরামর্শ থাকলে দয়া করে যোগাযোগ করুন।*
