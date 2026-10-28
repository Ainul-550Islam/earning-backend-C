# Security Module Extension Guide

## 📋 সূচনাপত্র (Table of Contents)

- [ভূমিকা](#ভূমিকা)
- [আর্কিটেকচার ওভারভিউ](#আর্কিটেকচার-ওভারভিউ)
- [নতুন ফিচার যোগ করার পদ্ধতি](#নতুন-ফিচার-যোগ-করার-পদ্ধতি)
- [এক্সটেনশন টেমপ্লেট](#এক্সটেনশন-টেমপ্লেট)
- [উদাহরণ ফিচার](#উদাহরণ-ফিচার)
- [বেস্ট প্র্যাকটিস](#বেস্ট-প্র্যাকটিস)
- [ট্রাবলশুটিং](#ট্রাবলশুটিং)
- [ফিচার ভেরিফিকেশন](#ফিচার-ভেরিফিকেশন)

---

## 🎯 ভূমিকা

এই গাইডের উদ্দেশ্য হলো Security Module-এ নতুন ফিচার যোগ করার জন্য একটি স্ট্যান্ডার্ড পদ্ধতি প্রদান করা। **"এক কাজের জন্য একটাই মালিক"** - এই guide অনুসরণ করলে core security code কখনো touch করতে হবে না।

### 🎨 মূলনীতি

- **কোর কোড অপরিবর্তিত রাখুন** - কখনোই core security files মডিফাই করবেন না
- **এক্সটেনশন-ফার্স্ট ডিজাইন** - নতুন ফিচার এক্সটেনশন হিসেবে তৈরি করুন
- **ডিপেন্ডেন্সি ইনজেকশন** - ডিপেন্ডেন্সি ইনজেকশন ব্যবহার করুন
- **ইন্টারফেস ফলো করুন** - সব ইন্টারফেস ও এবস্ট্রাক্ট ক্লাস ফলো করুন

---

## 🏗️ আর্কিটেকচার ওভারভিউ

### কোর কম্পোনেন্টস (অপরিবর্তনীয়)
```
api/security/
├── core/                    # Core security logic (অপরিবর্তনীয়)
├── models.py               # Core models (অপরিবর্তনীয়)
├── views.py                # Core views (অপরিবর্তনীয়)
├── serializers.py          # Core serializers (অপরিবর্তনীয়)
└── settings.py             # Core settings (অপরিবর্তনীয়)
```

### এক্সটেনশন এরিয়া (এক্সটেন্ডেড)
```
api/security/
├── extensions/             # নতুন ফিচার এখানে যোগ করুন
├── plugins/               # Plugin-based extensions
├── adapters/              # Adapter patterns
└── integration_system/    # Integration extensions
```

---

## 🔧 নতুন ফিচার যোগ করার পদ্ধতি

### স্টেপ ১: ফিচার প্ল্যানিং

#### ১.১ ফিচার ডিফাইনেশন
```python
# ফিচারের উদ্দেশ্য ও স্কোপ ডিফাইন করুন
FEATURE_NAME = "advanced_threat_detection"
VERSION = "1.0.0"
DESCRIPTION = "Advanced threat detection with ML integration"
```

#### ১.২ ডিপেন্ডেন্সি অ্যানালাইসিস
```python
# কোন কোর কম্পোনেন্টস প্রয়োজন
REQUIRED_CORE_COMPONENTS = [
    'models.SecurityLog',
    'models.SecurityIncident',
    'services.SecurityService'
]

# বাহ্যিক ডিপেন্ডেন্সি
EXTERNAL_DEPENDENCIES = [
    'scikit-learn>=1.0.0',
    'numpy>=1.21.0'
]
```

### স্টেপ ২: এক্সটেনশন স্ট্রাকচার তৈরি

#### ২.১ বেসিক ফোল্ডার স্ট্রাকচার
```
api/security/extensions/
└── advanced_threat_detection/
    ├── __init__.py
    ├── models.py          # Extension models
    ├── services.py        # Extension services
    ├── views.py           # Extension views
    ├── serializers.py     # Extension serializers
    ├── urls.py            # Extension URLs
    ├── admin.py           # Extension admin
    ├── migrations/        # Database migrations
    ├── tests/             # Test files
    ├── config.py          # Configuration
    └── README.md          # Documentation
```

#### ২.২ এক্সটেনশন রেজিস্ট্রেশন
```python
# api/security/extensions/advanced_threat_detection/__init__.py

from .config import ExtensionConfig
from ..registry import extension_registry

# এক্সটেনশন রেজিস্টার করুন
extension_registry.register(
    name="advanced_threat_detection",
    version="1.0.0",
    config_class=ExtensionConfig,
    module_path=__name__
)
```

### স্টেপ ৩: কোর ইন্টিগ্রেশন

#### ৩.১ এক্সটেনশন কনফিগ
```python
# api/security/extensions/advanced_threat_detection/config.py

from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class ExtensionConfig:
    """এক্সটেনশন কনফিগারেশন"""
    
    # বেসিক সেটিংস
    name: str = "advanced_threat_detection"
    version: str = "1.0.0"
    enabled: bool = True
    
    # কোর ইন্টিগ্রেশন
    core_models: List[str] = [
        'SecurityLog',
        'SecurityIncident',
        'ThreatIntelligence'
    ]
    
    # এক্সটেনশন সেটিংস
    ml_model_path: str = "models/threat_detector.pkl"
    confidence_threshold: float = 0.8
    batch_size: int = 100
    
    # ইন্টিগ্রেশন পয়েন্ট
    signal_handlers: List[str] = [
        'security_log_created',
        'threat_detected'
    ]
    
    def get_settings(self) -> Dict[str, Any]:
        """Django settings-এ এক্সপোজ করার জন্য"""
        return {
            f'{self.name.upper()}_ENABLED': self.enabled,
            f'{self.name.upper()}_MODEL_PATH': self.ml_model_path,
            f'{self.name.upper()}_CONFIDENCE_THRESHOLD': self.confidence_threshold,
            f'{self.name.upper()}_BATCH_SIZE': self.batch_size,
        }
```

#### ৩.২ কোর মডেল এক্সটেনশন
```python
# api/security/extensions/advanced_threat_detection/models.py

from django.db import models
from api.security.models import SecurityLog, SecurityIncident
from ..config import ExtensionConfig

class ThreatDetectionResult(models.Model):
    """এক্সটেনশন মডেল - কোর মডেল টাচ করে না"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    security_log = models.ForeignKey(
        SecurityLog, 
        on_delete=models.CASCADE,
        related_name='threat_detections'
    )
    
    # এক্সটেনশন-স্পেসিফিক ফিল্ড
    threat_score = models.FloatField()
    threat_type = models.CharField(max_length=100)
    confidence = models.FloatField()
    ml_features = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'security'
        db_table = 'extension_threat_detection_results'
```

#### ৩.৩ সার্ভিস ইন্টিগ্রেশন
```python
# api/security/extensions/advanced_threat_detection/services.py

from typing import Dict, Any, List
from django.utils import timezone
from api.security.services import SecurityService
from api.security.models import SecurityLog
from .models import ThreatDetectionResult

class AdvancedThreatDetectionService:
    """এক্সটেনশন সার্ভিস - কোর সার্ভিস ইনহেরিট করে"""
    
    def __init__(self):
        self.core_service = SecurityService()
        self.config = ExtensionConfig()
    
    def analyze_security_log(self, log_id: str) -> Dict[str, Any]:
        """কোর SecurityLog এনালাইজ করে"""
        
        # কোর সার্ভিস থেকে ডেটা নিন
        log_data = self.core_service.get_security_log(log_id)
        
        # এক্সটেনশন লজিক প্রয়োগ করুন
        threat_analysis = self._analyze_threat_patterns(log_data)
        
        # এক্সটেনশন মডেলে সেভ করুন
        result = ThreatDetectionResult.objects.create(
            security_log_id=log_id,
            threat_score=threat_analysis['score'],
            threat_type=threat_analysis['type'],
            confidence=threat_analysis['confidence'],
            ml_features=threat_analysis['features']
        )
        
        return {
            'threat_detected': threat_analysis['score'] > self.config.confidence_threshold,
            'result_id': str(result.id),
            'analysis': threat_analysis
        }
    
    def _analyze_threat_patterns(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """এক্সটেনশন-স্পেসিফিক এনালাইসিস"""
        # ML মডেল ব্যবহার করে এনালাইসিস
        features = self._extract_features(log_data)
        prediction = self._ml_predict(features)
        
        return {
            'score': prediction['score'],
            'type': prediction['type'],
            'confidence': prediction['confidence'],
            'features': features
        }
```

### স্টেপ ৪: ইন্টিগ্রেশন পয়েন্টস

#### ৪.১ সিগন্যাল হ্যান্ডলিং
```python
# api/security/extensions/advanced_threat_detection/signals.py

from django.dispatch import receiver
from api.security.signals import security_log_created
from .services import AdvancedThreatDetectionService

@receiver(security_log_created)
def analyze_new_security_log(sender, instance, **kwargs):
    """নতুন SecurityLog তৈরি হলে এনালাইজ করুন"""
    
    service = AdvancedThreatDetectionService()
    result = service.analyze_security_log(str(instance.id))
    
    if result['threat_detected']:
        # কোর ইনসিডেন্ট তৈরি করুন
        from api.security.models import SecurityIncident
        SecurityIncident.objects.create(
            title=f"Advanced Threat Detected: {result['analysis']['type']}",
            incident_type='advanced_threat',
            severity='high',
            description=f"ML-based threat detection with score {result['analysis']['score']}",
            metadata={
                'extension': 'advanced_threat_detection',
                'result_id': result['result_id'],
                'analysis': result['analysis']
            }
        )
```

#### ৪.২ ভিউ এক্সটেনশন
```python
# api/security/extensions/advanced_threat_detection/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from api.security.views import SecurityViewSet as CoreSecurityViewSet
from .services import AdvancedThreatDetectionService
from .serializers import ThreatDetectionSerializer

class AdvancedThreatDetectionViewSet(CoreSecurityViewSet):
    """কোর ভিউসেট এক্সটেন্ড করুন"""
    
    def __init__(self):
        super().__init__()
        self.detection_service = AdvancedThreatDetectionService()
    
    def analyze_threat(self, request, log_id=None):
        """কাস্টম এন্ডপয়েন্ট"""
        
        if log_id:
            result = self.detection_service.analyze_security_log(log_id)
        else:
            # ব্যাচ এনালাইসিস
            result = self.detection_service.batch_analyze()
        
        return Response({
            'status': 'success',
            'data': result
        }, status=status.HTTP_200_OK)
```

### স্টেপ ৫: কনফিগারেশন ও সেটআপ

#### ৫.১ Django Settings আপডেট
```python
# settings.py

# এক্সটেনশন সেটিংস অটো-লোড
EXTENSION_SETTINGS = {
    'advanced_threat_detection': {
        'ENABLED': True,
        'MODEL_PATH': 'models/threat_detector.pkl',
        'CONFIDENCE_THRESHOLD': 0.8,
        'BATCH_SIZE': 100,
    }
}

# এক্সটেনশন ইনস্টল করুন
INSTALLED_EXTENSIONS = [
    'api.security.extensions.advanced_threat_detection',
    'api.security.extensions.behavioral_analysis',
    'api.security.extensions.real_time_monitoring',
]
```

#### ৫.২ URL রাউটিং
```python
# api/security/extensions/advanced_threat_detection/urls.py

from django.urls import path, include
from .views import AdvancedThreatDetectionViewSet

urlpatterns = [
    path('analyze/<uuid:log_id>/', AdvancedThreatDetectionViewSet.as_view({'post': 'analyze_threat'})),
    path('batch-analyze/', AdvancedThreatDetectionViewSet.as_view({'post': 'batch_analyze'})),
]

# api/security/urls.py-এ যোগ করুন
urlpatterns += [
    path('extensions/advanced-threat/', include('api.security.extensions.advanced_threat_detection.urls')),
]
```

---

## 📝 এক্সটেনশন টেমপ্লেট

### টেমপ্লেট স্ট্রাকচার
```bash
# কপি করে নতুন ফিচার তৈরি করুন
cp -r api/security/extensions/template api/security/extensions/your_feature_name
```

### টেমপ্লেট ফাইলস

#### `__init__.py`
```python
"""
{{FEATURE_NAME}} Extension
{{DESCRIPTION}}
"""

from .config import ExtensionConfig
from ..registry import extension_registry

# এক্সটেনশন রেজিস্টার
extension_registry.register(
    name="{{FEATURE_SLUG}}",
    version="{{VERSION}}",
    config_class=ExtensionConfig,
    module_path=__name__
)

# সিগন্যাল কানেক্ট
from . import signals

# Export
__all__ = ['ExtensionConfig']
```

#### `config.py`
```python
"""
{{FEATURE_NAME}} Configuration
"""

from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class ExtensionConfig:
    """{{FEATURE_NAME}} কনফিগারেশন"""
    
    # বেসিক সেটিংস
    name: str = "{{FEATURE_SLUG}}"
    version: str = "{{VERSION}}"
    enabled: bool = True
    
    # কোর ইন্টিগ্রেশন
    core_models: List[str] = [
        # কোর মডেল লিস্ট
    ]
    
    # এক্সটেনশন সেটিংস
    # {{TODO: ফিচার-স্পেসিফিক সেটিংস}}
    
    def get_settings(self) -> Dict[str, Any]:
        """Django settings-এ এক্সপোজ"""
        return {
            f'{self.name.upper()}_ENABLED': self.enabled,
            # {{TODO: অন্য সেটিংস}}
        }
```

#### `models.py`
```python
"""
{{FEATURE_NAME}} Models
"""

from django.db import models
from api.security.models import SecurityLog  # কোর মডেল ইমপোর্ট

class {{FEATURE_NAME}}Result(models.Model):
    """{{FEATURE_NAME}} রেজাল্ট মডেল"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    security_log = models.ForeignKey(
        SecurityLog,
        on_delete=models.CASCADE,
        related_name='{{FEATURE_SLUG}}_results'
    )
    
    # {{TODO: ফিচার-স্পেসিফিক ফিল্ডস}}
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'security'
        db_table = 'extension_{{FEATURE_SLUG}}_results'
```

---

## 🚀 উদাহরণ ফিচার

### উদাহরণ ১: বিহেভিওরাল অ্যানালিটিক্স

```python
# api/security/extensions/behavioral_analysis/
├── __init__.py
├── config.py
├── models.py          # UserBehaviorPattern
├── services.py        # BehavioralAnalysisService
├── views.py           # BehavioralAnalyticsViewSet
└── signals.py         # user_activity_tracker

# কোর ইন্টিগ্রেশন
class UserBehaviorPattern(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    security_log = models.ForeignKey('api.security.SecurityLog', on_delete=models.CASCADE)
    behavior_score = models.FloatField()
    anomaly_detected = models.BooleanField(default=False)
```

### উদাহরণ ২: রিয়েল-টাইম মনিটরিং

```python
# api/security/extensions/real_time_monitoring/
├── __init__.py
├── config.py
├── services.py        # RealTimeMonitorService
├── consumers.py       # WebSocket consumers
├── tasks.py          # Celery tasks
└── websockets.py      # WebSocket handlers

# কোর ইন্টিগ্রেশন
@receiver(security_log_created)
def real_time_alert(sender, instance, **kwargs):
    if instance.severity == 'critical':
        # WebSocket-এ রিয়েল-টাইম নোটিফিকেশন
        send_websocket_notification({
            'type': 'security_alert',
            'data': instance.to_dict()
        })
```

---

## ✅ বেস্ট প্র্যাকটিস

### ১. কোড অর্গানাইজেশন
- **সিঙ্গেল রেসপন্সিবিলিটি**: প্রতি এক্সটেনশন একটি নির্দিষ্ট কাজ করে
- **লুজ কাপলিং**: কোর কোডের সাথে টাইট কাপলিং এড়াও
- **ডিপেন্ডেন্সি ইনজেকশন**: সরাসরি ডিপেন্ডেন্সি এড়াও

### ২. ডেটাবেস ডিজাইন
- **ফরেন কি রেফারেন্স**: কোর মডেলের সাথে ফরেন কি ব্যবহার
- **সেপারেট টেবিল**: এক্সটেনশন ডেটা আলাদা টেবিলে
- **ইনডেক্সিং**: পারফরম্যান্সের জন্য প্রপার ইনডেক্সিং

### ৩. পারফরম্যান্স
- **অ্যাসিনক্রোনাস প্রসেসিং**: ভারী কাজের জন্য Celery ব্যবহার
- **ক্যাশিং**: ফ্রিকোয়েন্টলি এক্সেস করা ডেটা ক্যাশ করুন
- **ব্যাচ প্রসেসিং**: বড় ডেটাসেট ব্যাচে প্রসেস করুন

### ৪. সিকিউরিটি
- **পারমিশন চেক**: কোর পারমিশন সিস্টেম ব্যবহার
- **ভ্যালিডেশন**: ইনপুট ভ্যালিডেশন করুন
- **অডিট লগ**: সব অ্যাকশন লগ করুন

---

## 🔧 ট্রাবলশুটিং

### সাধারণ সমস্যা ও সমাধান

#### ১. ইন্টিগ্রেশন সমস্যা
```python
# সমস্যা: কোর মডেল ফাউন্ড না
# সমাধান: প্রপার ইমপোর্ট চেক করুন
try:
    from api.security.models import SecurityLog
except ImportError:
    logger.error("Core SecurityLog model not found")
```

#### ২. সিগন্যাল কাজ করছে না
```python
# সমস্যা: সিগন্যাল হ্যান্ডলার কল হচ্ছে না
# সমাধান: সিগন্যাল কানেক্ট চেক করুন
from django.dispatch import Signal

# সিগন্যাল ডিফাইন আছে কিনা চেক করুন
if hasattr(SecurityLog, 'security_log_created'):
    print("Signal exists")
else:
    print("Signal not found")
```

#### ৩. ডাটাবেস মাইগ্রেশন
```python
# মাইগ্রেশন তৈরি
python manage.py makemigrations security --name=add_{{FEATURE_SLUG}}_extension

# মাইগ্রেশন অ্যাপ্লাই
python manage.py migrate security
```

### ডিবাগিং টুলস

#### এক্সটেনশন স্ট্যাটাস চেক
```python
# api/security/extensions/debug_tools.py

def check_extension_status(extension_name):
    """এক্সটেনশন স্ট্যাটাস চেক"""
    from ..registry import extension_registry
    
    extension = extension_registry.get(extension_name)
    if extension:
        return {
            'name': extension.name,
            'version': extension.version,
            'enabled': extension.enabled,
            'core_integrations': extension.core_integrations
        }
    else:
        return {'error': f'Extension {extension_name} not found'}
```

---

## 🧪 ফিচার ভেরিফিকেশন

### ১. ইউনিট টেস্টিং
```python
# api/security/extensions/advanced_threat_detection/tests/test_services.py

import unittest
from django.test import TestCase
from .services import AdvancedThreatDetectionService

class AdvancedThreatDetectionServiceTest(TestCase):
    def setUp(self):
        self.service = AdvancedThreatDetectionService()
    
    def test_analyze_security_log(self):
        """সিকিউরিটি লগ এনালাইসিস টেস্ট"""
        # টেস্ট ডেটা তৈরি
        log_data = self._create_test_security_log()
        
        # সার্ভিস কল
        result = self.service.analyze_security_log(log_data.id)
        
        # অ্যাসারশন
        self.assertIn('threat_detected', result)
        self.assertIsInstance(result['threat_detected'], bool)
```

### ২. ইন্টিগ্রেশন টেস্টিং
```python
# api/security/extensions/advanced_threat_detection/tests/test_integration.py

from django.test import TestCase
from django.test import Client
from api.security.models import SecurityLog

class ExtensionIntegrationTest(TestCase):
    def test_signal_integration(self):
        """সিগন্যাল ইন্টিগ্রেশন টেস্ট"""
        # SecurityLog তৈরি
        log = SecurityLog.objects.create(
            security_type='login_attempt',
            severity='high'
        )
        
        # এক্সটেনশন রেজাল্ট চেক
        self.assertTrue(
            log.threat_detections.exists()
        )
```

### ৩. পারফরম্যান্স টেস্টিং
```python
# api/security/extensions/advanced_threat_detection/tests/test_performance.py

import time
from django.test import TestCase
from .services import AdvancedThreatDetectionService

class PerformanceTest(TestCase):
    def test_batch_processing_performance(self):
        """ব্যাচ প্রসেসিং পারফরম্যান্স টেস্ট"""
        service = AdvancedThreatDetectionService()
        
        # ১০০টি লগ তৈরি
        logs = [self._create_test_security_log() for _ in range(100)]
        
        # ব্যাচ প্রসেসিং
        start_time = time.time()
        results = service.batch_analyze([log.id for log in logs])
        end_time = time.time()
        
        # পারফরম্যান্স অ্যাসারশন
        processing_time = end_time - start_time
        self.assertLess(processing_time, 5.0)  # ৫ সেকেন্ডের মধ্যে
```

---

## 📚 রেফারেন্স

### কোর কম্পোনেন্টস
- **Models**: `api.security.models`
- **Services**: `api.security.services`
- **Views**: `api.security.views`
- **Signals**: `api.security.signals`

### এক্সটেনশন রেজিস্ট্রি
- **Registry**: `api.security.extensions.registry`
- **Config**: `api.security.extensions.config`

### বেস্ট প্র্যাকটিস
- Django Extensions Documentation
- Plugin Architecture Patterns
- Dependency Injection Principles

---

## 🎯 সারাংশ

এই EXTENSION_GUIDE.md অনুসরণ করে আপনি:

✅ **কোর কোড অপরিবর্তিত রাখতে পারবেন**  
✅ **স্ট্যান্ডার্ডাইজড এক্সটেনশন তৈরি করতে পারবেন**  
✅ **প্রপার ইন্টিগ্রেশন নিশ্চিত করতে পারবেন**  
✅ **টেস্টেবল ও মেইনটেইনেবল কোড লিখতে পারবেন**

**"এক কাজের জন্য একটাই মালিক"** - এই নীতি মেনে কাজ করলে Security Module সবসময় স্থিতিশীল ও এক্সটেন্ডেবল থাকবে।

---

*গাইড লেখার সময় ব্যবহৃত সংস্করণ: v1.0.0*  
*আপডেট তারিখ: ২৫ এপ্রিল ২০২৬*
