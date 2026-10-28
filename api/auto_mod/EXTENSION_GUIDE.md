# Auto Mod Extension Guide

> "এক কাজের জন্য একটাই মালিক" — এই guide অনুসরণ করলে **core auto_mod code কখনো touch করতে হবে না।"

## 📋 সূচনা

এই guide টি auto_mod সিস্টেমে নতুন features যোগ করার জন্য তৈরি করা হয়েছে। এখানে core code পরিবর্তন না করেই কিভাবে extensible architecture ব্যবহার করে নতুন functionality যোগ করা যায় তা দেখানো হয়েছে।

---

## 🏗️ Architecture Overview

### Core Components (যেগুলো পরিবর্তন করা যাবে না)

```
api/auto_mod/
├── models.py              ✅ Core Models (Don't touch)
├── services.py             ✅ Core Services (Don't touch)
├── tasks.py                ✅ Core Tasks (Don't touch)
├── signals.py              ✅ Core Signals (Don't touch)
├── constants.py            ✅ Core Constants (Don't touch)
└── ...
```

### Extension Points (যেগুলো ব্যবহার করা যাবে)

```
api/auto_mod/
├── extensions/             🆕 Your extensions here
│   ├── __init__.py
│   ├── scanners/           🆕 Custom scanners
│   ├── validators/         🆕 Custom validators
│   ├── processors/         🆕 Custom processors
│   └── hooks/              🆕 Custom hooks
├── events.py               ✅ Event system (Use for extensions)
├── hooks.py                ✅ Hook system (Use for extensions)
├── signals_cap.py          ✅ Signal capabilities
└── tasks_cap.py            ✅ Task capabilities
```

---

## 🚀 Extension Methods

### Method 1: Event-Driven Extensions (Recommended)

**সবন্ধরভাবে ব্যবহার করুন এটি**

```python
# api/auto_mod/extensions/my_feature/__init__.py

from api.auto_mod.events import EventDispatcher, Event
from api.auto_mod.hooks import HookRegistry, BaseHook

class MyFeatureEvent(Event):
    """Custom event for my feature"""
    def __init__(self, submission_id, custom_data):
        super().__init__('my_feature_triggered')
        self.submission_id = submission_id
        self.custom_data = custom_data

class MyFeatureHook(BaseHook):
    """Custom hook for my feature"""
    def __init__(self):
        super().__init__('my_feature_processor')
    
    def execute(self, context):
        # Your custom logic here
        print(f"Processing feature for {context.get('submission_id')}")
        return context

# Register hooks
HookRegistry.register_hook(MyFeatureHook())

# Dispatch events
def trigger_my_feature(submission_id, data):
    dispatcher = EventDispatcher()
    event = MyFeatureEvent(submission_id, data)
    dispatcher.dispatch(event)
```

### Method 2: Plugin-Based Extensions

**যখন আপনার নিজের একাধিকার feature থাকে**

```python
# api/auto_mod/extensions/my_feature/scanner.py

from api.auto_mod.services.ScannerService
from api.auto_mod.models import SuspiciousSubmission

class MyCustomScanner:
    """Custom scanner that doesn't modify core code"""
    
    def __init__(self):
        self.name = "my_custom_scanner"
    
    def scan(self, submission: SuspiciousSubmission) -> dict:
        """Custom scanning logic"""
        custom_result = {
            'scanner_type': self.name,
            'confidence': 0.85,
            'risk_score': 0.7,
            'details': {
                'custom_analysis': self._analyze_content(submission),
                'pattern_matches': self._detect_patterns(submission)
            }
        }
        
        # Store custom results without touching core models
        self._store_custom_result(submission.id, custom_result)
        
        return custom_result
    
    def _analyze_content(self, submission):
        """Your custom analysis logic"""
        return {"analysis": "custom_result"}
    
    def _detect_patterns(self, submission):
        """Your custom pattern detection"""
        return {"patterns": ["pattern1", "pattern2"]}
    
    def _store_custom_result(self, submission_id, result):
        """Store in your own table/cache"""
        # Use your own model or cache
        pass

# Register scanner
from api.auto_mod.extensions import register_scanner
register_scanner(MyCustomScanner())
```

### Method 3: Task-Based Extensions

**Background processing এর জন্য**

```python
# api/auto_mod/extensions/my_feature/tasks.py

from celery import shared_task
from api.auto_mod.signals_cap import SignalCapability

@shared_task
def my_feature_processor(submission_id):
    """Custom background task"""
    # Your custom processing logic
    result = process_with_custom_logic(submission_id)
    
    # Emit custom signal
    signal_cap = SignalCapability()
    signal_cap.emit_signal('my_feature_completed', {
        'submission_id': submission_id,
        'result': result
    })
    
    return result

# Register with signal capabilities
SignalCapability.register_signal_handler('my_feature_completed', my_feature_handler)
```

---

## 📁 File Structure for Extensions

### Step 1: Extension Directory তৈরি করুন

```bash
mkdir -p api/auto_mod/extensions/your_feature
mkdir -p api/auto_mod/extensions/your_feature/{scanners,validators,processors,hooks}
touch api/auto_mod/extensions/your_feature/__init__.py
```

### Step 2: Extension Files তৈরি করুন

```python
# api/auto_mod/extensions/your_feature/__init__.py

from .scanners import YourCustomScanner
from .validators import YourCustomValidator
from .processors import YourCustomProcessor
from .hooks import YourCustomHook

# Auto-registration
def register_extensions():
    """Register all your extensions"""
    # Register scanner
    from api.auto_mod.extensions import register_scanner
    register_scanner(YourCustomScanner())
    
    # Register validator
    from api.auto_mod.extensions import register_validator
    register_validator(YourCustomValidator())
    
    # Register processor
    from api.auto_mod.extensions import register_processor
    register_processor(YourCustomProcessor())
    
    # Register hook
    from api.auto_mod.hooks import HookRegistry
    HookRegistry.register_hook(YourCustomHook())
```

---

## 🔌 Hook Points (Core System Integration)

### Available Hook Points

```python
# Core hooks you can extend without modifying core code

HOOK_POINTS = {
    'submission_received': 'When a new submission arrives',
    'submission_scanned': 'After scanning is complete',
    'decision_made': 'When a moderation decision is made',
    'appeal_created': 'When an appeal is created',
    'bot_status_changed': 'When bot status changes',
    'rule_matched': 'When an auto-approval rule matches',
    'queue_item_assigned': 'When queue item is assigned',
    'model_retrained': 'When ML model is retrained'
}
```

### Hook Registration Example

```python
# api/auto_mod/extensions/your_feature/hooks.py

from api.auto_mod.hooks import BaseHook, HookRegistry

class YourFeatureHook(BaseHook):
    """Hook that integrates with core system"""
    
    def __init__(self):
        super().__init__('your_feature_processor')
        self.priority = 50  # Lower priority than core hooks
    
    def execute(self, context):
        """Execute your custom logic"""
        hook_point = context.get('hook_point')
        
        if hook_point == 'submission_received':
            return self.handle_submission_received(context)
        elif hook_point == 'decision_made':
            return self.handle_decision_made(context)
        
        return context
    
    def handle_submission_received(self, context):
        """Handle new submission"""
        submission = context.get('submission')
        # Your custom logic here
        return context
    
    def handle_decision_made(self, context):
        """Handle moderation decision"""
        decision = context.get('decision')
        # Your custom logic here
        return context

# Auto-register
HookRegistry.register_hook(YourFeatureHook())
```

---

## 🎯 Use Cases & Examples

### Use Case 1: Custom Scanner Integration

```python
# api/auto_mod/extensions/custom_ai/scanner.py

class CustomAIScanner:
    """Custom AI scanner without touching core code"""
    
    def scan(self, submission):
        """Scan submission with custom AI"""
        # Use your own AI service
        result = your_ai_service.analyze(submission.text_content)
        
        # Store results in your own table
        CustomScanResult.objects.create(
            submission_id=submission.id,
            ai_result=result,
            confidence=result['confidence']
        )
        
        return result

# Register without core changes
from api.auto_mod.extensions import register_scanner
register_scanner(CustomAIScanner())
```

### Use Case 2: Custom Validation Rules

```python
# api/auto_mod/extensions/business_rules/validator.py

class BusinessRuleValidator:
    """Business-specific validation without core changes"""
    
    def validate(self, submission):
        """Apply business rules"""
        violations = []
        
        # Your custom business rules
        if self._contains_prohibited_content(submission):
            violations.append('prohibited_content')
        
        if self._violates_business_policy(submission):
            violations.append('business_policy_violation')
        
        return violations

# Register
from api.auto_mod.extensions import register_validator
register_validator(BusinessRuleValidator())
```

### Use Case 3: Custom Analytics

```python
# api/auto_mod/extensions/analytics/processor.py

class AnalyticsProcessor:
    """Custom analytics without touching core"""
    
    def process(self, submission, decision):
        """Process analytics data"""
        # Store in your analytics system
        analytics_data = {
            'submission_id': submission.id,
            'decision_type': decision.decision_type,
            'processing_time': decision.processing_time,
            'custom_metrics': self._calculate_custom_metrics(submission)
        }
        
        # Send to your analytics service
        analytics_service.track_event('moderation_completed', analytics_data)

# Register
from api.auto_mod.extensions import register_processor
register_processor(AnalyticsProcessor())
```

---

## 📊 Data Storage (Without Core Modifications)

### Option 1: Separate Models

```python
# api/auto_mod/extensions/your_feature/models.py

from django.db import models
from api.auto_mod.models import SuspiciousSubmission

class YourFeatureData(models.Model):
    """Your custom data model"""
    submission = models.ForeignKey(SuspiciousSubmission, on_delete=models.CASCADE)
    custom_field = models.TextField()
    confidence = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'auto_mod_extensions'
```

### Option 2: JSON Field Extensions

```python
# Use existing submission's metadata field
def store_custom_data(submission_id, custom_data):
    """Store custom data in metadata field"""
    submission = SuspiciousSubmission.objects.get(id=submission_id)
    
    # Add to existing metadata
    metadata = submission.metadata or {}
    metadata.update({
        'your_feature': custom_data,
        'processed_at': timezone.now().isoformat()
    })
    
    submission.metadata = metadata
    submission.save(update_fields=['metadata'])
```

### Option 3: External Storage

```python
# Use Redis or external database
import redis

def store_custom_result(submission_id, result):
    """Store in Redis"""
    redis_client = redis.Redis()
    key = f"custom_feature:{submission_id}"
    redis_client.setex(key, 3600, json.dumps(result))  # 1 hour expiry
```

---

## 🔧 Configuration

### Extension Settings

```python
# settings.py

# Auto mod extension settings
AUTO_MOD_EXTENSIONS = {
    'enabled': True,
    'custom_scanners': [
        'api.auto_mod.extensions.your_feature.scanners.YourCustomScanner',
        'api.auto_mod.extensions.ai_scanner.AIScanner',
    ],
    'custom_validators': [
        'api.auto_mod.extensions.business_rules.BusinessRuleValidator',
    ],
    'custom_processors': [
        'api.auto_mod.extensions.analytics.AnalyticsProcessor',
    ],
    'storage_backend': 'redis',  # or 'database', 'file'
}
```

### Extension Registry

```python
# api/auto_mod/extensions/registry.py

class ExtensionRegistry:
    """Registry for managing extensions"""
    
    def __init__(self):
        self.scanners = []
        self.validators = []
        self.processors = []
        self.hooks = []
    
    def register_scanner(self, scanner_class):
        """Register a scanner"""
        self.scanners.append(scanner_class)
    
    def register_validator(self, validator_class):
        """Register a validator"""
        self.validators.append(validator_class)
    
    def register_processor(self, processor_class):
        """Register a processor"""
        self.processors.append(processor_class)
    
    def register_hook(self, hook_class):
        """Register a hook"""
        self.hooks.append(hook_class)

# Global registry
extension_registry = ExtensionRegistry()

# Convenience functions
def register_scanner(scanner_class):
    extension_registry.register_scanner(scanner_class)

def register_validator(validator_class):
    extension_registry.register_validator(validator_class)

def register_processor(processor_class):
    extension_registry.register_processor(processor_class)
```

---

## 🚨 Best Practices

### ✅ Do's

1. **Use Event System** - Core events ব্যবহার করুন core code touch না করে
2. **Register Extensions** - Extension registry ব্যবহার করুন
3. **Separate Storage** - আপনার data আলাদা করে store করুন
4. **Test Extensions** - আপনার extensions আলাদাভাবে test করুন
5. **Document Extensions** - Clear documentation রাখুন

### ❌ Don'ts

1. **Don't modify core models** - কখনো models.py পরিবর্তন করবেন না
2. **Don't modify core services** - services.py পরিবর্তন করবেন না
3. **Don't break existing APIs** - Core functionality break করবেন না
4. **Don't add dependencies** - Core system-এ নতুন dependencies add করবেন না
5. **Don't store in core tables** - Core tables-এ নতুন fields add করবেন না

---

## 🔍 Testing Extensions

### Unit Tests

```python
# api/auto_mod/extensions/your_feature/tests.py

from django.test import TestCase
from api.auto_mod.extensions.your_feature.scanner import YourCustomScanner

class YourFeatureTest(TestCase):
    """Test your custom feature"""
    
    def setUp(self):
        self.scanner = YourCustomScanner()
    
    def test_custom_scan(self):
        """Test custom scanning logic"""
        submission = create_test_submission()
        result = self.scanner.scan(submission)
        
        self.assertIn('confidence', result)
        self.assertIn('risk_score', result)
        self.assertGreater(result['confidence'], 0.5)
```

### Integration Tests

```python
# api/auto_mod/tests/test_extensions.py

from django.test import TestCase
from api.auto_mod.signals import submission_received
from api.auto_mod.extensions.your_feature.hooks import YourFeatureHook

class ExtensionIntegrationTest(TestCase):
    """Test extension integration"""
    
    def test_hook_execution(self):
        """Test hook execution"""
        # Create test submission
        submission = create_test_submission()
        
        # Trigger signal
        submission_received.send(sender=SuspiciousSubmission, instance=submission)
        
        # Verify hook executed
        self.assertTrue(CustomHookData.objects.filter(submission=submission).exists())
```

---

## 📚 Examples Repository

### Complete Example: Custom AI Scanner

```python
# api/auto_mod/extensions/ai_scanner/__init__.py

from .scanner import AdvancedAIScanner
from .models import AIScanResult

def register_extensions():
    """Register AI scanner extensions"""
    from api.auto_mod.extensions import register_scanner
    register_scanner(AdvancedAIScanner())

# api/auto_mod/extensions/ai_scanner/scanner.py

class AdvancedAIScanner:
    """Advanced AI scanner example"""
    
    def __init__(self):
        self.name = "advanced_ai_scanner"
        self.ai_client = self._init_ai_client()
    
    def scan(self, submission):
        """Scan with advanced AI"""
        # Get content
        content = self._extract_content(submission)
        
        # AI analysis
        ai_result = self.ai_client.analyze(content)
        
        # Store results
        result = AIScanResult.objects.create(
            submission=submission,
            ai_confidence=ai_result['confidence'],
            risk_score=ai_result['risk_score'],
            analysis=ai_result['analysis'],
            processing_time=ai_result['processing_time']
        )
        
        return {
            'scanner_type': self.name,
            'confidence': ai_result['confidence'],
            'risk_score': ai_result['risk_score'],
            'details': {
                'ai_result_id': result.id,
                'analysis_summary': ai_result['summary']
            }
        }
```

---

## 🎯 Quick Start Guide

### 1-Minute Setup

```python
# 1. Create extension file
# api/auto_mod/extensions/my_feature/__init__.py

# 2. Add your code
from api.auto_mod.hooks import BaseHook, HookRegistry

class MyHook(BaseHook):
    def execute(self, context):
        print(f"My feature triggered: {context}")
        return context

# 3. Register
HookRegistry.register_hook(MyHook())

# 4. Done! No core code touched
```

---

## 📞 Support

### Common Issues

1. **Extension not loading** - Check `__init__.py` imports
2. **Hook not executing** - Verify hook point name
3. **Data not saving** - Check model configuration
4. **Tests failing** - Verify test setup

### Debug Tips

```python
# Enable extension logging
import logging
logging.getLogger('api.auto_mod.extensions').setLevel(logging.DEBUG)

# Check registered extensions
from api.auto_mod.extensions.registry import extension_registry
print(f"Registered scanners: {len(extension_registry.scanners)}")
```

---

## 🏆 Success Stories

### Example 1: Custom Language Detection

> "আমরা বাংলা detection যোগ করেছি core code touch না করেই। Event system ব্যবহার করে 15টি language support add করেছি।"

### Example 2: Business Rules Engine

> "আমাদের business validation rules যোগ করেছি। Hook system ব্যবহার করে core logic পরিবর্তন না করেই।"

---

## 📖 Conclusion

এই guide অনুসরণ করে আপনি auto_mod system-এ নতুন features যোগ করতে পারবেন core code modify না করেই। Event system, hooks, এবং extension registry ব্যবহার করে maintainable এবং extensible architecture maintain করতে পারবেন।

**Remember:** "এক কাজের জন্য একটাই মালিক" - Core code রক্ষা করুন, extensions দিয় কাজ করুন! 🚀
