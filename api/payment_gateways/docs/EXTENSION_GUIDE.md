# 🔧 EXTENSION GUIDE — payment_gateways
## "এক কাজের জন্য একটাই মালিক"
### Core code কখনো touch করতে হবে না

---

## 📋 সূচিপত্র (Table of Contents)

1. [Architecture Overview](#1-architecture-overview)
2. [নতুন Payment Gateway যোগ করা](#2-নতুন-payment-gateway-যোগ-করা)
3. [নতুন Offer Type যোগ করা](#3-নতুন-offer-type-যোগ-করা)
4. [নতুন Webhook Handler যোগ করা](#4-নতুন-webhook-handler-যোগ-করা)
5. [নতুন Background Job যোগ করা](#5-নতুন-background-job-যোগ-করা)
6. [নতুন API Endpoint যোগ করা](#6-নতুন-api-endpoint-যোগ-করা)
7. [নতুন Notification Template যোগ করা](#7-নতুন-notification-template-যোগ-করা)
8. [নতুন Fraud Rule যোগ করা](#8-নতুন-fraud-rule-যোগ-করা)
9. [নতুন Feature Flag যোগ করা](#9-নতুন-feature-flag-যোগ-করা)
10. [নতুন Publisher Metric যোগ করা](#10-নতুন-publisher-metric-যোগ-করা)
11. [নতুন Integration (External App) যোগ করা](#11-নতুন-integration-external-app-যোগ-করা)
12. [নতুন Report/Export যোগ করা](#12-নতুন-reportexport-যোগ-করা)
13. [নতুন SmartLink Rotation Mode যোগ করা](#13-নতুন-smartlink-rotation-mode-যোগ-করা)
14. [নতুন Payout Method যোগ করা](#14-নতুন-payout-method-যোগ-করা)
15. [Database Migration Rules](#15-database-migration-rules)
16. [Testing Checklist](#16-testing-checklist)
17. [Common Mistakes & Solutions](#17-common-mistakes--solutions)

---

## 1. Architecture Overview

```
payment_gateways/
├── services/          ← Gateway-specific business logic (1 file = 1 gateway)
├── viewsets/          ← API endpoints (1 file = 1 resource)
├── models/            ← Database models (grouped by domain)
├── tasks/             ← Celery background tasks
├── integration_system/← Cross-app integration (registry + event bus)
│   ├── integ_registry.py     ← Event handler registration
│   ├── integ_adapter.py      ← Auto-wires all integrations
│   ├── integrations.py       ← Concrete integration classes
│   └── ...
├── plugins.py         ← Plugin system (extend without modifying)
├── hooks.py           ← Pre/post hooks (extend without modifying)
├── registry.py        ← Service + webhook registries
├── feature_flags.py   ← Feature toggle system
└── docs/              ← This file
```

### Extension নীতি (The Golden Rule)

```
❌ Core file touch করবেন না:
   services/BkashService.py
   models/core.py
   viewsets/GatewayViewSet.py

✅ এগুলো দিয়ে extend করুন:
   plugins.py      → PaymentPlugin class
   hooks.py        → pre/post hooks
   registry.py     → register handlers
   feature_flags.py→ enable/disable
   integration_system/integ_registry.py → event handlers
```

---

## 2. নতুন Payment Gateway যোগ করা

### উদাহরণ: "Rocket" (Dutch-Bangla Bank) গেটওয়ে যোগ করা

#### Step 1: Service file তৈরি করুন

```python
# api/payment_gateways/services/RocketService.py
import requests
from decimal import Decimal
from django.conf import settings
from .abstracts import BaseGatewayService  # ← এটা আগে থেকেই আছে

class RocketService(BaseGatewayService):
    """
    Dutch-Bangla Bank Rocket mobile banking gateway.
    Extends BaseGatewayService — সব abstract methods implement করতে হবে।
    """
    gateway_name = 'rocket'

    def __init__(self):
        self.merchant_id  = getattr(settings, 'ROCKET_MERCHANT_ID', '')
        self.merchant_key = getattr(settings, 'ROCKET_MERCHANT_KEY', '')
        self.sandbox      = getattr(settings, 'ROCKET_SANDBOX', True)
        self.base_url     = ('https://sandbox.rocket.com.bd' if self.sandbox
                             else 'https://rocket.com.bd')

    def process_deposit(self, user, amount: Decimal, **kwargs) -> dict:
        """Initiate Rocket payment."""
        reference_id = kwargs.get('reference_id', '')
        try:
            resp = requests.post(f'{self.base_url}/api/initiate', json={
                'merchantId':   self.merchant_id,
                'amount':       str(amount),
                'reference':    reference_id,
                'callbackUrl':  f'https://yourdomain.com/api/payment/webhooks/rocket/',
            }, headers={'Authorization': f'Bearer {self.merchant_key}'}, timeout=10)
            data = resp.json()
            return {
                'success':      data.get('status') == 'success',
                'payment_url':  data.get('paymentUrl', ''),
                'payment_id':   data.get('paymentId', ''),
                'session_key':  data.get('paymentId', ''),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def verify_payment(self, session_id: str, **kwargs) -> dict:
        """Verify payment status."""
        try:
            resp = requests.get(f'{self.base_url}/api/verify/{session_id}',
                headers={'Authorization': f'Bearer {self.merchant_key}'}, timeout=10)
            data = resp.json()
            return {
                'status':       'completed' if data.get('trxStatus') == 'S' else 'pending',
                'gateway_ref':  data.get('trxId', ''),
                'amount':       Decimal(str(data.get('amount', 0))),
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def process_withdrawal(self, user, amount: Decimal, payment_method, **kwargs) -> dict:
        """Send payout to Rocket account."""
        phone = payment_method.account_number
        try:
            resp = requests.post(f'{self.base_url}/api/disbursement', json={
                'merchantId': self.merchant_id,
                'amount':     str(amount),
                'msisdn':     phone,
                'reference':  kwargs.get('reference_id', ''),
            }, headers={'Authorization': f'Bearer {self.merchant_key}'}, timeout=15)
            data = resp.json()
            return {'success': data.get('status') == 'success', 'gateway_ref': data.get('trxId', '')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def process_refund(self, transaction_id: str, amount: Decimal, **kwargs) -> dict:
        return {'success': False, 'error': 'Refund not supported for Rocket'}
```

#### Step 2: Registry-তে register করুন (core touch করতে হবে না)

```python
# api/payment_gateways/services/RocketService.py — এর নিচে add করুন
# অথবা যেকোনো app এর apps.py তে ready() method এ

from api.payment_gateways.registry import gateway_registry
from api.payment_gateways.services.RocketService import RocketService

# Auto-register হয়ে যাবে
gateway_registry.register('rocket', RocketService, {
    'display_name': 'Rocket (DBBL)',
    'color':        '#E31E24',
    'region':       'BD',
    'currency':     'BDT',
})
```

#### Step 3: DB record তৈরি করুন (fixture বা migration)

```python
# api/payment_gateways/migrations/XXXX_add_rocket_gateway.py
from django.db import migrations

def add_rocket(apps, schema_editor):
    PaymentGateway = apps.get_model('payment_gateways', 'PaymentGateway')
    PaymentGateway.objects.get_or_create(name='rocket', defaults={
        'display_name':               'Rocket (DBBL)',
        'status':                     'active',
        'region':                     'BD',
        'color_code':                 '#E31E24',
        'sort_order':                 6,
        'minimum_amount':             10,
        'maximum_amount':             50000,
        'transaction_fee_percentage': 1.8,
        'supports_deposit':           True,
        'supports_withdrawal':        True,
    })

class Migration(migrations.Migration):
    dependencies = [('payment_gateways', '0006_deposit_withdrawal_gateway_config')]
    operations   = [migrations.RunPython(add_rocket, migrations.RunPython.noop)]
```

#### Step 4: Settings-এ credentials add করুন

```python
# settings.py
ROCKET_MERCHANT_ID  = os.environ.get('ROCKET_MERCHANT_ID', '')
ROCKET_MERCHANT_KEY = os.environ.get('ROCKET_MERCHANT_KEY', '')
ROCKET_SANDBOX      = os.environ.get('ROCKET_SANDBOX', 'True') == 'True'
```

#### Step 5: Webhook URL register করুন

Rocket-এর dashboard-এ এই URL set করুন:
```
https://yourdomain.com/api/payment/webhooks/rocket/
```

Gateway webhook handler auto-dispatches করবে — কোনো extra code লাগবে না।

#### Step 6: choices.py তে add করুন

```python
# api/payment_gateways/choices.py এ নতুন entry:
BD_GATEWAYS = ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay', 'rocket']  # ← যোগ করুন
ALL_GATEWAYS = BD_GATEWAYS + GLOBAL_GATEWAYS
```

#### ✅ Done! Gateway is live. Test করুন:

```bash
python manage.py shell
>>> from api.payment_gateways.registry import gateway_registry
>>> svc = gateway_registry.get_instance('rocket')
>>> print(svc.gateway_name)  # → 'rocket'
```

---

## 3. নতুন Offer Type যোগ করা

### উদাহরণ: "CPL" (Cost Per Lead) offer type

```python
# api/payment_gateways/choices.py — add new type:
OFFER_TYPES = (
    ...existing...,
    ('cpl_email',    'CPL — Email Lead'),      # ← নতুন
    ('cpl_phone',    'CPL — Phone Lead'),      # ← নতুন
    ('cpl_form',     'CPL — Form Submission'), # ← নতুন
)

# api/payment_gateways/conversion_goals.py — এতে add করুন:
GOAL_TYPES['email_lead']  = 'cpl_email'
GOAL_TYPES['phone_lead']  = 'cpl_phone'
GOAL_TYPES['form_submit'] = 'cpl_form'
```

নতুন offer type-এর জন্য আলাদা migration লাগবে না — CharField max_length মধ্যে পড়ে।

---

## 4. নতুন Webhook Handler যোগ করা

### উদাহরণ: "Kochava" tracker webhook যোগ করা

```python
# api/payment_gateways/webhooks/handlers/KochavaHandler.py (নতুন file)
from api.payment_gateways.registry import webhook_registry
from api.payment_gateways.interactors import ConversionFlowInteractor

def handle_kochava_webhook(payload: dict, headers: dict) -> dict:
    """
    Kochava postback handler.
    Kochava sends: click_id, event_name, revenue, country
    """
    click_id   = payload.get('click_id', '')
    event      = payload.get('event_name', 'install')
    revenue    = payload.get('revenue', 0)
    country    = payload.get('country', '')

    if not click_id:
        return {'success': False, 'error': 'click_id missing'}

    result = ConversionFlowInteractor().process_postback(
        params={
            'click_id': click_id,
            'payout':   revenue,
            'status':   'approved',
            'sub1':     event,
            'country':  country,
        },
        ip=headers.get('X-Forwarded-For', ''),
    )
    return result

# Register কোথাও call করুন (apps.py ready() বা startup):
webhook_registry.register('kochava', handle_kochava_webhook)
```

**URL এখন auto-work করবে:**
```
https://yourdomain.com/api/payment/webhooks/kochava/
```

---

## 5. নতুন Background Job যোগ করা

```python
# api/payment_gateways/background_jobs.py তে শুধু নতুন task add করুন:

@shared_task(name='pg.custom.my_new_job')
def job_my_new_task():
    """আমার নতুন কাজ।"""
    # ... your logic ...
    return {'done': True}
```

**Celery Beat schedule-এ add করুন:**

```python
# settings.py বা celery.py তে:
from api.payment_gateways.celery_beat_config import BEAT_SCHEDULE
from datetime import timedelta

BEAT_SCHEDULE.update({
    'pg-my-new-job': {
        'task':     'pg.custom.my_new_job',
        'schedule': timedelta(hours=6),
    },
})
```

Core `celery_beat_config.py` touch করতে হয়নি।

---

## 6. নতুন API Endpoint যোগ করা

```python
# নতুন file: api/payment_gateways/viewsets/MyNewViewSet.py

from api.payment_gateways.viewset import PaymentBaseViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

class MyNewViewSet(PaymentBaseViewSet):
    """নতুন resource-এর ViewSet।"""
    queryset           = MyModel.objects.all()
    serializer_class   = MySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_custom_action(self, request):
        return self.success_response(data={'hello': 'world'})
```

**URLs-এ add করুন:**

```python
# api/payment_gateways/urls.py তে:
from api.payment_gateways.viewsets.MyNewViewSet import MyNewViewSet

router.register(r'my-resource', MyNewViewSet, basename='my-resource')
```

---

## 7. নতুন Notification Template যোগ করা

```python
# apps.py এর ready() method-এ অথবা startup code-এ:

from api.payment_gateways.registry import notification_registry

notification_registry.register(
    'payment_offer_cap_warning',
    subject='⚠️ Offer Cap Warning: {offer_name}',
    body=(
        'Your offer "{offer_name}" has used {pct_used}% of its {cap_type} cap.\n'
        'Consider increasing the limit in your dashboard.'
    ),
    channels=['email', 'in_app'],
)
```

**Use করুন:**

```python
from api.payment_gateways.registry import notification_registry
rendered = notification_registry.render('payment_offer_cap_warning', {
    'offer_name': 'Gaming App Install',
    'pct_used':   85,
    'cap_type':   'daily',
})
# → {'subject': '⚠️ Offer Cap Warning: Gaming App Install', 'body': '...', 'channels': [...]}
```

---

## 8. নতুন Fraud Rule যোগ করা

Plugin system দিয়ে নতুন fraud rule যোগ করুন:

```python
# api/payment_gateways/plugins.py তে নিচে add করুন:

class MyCustomFraudPlugin(PaymentPlugin):
    """আমার কাস্টম fraud detection rule।"""
    name        = 'custom_fraud_checker'
    version     = '1.0.0'
    description = 'Blocks transactions from VPN IPs in high-risk periods'

    def validate_deposit(self, user, amount, gateway) -> tuple:
        """
        Return: (is_valid: bool, errors: list[str])
        False return করলে transaction block হবে।
        """
        from api.payment_gateways.ip_intelligence import ip_intelligence
        from django.utils import timezone

        # Business hours check
        hour = timezone.localtime().hour
        if 2 <= hour <= 5:  # Block 2AM-5AM suspicious activity
            # Check if high-value
            if amount > 10000:
                return False, ['High-value transactions blocked during off-hours (2AM-5AM)']

        return True, []

    def on_deposit_completed(self, user, deposit):
        """Hook into deposit completion event."""
        if float(deposit.amount) > 50000:
            # Alert for large deposits
            import logging
            logging.getLogger(__name__).warning(
                f'Large deposit: user={user.id} amount={deposit.amount}'
            )

# Register — apps.py ready() তে বা যেকোনো startup file-এ:
from api.payment_gateways.plugins import register_plugin
register_plugin(MyCustomFraudPlugin())
```

---

## 9. নতুন Feature Flag যোগ করা

```python
# api/payment_gateways/feature_flags.py তে DEFAULT_FLAGS-এ add করুন:
DEFAULT_FLAGS = {
    ...existing...,
    'my_new_feature': False,  # ← নতুন flag — default off
}
```

**Use করুন:**

```python
from api.payment_gateways.feature_flags import feature_flags

# Check
if feature_flags.is_enabled('my_new_feature', user=request.user):
    do_new_thing()

# Enable for all
feature_flags.enable('my_new_feature')

# Enable for specific user only
from django.core.cache import cache
cache.set(f'ff_user:{user.id}:my_new_feature', True, 86400)

# View decorator
from api.payment_gateways.feature_flags import require_feature

@require_feature('my_new_feature')
def my_view(request):
    ...
```

---

## 10. নতুন Publisher Metric যোগ করা

```python
# api/payment_gateways/selectors.py তে PublisherSelector class-এ add করুন:

@staticmethod
def get_my_new_metric(publisher, days: int = 30) -> dict:
    """My new custom metric."""
    from api.payment_gateways.tracking.models import Click
    from django.utils import timezone
    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)
    # ... calculation logic ...
    return {'metric': value}

# api/payment_gateways/analytics.py তে get_publisher_analytics()-এ merge করুন:
def get_publisher_analytics(self, user, days=30):
    result = { ...existing... }
    result['my_metric'] = PublisherSelector.get_my_new_metric(user, days)
    return result
```

---

## 11. নতুন Integration (External App) যোগ করা

আপনার system-এ নতুন app যোগ হয়েছে? Integration system-এ connect করুন:

```python
# api/payment_gateways/integration_system/integrations.py তে নতুন class add করুন:

class MyNewAppIntegration:
    """My new app integration."""

    def on_deposit_completed(self, user, deposit, amount, **kwargs):
        """Deposit complete হলে my_new_app-কে notify করো।"""
        try:
            from api.my_new_app.services import MyService
            MyService().handle_payment(user=user, amount=float(amount))
        except ImportError:
            pass  # App not installed — silent fail
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'MyNewApp integration: {e}')

    def on_conversion_approved(self, conversion, publisher, payout, **kwargs):
        """Conversion approve হলে bonus award করো।"""
        try:
            from api.my_new_app.services import BonusService
            BonusService().award(user=publisher, amount=float(payout))
        except ImportError:
            pass

# api/payment_gateways/integration_system/integ_adapter.py তে setup_all()-এ add করুন:
def setup_all(self):
    ...existing setup calls...
    self._setup_my_new_app()  # ← add this line

def _setup_my_new_app(self):
    from .integrations import MyNewAppIntegration
    ni = MyNewAppIntegration()
    registry.register(IntegEvent.DEPOSIT_COMPLETED,     ni.on_deposit_completed,
                       module='api.my_new_app', priority=Priority.NORMAL, is_async=True)
    registry.register(IntegEvent.CONVERSION_APPROVED,   ni.on_conversion_approved,
                       module='api.my_new_app', priority=Priority.LOW, is_async=True)
```

---

## 12. নতুন Report/Export যোগ করা

```python
# api/payment_gateways/data_export.py তে DataExporter class-এ add করুন:

def export_my_custom_report(self, user=None, start_date=None,
                              end_date=None, fmt='csv') -> HttpResponse:
    """My custom report."""
    headers = ['Column 1', 'Column 2', 'Column 3']
    rows    = []

    # Query your data
    from api.payment_gateways.models.core import GatewayTransaction
    qs = GatewayTransaction.objects.all()
    if user: qs = qs.filter(user=user)

    for obj in qs[:5000]:
        rows.append([obj.reference_id, float(obj.amount), obj.status])

    filename = f'my_report_{timezone.now().strftime("%Y%m%d")}'
    return self._to_format(headers, rows, filename, fmt)

# API view যোগ করুন:
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_my_report(request):
    return exporter.export_my_custom_report(user=request.user, fmt=request.GET.get('format','csv'))

# urls.py তে:
path('export/my-report/', export_my_report, name='export-my-report'),
```

---

## 13. নতুন SmartLink Rotation Mode যোগ করা

```python
# api/payment_gateways/offer_rotator.py তে rotate() method-এ add করুন:

def rotate(self, smart_link, click_data=None):
    mode = smart_link.rotation_mode
    # ...existing code...

    # নতুন mode:
    if mode == 'my_custom_mode':
        return self._my_custom_rotation(smart_link, candidates, click_data)

    return random.choice(candidates)

def _my_custom_rotation(self, smart_link, candidates, click_data):
    """My custom rotation algorithm."""
    # Example: Return offer with most remaining cap
    from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
    engine = ConversionCapEngine()
    best   = max(
        candidates,
        key=lambda o: (engine.get_cap_status(o).get('daily_remaining') or 999)
    )
    return best

# choices.py তে mode add করুন:
SMARTLINK_ROTATION_MODES = (
    ...existing...,
    ('my_custom_mode', 'My Custom Rotation'),
)
```

---

## 14. নতুন Payout Method যোগ করা

### উদাহরণ: "M-Pesa" (Africa) যোগ করা

```python
# Step 1: Service file
# api/payment_gateways/services/MPesaService.py
from .abstracts import BaseGatewayService
import requests
from decimal import Decimal
from django.conf import settings

class MPesaService(BaseGatewayService):
    gateway_name = 'mpesa'
    def process_deposit(self, user, amount: Decimal, **kwargs) -> dict:
        ...
    def process_withdrawal(self, user, amount: Decimal, payment_method, **kwargs) -> dict:
        ...
    def verify_payment(self, session_id: str, **kwargs) -> dict:
        ...
    def process_refund(self, transaction_id: str, amount: Decimal, **kwargs) -> dict:
        return {'success': False, 'error': 'Refund not supported'}

# Step 2: Register
from api.payment_gateways.registry import gateway_registry
gateway_registry.register('mpesa', MPesaService, {'display_name': 'M-Pesa', 'region': 'AF', 'currency': 'KES'})

# Step 3: choices.py
SUPPORTED_GATEWAYS = [...existing..., 'mpesa']
GLOBAL_GATEWAYS    = [...existing..., 'mpesa']

# Step 4: validator.py তে account format add করুন:
# ACCOUNT_PATTERNS['mpesa'] = r'^\+254[17]\d{8}$'  # Kenya phone format

# Step 5: GATEWAY_LIMITS এ add করুন:
# GATEWAY_LIMITS['mpesa'] = {'min': Decimal('10'), 'max': Decimal('150000')}
```

---

## 15. Database Migration Rules

### নতুন Model Field যোগ করার rules:

```python
# ✅ DO: Always add with null=True or default
class MyModel(models.Model):
    new_field = models.CharField(max_length=100, blank=True, default='')  # ✅
    new_int   = models.IntegerField(default=0)                            # ✅
    new_fk    = models.ForeignKey(Other, null=True, blank=True,           # ✅
                                   on_delete=models.SET_NULL)

# ❌ DON'T: Add NOT NULL field without default (breaks existing data)
class MyModel(models.Model):
    new_field = models.CharField(max_length=100)  # ❌ — will break migration!
```

### Migration তৈরি করুন:

```bash
# নতুন sub-app এর জন্য:
python manage.py makemigrations payment_gateways_myapp

# Root app এর জন্য:
python manage.py makemigrations payment_gateways

# Apply করুন:
python manage.py migrate payment_gateways
python manage.py migrate payment_gateways_myapp
```

### Migration naming convention:

```
0001_initial.py
0002_add_completed_at.py
0003_add_gateway_config.py
0004_add_deposit_request.py
0005_add_completed_at_fix.py
0006_deposit_withdrawal_gateway_config.py
0007_add_rocket_gateway.py          ← নতুন gateway
0008_add_mpesa_gateway.py           ← আরেকটা gateway
```

---

## 16. Testing Checklist

নতুন feature যোগ করার পর এই tests run করুন:

```bash
# 1. নতুন service test
python manage.py shell -c "
from api.payment_gateways.registry import gateway_registry
svc = gateway_registry.get_instance('rocket')  # নতুন gateway
print('✅ Service registered:', svc.gateway_name)
"

# 2. Integration test
python manage.py shell -c "
from api.payment_gateways.integration_system.integ_registry import registry
events = registry.list_events()
print('✅ Registered events:', len(events))
"

# 3. Feature flag test
python manage.py shell -c "
from api.payment_gateways.feature_flags import feature_flags
flags = feature_flags.get_all_flags()
print('✅ Feature flags:', len(flags))
"

# 4. Full test suite
python manage.py test api.payment_gateways --verbosity=2

# 5. Syntax check
python -m py_compile api/payment_gateways/services/RocketService.py
echo '✅ Syntax OK'

# 6. Migration check
python manage.py migrate --check
echo '✅ No pending migrations'
```

---

## 17. Common Mistakes & Solutions

### ❌ Mistake 1: Core file-এ সরাসরি code লেখা

```python
# ❌ WRONG:
# api/payment_gateways/services/DepositService.py তে সরাসরি add:
if gateway == 'rocket':
    rocket_specific_code()

# ✅ CORRECT:
# registry.py দিয়ে:
gateway_registry.register('rocket', RocketService)
# DepositService automatically uses registry — কোনো change দরকার নেই
```

### ❌ Mistake 2: Signal receiver duplicate

```python
# ❌ WRONG: Same receiver twice (causes double execution):
@receiver(post_save, sender=DepositRequest)
def handler1(sender, instance, **kwargs): ...

@receiver(post_save, sender=DepositRequest)
def handler2(sender, instance, **kwargs): ...  # Runs twice!

# ✅ CORRECT: IntegrationRegistry দিয়ে:
registry.register(IntegEvent.DEPOSIT_COMPLETED, handler1, module='module1')
registry.register(IntegEvent.DEPOSIT_COMPLETED, handler2, module='module2')
# Registry ensures correct execution order and prevents duplicates
```

### ❌ Mistake 3: Circular import

```python
# ❌ WRONG: Module level import in service:
from api.payment_gateways.models.core import GatewayTransaction

class BkashService:
    def process_deposit(self, ...):
        txn = GatewayTransaction.objects.create(...)  # Circular!

# ✅ CORRECT: Import inside method:
class BkashService:
    def process_deposit(self, ...):
        from api.payment_gateways.models.core import GatewayTransaction  # ← Inside method
        txn = GatewayTransaction.objects.create(...)
```

### ❌ Mistake 4: Missing apps.py label

```python
# ❌ WRONG: New sub-app without label
class MyAppConfig(AppConfig):
    name = 'api.payment_gateways.myapp'
    # No label — conflicts with other apps!

# ✅ CORRECT:
class MyAppConfig(AppConfig):
    name    = 'api.payment_gateways.myapp'
    label   = 'payment_gateways_myapp'  # ← Unique label
    verbose_name = 'My App'
```

### ❌ Mistake 5: Missing default for new DB field

```python
# ❌ WRONG:
amount = models.DecimalField(max_digits=12, decimal_places=2)

# ✅ CORRECT:
amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
# Or:
amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
```

### ❌ Mistake 6: Gateway not in INSTALLED_APPS

```python
# নতুন sub-app তৈরি করলে settings.py তে add করতে হবে:

# settings.py:
INSTALLED_APPS += [
    'api.payment_gateways.myapp',  # ← এটা add না করলে migration হবে না!
]
```

---

## 🚀 Quick Reference — "কোথায় কী আছে"

| আমি কী করতে চাই | কোন file edit করব |
|------------------|-------------------|
| নতুন gateway যোগ | `services/MyGateway.py` (নতুন file) + `registry.py` register |
| নতুন API endpoint | `viewsets/MyViewSet.py` (নতুন file) + `urls.py` |
| নতুন background job | `background_jobs.py` এ `@shared_task` |
| নতুন fraud rule | `plugins.py` এ `PaymentPlugin` subclass |
| নতুন notification | `registry.py` এ `notification_registry.register()` |
| নতুন event handler | `integration_system/integrations.py` + `integ_adapter.py` |
| নতুন webhook handler | `registry.py` এ `webhook_registry.register()` |
| নতুন feature flag | `feature_flags.py` এ `DEFAULT_FLAGS` dict |
| নতুন export format | `data_export.py` এ `DataExporter` class |
| নতুন payout rule | `payout_rules.py` এ `PayoutRulesEngine` |
| নতুন analytics metric | `selectors.py` + `analytics.py` |
| নতুন caching strategy | `caching.py` এ `PaymentCache` class |
| নতুন compliance rule | `compliance.py` এ `ComplianceEngine` |
| নতুন sanctions country | `sanctions.py` এ lists |
| নতুন rotation mode | `offer_rotator.py` এ `rotate()` method |
| নতুন SmartLink mode | `smartlink/ABTestEngine.py` |
| নতুন cap type | `offers/ConversionCapEngine.py` |

---

## 📞 Support

যদি কোনো integration কাজ না করে:

1. `python manage.py shell` → `from api.payment_gateways.registry import gateway_registry; print(gateway_registry.list_gateways())`
2. Check `INSTALLED_APPS` — নতুন sub-app আছে?
3. Check `apps.py` — unique `label` আছে?
4. Check migrations — `python manage.py migrate --check`
5. Check logs: `grep "pg_" /var/log/django/app.log`

---

*এই guide follow করলে **core payment_gateways code কখনো touch করতে হবে না।***
*সব extension points ready আছে — শুধু নিজের code লিখুন।* ✅
