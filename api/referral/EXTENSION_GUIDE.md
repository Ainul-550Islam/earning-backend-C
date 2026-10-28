# EXTENSION GUIDE — api/referral/
## নতুন Feature যোগ করার সম্পূর্ণ নির্দেশিকা

> **"এক কাজের জন্য একটাই মালিক — core referral code কখনো touch করতে হবে না।"**

---

## ৮টি Extension Point — Quick Reference

| স্তর | File | কাজ |
|---|---|---|
| 1. Feature Flag | `feature_flags.py` | Admin থেকে ON/OFF — deploy ছাড়া |
| 2. Model | `models/advanced.py` | Database table তৈরি |
| 3. Service | `services/XxxService.py` | Business logic |
| 4. Plugin | `plugins.py` | Existing event এ hook করো |
| 5. Hook | `hooks.py` | Custom event listener |
| 6. Signal | `signals_cap.py` | Django signal fire করো |
| 7. ViewSet + URL | `viewset_cap.py` + `urls.py` | REST API endpoint |
| 8. Celery Task | `tasks_cap.py` | Background / scheduled job |

> **নিয়ম:** নতুন feature = নতুন file। পুরনো file এ শুধু শেষে ১-২ লাইন যোগ করো।

---

## Extension Point 1: Feature Flag

নতুন feature সবসময় Flag এর পেছনে রাখো — production এ safe থাকে।

### feature_flags.py তে যোগ করো

```python
# ── Step 1: Constant define করো ──────────────────────────────
FLAG_SPIN_WHEEL   = 'referral.spin_wheel'
FLAG_NPS_TRACKING = 'referral.nps_tracking'

# ── Step 2: Default value set করো ────────────────────────────
DEFAULTS: Dict[str, bool] = {
    # ... existing flags ...
    FLAG_SPIN_WHEEL:   False,   # নতুন feature সবসময় False দিয়ে শুরু
    FLAG_NPS_TRACKING: False,
}
```

### ব্যবহার — Service বা View এ

```python
from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL

class SpinWheelService:
    @staticmethod
    def spin(user):
        if not FeatureFlags.is_enabled(FLAG_SPIN_WHEEL):
            return {'error': 'Spin wheel is currently disabled'}
        # ... feature logic ...
```

### Admin থেকে ON/OFF

```python
from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL

FeatureFlags.set(FLAG_SPIN_WHEEL, True)    # ON
FeatureFlags.set(FLAG_SPIN_WHEEL, False)   # OFF
print(FeatureFlags.get_all())              # সব flag দেখো
```

### Decorator ব্যবহার (optional)

```python
from api.referral.feature_flags import flag_required, FLAG_SPIN_WHEEL

@flag_required(FLAG_SPIN_WHEEL, fallback={'error': 'disabled'})
def generate_spin(user):
    return SpinWheelService.spin(user)
```

---

## Extension Point 2: Model (Database)

নতুন model সবসময় `models/advanced.py` এর **শেষে** যোগ করো।

### models/advanced.py এর শেষে add করো

```python
# ── Spin Wheel Entry ──────────────────────────────────────────────────────
class SpinWheelEntry(models.Model):
    """
    One spin attempt per successful referral.
    User gets to spin after each new referral.
    """
    PRIZE_TYPE = [
        ('cash',    'Cash Reward'),
        ('bonus',   'Commission Bonus'),
        ('nothing', 'No Prize'),
    ]
    tenant       = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referral_spinentry_tenant',
    )
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='spin_wheel_entries',
    )
    referral     = models.ForeignKey(
        'Referral', on_delete=models.CASCADE,
        related_name='spin_entries', null=True, blank=True,
    )
    is_used      = models.BooleanField(default=False)
    prize_type   = models.CharField(max_length=10, choices=PRIZE_TYPE, blank=True)
    prize_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    spun_at      = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering  = ['-created_at']

    def __str__(self):
        return f"Spin({self.user.username}: {self.prize_type} {self.prize_amount})"
```

### models/\_\_init\_\_.py তে export যোগ করো

```python
from .advanced import (
    # ... existing imports ...
    SpinWheelEntry,   # নতুন
)

__all__ = [
    # ... existing ...
    'SpinWheelEntry',  # নতুন
]
```

### Migration তৈরি ও apply করো

```bash
python manage.py makemigrations referral
python manage.py migrate referral
```

> **নিয়ম:** `related_name` সবসময় `"referral_modelname_tenant"` pattern এ লেখো — conflict এড়ানোর জন্য।

---

## Extension Point 3: Service

নতুন service সবসময় **নতুন file** এ: `services/SpinWheelService.py`

```python
# api/referral/services/SpinWheelService.py
import random
import logging
from decimal import Decimal
from django.utils import timezone
from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL

logger = logging.getLogger(__name__)

PRIZES = [
    {'type': 'cash',    'amount': Decimal('50'),  'weight': 1},
    {'type': 'cash',    'amount': Decimal('20'),  'weight': 3},
    {'type': 'cash',    'amount': Decimal('10'),  'weight': 5},
    {'type': 'bonus',   'amount': Decimal('0'),   'weight': 4},
    {'type': 'nothing', 'amount': Decimal('0'),   'weight': 10},
]

class SpinWheelService:

    @staticmethod
    def award_ticket(referrer, referral) -> bool:
        """নতুন referral হলে spin ticket দাও। Plugin থেকে call হয়।"""
        if not FeatureFlags.is_enabled(FLAG_SPIN_WHEEL):
            return False
        from api.referral.models import SpinWheelEntry
        SpinWheelEntry.objects.create(user=referrer, referral=referral, is_used=False)
        logger.info(f'[SpinWheel] Ticket awarded to {referrer.username}')
        return True

    @staticmethod
    def spin(user) -> dict:
        """User spin করে prize পায়। ViewSet থেকে call হয়।"""
        if not FeatureFlags.is_enabled(FLAG_SPIN_WHEEL):
            return {'success': False, 'reason': 'feature_disabled'}

        from api.referral.models import SpinWheelEntry
        entry = SpinWheelEntry.objects.filter(user=user, is_used=False).first()
        if not entry:
            return {'success': False, 'reason': 'no_tickets_available'}

        weights = [p['weight'] for p in PRIZES]
        prize   = random.choices(PRIZES, weights=weights, k=1)[0]

        entry.is_used      = True
        entry.prize_type   = prize['type']
        entry.prize_amount = prize['amount']
        entry.spun_at      = timezone.now()
        entry.save()

        if prize['type'] == 'cash' and prize['amount'] > 0:
            from api.referral.INTEGRATION_SYSTEM.integ_adapter import WalletAdapter
            WalletAdapter.credit_bonus(
                user=user, amount=prize['amount'], description='Spin wheel prize'
            )

        return {
            'success':      True,
            'prize_type':   prize['type'],
            'prize_amount': float(prize['amount']),
        }

    @staticmethod
    def get_available_spins(user) -> int:
        from api.referral.models import SpinWheelEntry
        return SpinWheelEntry.objects.filter(user=user, is_used=False).count()
```

### services/\_\_init\_\_.py তে শেষে add করো

```python
from .SpinWheelService import SpinWheelService
```

---

## Extension Point 4: Plugin

Plugin দিয়ে existing referral events এ hook করো — existing code না বদলেই।

### plugins.py তে নতুন Plugin class যোগ করো

```python
# plugins.py — existing class গুলোর পরে add করো:

class SpinWheelPlugin(ReferralPlugin):
    """নতুন referral হলে spin ticket award করে।"""
    name    = 'spin_wheel'
    version = '1.0.0'

    def on_referral_created(self, referrer, referred_user, referral, **kwargs) -> None:
        try:
            from api.referral.services.SpinWheelService import SpinWheelService
            SpinWheelService.award_ticket(referrer=referrer, referral=referral)
        except Exception as e:
            logger.debug(f'[Plugin:spin_wheel] failed: {e}')

    def on_milestone_reached(self, user, milestone_value, bonus, **kwargs) -> None:
        """Milestone এ extra spin ticket দাও।"""
        try:
            from api.referral.services.SpinWheelService import SpinWheelService
            SpinWheelService.award_ticket(referrer=user, referral=None)
        except Exception as e:
            logger.debug(f'[Plugin:spin_wheel] milestone failed: {e}')
```

### setup_default_plugins() তে register করো

```python
def setup_default_plugins() -> None:
    PluginRegistry.register(DjoyaltyPlugin())
    PluginRegistry.register(AnalyticsPlugin())
    PluginRegistry.register(AuditPlugin())
    PluginRegistry.register(SpinWheelPlugin())  # ← নতুন
```

**Available plugin events:**
- `on_referral_created(referrer, referred_user, referral)`
- `on_commission_paid(user, amount, level, from_user)`
- `on_milestone_reached(user, milestone_value, bonus)`
- `on_fraud_detected(referral, fraud_score)`
- `on_signup(new_user, referral_code)`

---

## Extension Point 5: Hook

Hook দিয়ে custom event তৈরি করো এবং অন্য module এ subscribe করো।

### hooks.py তে নতুন method যোগ করো

```python
# hooks.py — ReferralHooks class এর শেষে add করো:

@classmethod
def on_spin_wheel_won(cls, user, prize_amount, prize_type, **kwargs) -> None:
    """Spin wheel এ prize জেতার পরে fire হয়।"""
    cls.fire('spin_wheel_won', user=user,
             prize_amount=prize_amount, prize_type=prize_type, **kwargs)
```

### অন্য module থেকে subscribe করো

```python
from api.referral.hooks import ReferralHooks

def send_spin_win_notification(user, prize_amount, **kwargs):
    from api.referral.notifications_push import ReferralPushNotificationService
    ReferralPushNotificationService.send(
        user=user,
        template_name='spin_wheel_won',
        data={'amount': prize_amount},
    )

ReferralHooks.register('spin_wheel_won', send_spin_win_notification)
```

---

## Extension Point 6: Signal

Django Signal ব্যবহার করো যখন DB save/delete এ automatically কিছু করতে চাও।

### signals_cap.py তে যোগ করো

```python
# signals_cap.py এর শেষে add করো:

spin_wheel_prize_won = Signal()
# args: sender, user, prize_type, prize_amount

@receiver(post_save, sender='referral.SpinWheelEntry')
def on_spin_wheel_entry_saved(sender, instance, created, **kwargs):
    """SpinWheelEntry update হলে (spin হলে) fire করো।"""
    if not instance.is_used or not instance.prize_type:
        return
    if instance.prize_type == 'nothing':
        return

    def _fire():
        spin_wheel_prize_won.send(
            sender=sender,
            user=instance.user,
            prize_type=instance.prize_type,
            prize_amount=float(instance.prize_amount),
        )

    from django.db import transaction
    transaction.on_commit(_fire)
```

> **নিয়ম:** সবসময় `transaction.on_commit()` ব্যবহার করো — DB commit এর পরেই signal fire হবে।

---

## Extension Point 7: ViewSet + URL

### viewset_cap.py তে নতুন View class যোগ করো

```python
# viewset_cap.py — existing views এর পরে add করো:

class SpinWheelView(APIView):
    """
    GET  /referral/spin/  → available spins count
    POST /referral/spin/  → spin করো
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [ReferralUserThrottle]

    def get(self, request):
        from api.referral.services.SpinWheelService import SpinWheelService
        count = SpinWheelService.get_available_spins(request.user)
        return Response({
            'available_spins': count,
            'feature_enabled': FeatureFlags.is_enabled(FLAG_SPIN_WHEEL),
        })

    def post(self, request):
        from api.referral.services.SpinWheelService import SpinWheelService
        result = SpinWheelService.spin(request.user)
        if not result['success']:
            return Response(result, status=400)
        return Response(result)
```

### urls.py তে একটি line যোগ করো

```python
from api.referral.viewset_cap import (
    # ... existing imports ...
    SpinWheelView,   # নতুন
)

urlpatterns = [
    # ... existing patterns ...
    path('spin/', SpinWheelView.as_view(), name='spin-wheel'),  # নতুন
]
```

---

## Extension Point 8: Celery Task

### tasks_cap.py তে নতুন task যোগ করো

```python
# tasks_cap.py — existing tasks এর পরে add করো:

@shared_task(name='referral.expire_unused_spin_tickets')
def expire_unused_spin_tickets() -> dict:
    """৩০ দিনের বেশি পুরনো unused spin ticket expire করো।"""
    from django.utils import timezone
    from datetime import timedelta
    from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL

    if not FeatureFlags.is_enabled(FLAG_SPIN_WHEEL):
        return {'skipped': True, 'reason': 'feature_disabled'}

    cutoff  = timezone.now() - timedelta(days=30)
    from api.referral.models import SpinWheelEntry
    expired = SpinWheelEntry.objects.filter(is_used=False, created_at__lt=cutoff).delete()
    return {'expired': expired[0]}
```

### celery_beat_config.py তে schedule যোগ করো

```python
# REFERRAL_BEAT_CONFIG dict এ add করো:
'referral-expire-spin-tickets': {
    'task':     'referral.expire_unused_spin_tickets',
    'schedule': crontab(hour=4, minute=30),  # Daily 4:30 AM
    'options':  {'queue': 'referral_low'},
},
```

---

## সম্পূর্ণ উদাহরণ — Spin Wheel Feature Checklist

নতুন Spin Wheel feature add করার সম্পূর্ণ step-by-step:

| # | কী করতে হবে |
|---|---|
| 1 | `feature_flags.py` তে `FLAG_SPIN_WHEEL` যোগ করো, `DEFAULTS` এ `False` |
| 2 | `models/advanced.py` এর শেষে `SpinWheelEntry` class যোগ করো |
| 3 | `models/__init__.py` তে `SpinWheelEntry` import করো |
| 4 | `python manage.py makemigrations referral && migrate` |
| 5 | `services/SpinWheelService.py` নতুন file তৈরি করো |
| 6 | `services/__init__.py` তে import যোগ করো |
| 7 | `plugins.py` তে `SpinWheelPlugin` class যোগ করো |
| 8 | `plugins.py` এর `setup_default_plugins()` তে register করো |
| 9 | `hooks.py` তে `on_spin_wheel_won()` method যোগ করো |
| 10 | `signals_cap.py` তে `spin_wheel_prize_won` signal যোগ করো |
| 11 | `viewset_cap.py` তে `SpinWheelView` class যোগ করো |
| 12 | `urls.py` তে `path('spin/', ...)` যোগ করো |
| 13 | `tasks_cap.py` তে `expire_unused_spin_tickets` task যোগ করো |
| 14 | `celery_beat_config.py` তে schedule যোগ করো |
| 15 | `tests/test_services.py` তে test case যোগ করো |
| 16 | `FeatureFlags.set(FLAG_SPIN_WHEEL, True)` করে test করো |

> **মোট পরিবর্তন:** ১টি নতুন service file + ১টি নতুন migration file। বাকি সব existing file এ মাত্র কয়েক লাইন addition। **কোনো existing logic ভাঙেনি।**

---

## Test করার পদ্ধতি

```python
# tests/test_services.py এর শেষে add করো:

class TestSpinWheelService(TestCase):

    def setUp(self):
        from api.referral.models import ReferralSettings
        ReferralSettings.objects.create(is_active=True)
        self.user = User.objects.create_user(username='spin_user', password='pass')

    def test_spin_disabled_by_default(self):
        from api.referral.services.SpinWheelService import SpinWheelService
        result = SpinWheelService.spin(self.user)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'feature_disabled')

    def test_spin_no_tickets(self):
        from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL
        FeatureFlags.set(FLAG_SPIN_WHEEL, True)
        from api.referral.services.SpinWheelService import SpinWheelService
        result = SpinWheelService.spin(self.user)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'no_tickets_available')
        FeatureFlags.set(FLAG_SPIN_WHEEL, False)

    def test_award_ticket_success(self):
        from api.referral.feature_flags import FeatureFlags, FLAG_SPIN_WHEEL
        FeatureFlags.set(FLAG_SPIN_WHEEL, True)
        from api.referral.models import SpinWheelEntry
        from api.referral.services.SpinWheelService import SpinWheelService
        SpinWheelService.award_ticket(referrer=self.user, referral=None)
        self.assertEqual(SpinWheelEntry.objects.filter(user=self.user).count(), 1)
        FeatureFlags.set(FLAG_SPIN_WHEEL, False)
```

```bash
# Test চালাও:
python manage.py test api.referral.tests.test_services.TestSpinWheelService
python manage.py test api.referral.tests --verbosity=2
```

---

## Deployment Checklist

| চেক | বিস্তারিত |
|---|---|
| Migration আছে? | `python manage.py showmigrations referral` |
| Test pass? | `python manage.py test api.referral.tests` |
| Flag default False? | `DEFAULTS` এ `False` — production safe |
| Syntax error নেই? | `python -m py_compile api/referral/*.py` |
| Migration apply? | `python manage.py migrate referral` — production এ |
| Celery restart? | নতুন task আছে? Worker restart করো |
| Feature test করেছ? | `FeatureFlags.set(FLAG_NEW, True)` করে manually test |
| Flag বন্ধ রাখো | Stable হওয়ার পর ON করো |

> ⚠️ **Deploy করার পর feature সাথে সাথে ON করো না।** ১-২ দিন monitor করো, তারপর ON করো।

---

## কোন Extension Point কখন ব্যবহার করবে

| পরিস্থিতি | Extension |
|---|---|
| নতুন feature safe রাখতে চাই | Feature Flag → default `False` |
| নতুন DB table দরকার | Model → `models/advanced.py` |
| Business logic আলাদা রাখতে চাই | Service → `services/NewService.py` |
| Referral create হলে কিছু করতে চাই | Plugin → `on_referral_created()` |
| Commission pay হলে কিছু করতে চাই | Plugin → `on_commission_paid()` |
| Custom event তৈরি করতে চাই | Hook → `hooks.py` এ new method |
| DB save/delete এ react করতে চাই | Signal → `signals_cap.py` এ `@receiver` |
| REST API endpoint দরকার | ViewSet → `viewset_cap.py` + `urls.py` |
| Background job দরকার | Celery Task → `tasks_cap.py` |
| Scheduled job দরকার | Celery Task + `celery_beat_config.py` |
| অন্য module কে notify করতে চাই | Event Bus → `events.py` তে `publish()` |
| Cache clear করতে চাই | Receiver → `receivers.py` তে signal handler |
| Admin panel এ দেখাতে চাই | Admin → `admin.py` তে `register()` |

---

## সারসংক্ষেপ

```
নতুন feature add করার golden rule:

  1. feature_flags.py   → FLAG_XXX = False (সবসময় প্রথমে)
  2. models/advanced.py → নতুন model class (যদি দরকার হয়)
  3. services/NewService.py → নতুন file (business logic)
  4. plugins.py         → Plugin class (existing event এ hook)
  5. viewset_cap.py     → View class (API endpoint)
  6. urls.py            → একটি path() line
  7. tasks_cap.py       → Task (background job, যদি দরকার)
  8. tests/             → Test case

  কোনো existing core file MODIFY করো না।
  শুধু APPEND করো।
```

---

*এই guide api/referral/ এর অংশ — যেকোনো সময় reference হিসেবে ব্যবহার করো।*
