# 🏗️ SUPPORT SYSTEM — EXTENSION GUIDE
## "এক কাজের জন্য একটাই মালিক"
> এই guide অনুসরণ করলে **core support code কখনো touch করতে হবে না।**
> শুধু নতুন file তৈরি করো — বাকি সব auto-connect হয়।

---

## 📐 আর্কিটেকচার Overview

```
┌─────────────────────────────────────────────────────────┐
│                   SUPPORT SYSTEM                        │
│                                                         │
│  Views → Use Cases → Services → Repositories → Models  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │           EXTENSION POINTS                      │   │
│  │                                                 │   │
│  │  1. hooks.py        → ticket lifecycle          │   │
│  │  2. event_bus.py    → pub/sub events            │   │
│  │  3. registry.py     → plugins                   │   │
│  │  4. feature_flags.py→ on/off                    │   │
│  │  5. integrations/   → other apps                │   │
│  │  6. signals_*.py    → Django signals            │   │
│  │  7. tasks.py        → Celery async              │   │
│  │  8. middleware.py   → HTTP layer                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 আর্কিটেকচার নিয়ম (লঙ্ঘন করলে merge হবে না)

| ✅ করো | ❌ করো না |
|--------|----------|
| `wallet.credit(amount)` — wallet-এর method call | `wallet.balance += amount` — field সরাসরি change |
| নতুন file তৈরি করো | `services.py`, `models.py`, `views.py` modify করো |
| `event_bus.publish(event, ...)` | অন্য app-এর signal directly handle |
| `hooks.py`-তে hook register করো | `services.py`-তে নতুন logic যোগ করো |
| `feature_flags.py`-তে flag add করো | hardcode করো |

---

## 🚀 USE CASE 1: নতুন Ticket Hook যোগ করা

### কোনো core file touch করতে হবে না।

**ধরো: Ticket create হলে Slack-এ notify করতে চাই।**

```python
# api/support/integrations/project_specific/slack_ticket_hook.py  ← নতুন file

import logging
logger = logging.getLogger(__name__)

def on_ticket_created_slack(ticket) -> None:
    """
    Ticket তৈরি হলে Slack-এ notify করে।
    hooks.py-তে register করে activate হয়।
    """
    try:
        from support.webhooks import webhook_sender
        from support.models import SupportSettings
        settings_obj, _ = SupportSettings.objects.get_or_create(id=1)
        if settings_obj.slack_webhook_url:
            webhook_sender.send(
                url   = settings_obj.slack_webhook_url,
                event = 'ticket.created',
                payload = {
                    'ticket_id': ticket.ticket_id,
                    'category':  ticket.category,
                    'priority':  ticket.priority,
                    'user':      ticket.user.username,
                    'text':      f'New {ticket.priority} ticket: {ticket.subject}',
                }
            )
    except Exception as e:
        logger.debug(f'slack_ticket_hook: {e}')
```

**apps.py-তে register করো (শুধু apps.py-র `ready()` section):**

```python
# apps.py ready() এ যোগ করো:
try:
    from api.support.hooks import ticket_hooks
    from api.support.integrations.project_specific.slack_ticket_hook import on_ticket_created_slack
    # post_create hook-এ register
    original_post_create = ticket_hooks.__class__.post_create.__func__
    
    @staticmethod
    def enhanced_post_create(ticket):
        original_post_create(ticket)       # original hooks চলবে
        on_ticket_created_slack(ticket)    # নতুন hook যোগ হবে
    
    ticket_hooks.__class__.post_create = enhanced_post_create
except Exception as e:
    logger.debug(f'Slack hook: {e}')
```

**অথবা আরো সহজে — event_bus দিয়ে:**

```python
# api/support/integrations/project_specific/slack_ticket_hook.py

from support.integrations.event_bus import event_bus

@event_bus.on('ticket.created')
def handle_ticket_created_for_slack(event_type, ticket=None, **kwargs):
    """Event bus subscribe — apps.py ready() ছাড়াই কাজ করে।"""
    if not ticket:
        return
    try:
        from support.webhooks import webhook_sender
        # ... slack notify code
    except Exception:
        pass
```

```python
# apps.py ready()-তে শুধু import করলেই হয়:
try:
    from api.support.integrations.project_specific import slack_ticket_hook  # noqa
except Exception as e:
    logger.debug(f'Slack hook load: {e}')
```

---

## 🔌 USE CASE 2: নতুন Integration Adapter যোগ করা

**ধরো: `subscription` app থেকে user plan check করতে চাই।**

```python
# api/support/integrations/project_specific/subscription_adapter.py  ← নতুন file

import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)


class SubscriptionAdapter:
    """
    Support → subscription app integration.
    শুধু READ করে। কোনো write নেই।
    """
    
    def get_plan(self, user) -> dict:
        """User-এর subscription plan পড়ে।"""
        cache_key = f'support:subscription:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            from django.apps import apps
            UserSub = apps.get_model('subscription', 'UserSubscription')
            sub = UserSub.objects.filter(
                user=user, status='active'
            ).select_related('plan').first()
            
            if sub and sub.plan:
                result = {
                    'has_plan':   True,
                    'plan_name':  sub.plan.name,
                    'plan_tier':  getattr(sub.plan, 'tier', 'standard'),
                    'expires_at': sub.expires_at.isoformat() if hasattr(sub, 'expires_at') else None,
                }
            else:
                result = {'has_plan': False, 'plan_name': 'free', 'plan_tier': 'free'}
            
            cache.set(cache_key, result, timeout=300)
            return result
        
        except Exception as e:
            logger.debug(f'SubscriptionAdapter.get_plan: {e}')
            return {'has_plan': False, 'plan_name': 'free', 'plan_tier': 'free'}
    
    def is_premium(self, user) -> bool:
        """Quick premium check."""
        plan = self.get_plan(user)
        return plan.get('plan_tier') in ('premium', 'vip', 'gold', 'pro')


# Singleton
subscription_adapter = SubscriptionAdapter()
```

**Register করো `integ_adapter.py`-তে নয়, `apps.py`-তে:**

```python
# apps.py ready()-তে:
try:
    from api.support.integrations.integ_adapter import setup_adapters
    from api.support.integrations.integ_registry import get_registry
    from api.support.integrations.project_specific.subscription_adapter import subscription_adapter
    
    setup_adapters()  # existing adapters
    get_registry().register_adapter('subscription', subscription_adapter)
except Exception as e:
    logger.debug(f'Subscription adapter: {e}')
```

**ব্যবহার:**

```python
from support.integrations.integ_registry import get_registry

registry = get_registry()
adapter  = registry.get_adapter('subscription')
if adapter:
    is_premium = adapter.is_premium(user)
```

---

## 📡 USE CASE 3: নতুন Event Handler যোগ করা

**ধরো: Dispute approve হলে একটি custom reward দিতে চাই।**

```python
# api/support/integrations/project_specific/custom_reward_handler.py

from support.integrations.event_bus import event_bus

@event_bus.on('dispute.approved')
def on_dispute_approved_reward(event_type, dispute=None, ticket=None, **kwargs):
    """
    Dispute approve হলে custom reward দেয়।
    
    Event trigger: integ_handler.py → _auto_approve_dispute() → 
                   event_bus.publish(EVT_OFFER_DISPUTE_APPROVED, ...)
    """
    if not dispute:
        return
    
    try:
        # তোমার custom logic এখানে
        from api.rewards.services import reward_service
        reward_service.grant(
            user    = dispute.user,
            reason  = f'dispute_approved_{dispute.offer_id}',
            amount  = dispute.expected_amount * 0.1,  # 10% bonus
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f'custom_reward_handler: {e}')
```

```python
# apps.py ready()-তে:
try:
    from api.support.integrations.project_specific import custom_reward_handler  # noqa
except Exception:
    pass
```

---

## 🎛️ USE CASE 4: নতুন Feature Flag যোগ করা

**কোনো core file touch করতে হবে না।**

```python
# feature_flags.py-তে DEFAULTS dict-এ add করো:
# (এই file-টি তোমার extension point)

DEFAULTS = {
    # ... existing flags ...
    
    # নতুন flag:
    'SUPPORT_CUSTOM_REWARD': False,          # Custom reward system
    'SUPPORT_MULTI_CURRENCY': False,         # Multi-currency support  
    'SUPPORT_AI_ROUTING': False,             # AI-based ticket routing
    'SUPPORT_SOCIAL_LOGIN_TICKET': False,    # Social login ticket link
}
```

**ব্যবহার:**

```python
from support.feature_flags import is_enabled

if is_enabled('SUPPORT_CUSTOM_REWARD'):
    # reward logic
    pass

# env দিয়ে enable করো (deploy ছাড়া):
# SUPPORT_CUSTOM_REWARD=true python manage.py runserver
```

---

## 🔔 USE CASE 5: নতুন Notification Channel যোগ করা

**ধরো: Discord notification channel যোগ করতে চাই।**

```python
# api/support/integrations/project_specific/discord_backend.py

import logging
import requests
from support.plugins import NotificationBackend

logger = logging.getLogger(__name__)


class DiscordNotificationBackend(NotificationBackend):
    """
    Discord webhook notification backend.
    support.registry-তে register হলে সব ticket notifications Discord-এ যাবে।
    """
    
    def __init__(self, webhook_url: str = ''):
        self.webhook_url = webhook_url or self._get_url()
    
    def _get_url(self) -> str:
        import os
        return os.environ.get('DISCORD_SUPPORT_WEBHOOK', '')
    
    def send(self, user, title: str, body: str, **kwargs) -> bool:
        """Discord embed message পাঠায়।"""
        if not self.webhook_url:
            return False
        try:
            data = {
                'embeds': [{
                    'title':       title,
                    'description': body,
                    'color':       5814783,  # Blue
                    'footer':      {'text': f'User: {user.username}'},
                }]
            }
            resp = requests.post(
                self.webhook_url,
                json=data,
                timeout=5
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.debug(f'DiscordBackend.send: {e}')
            return False
```

**Register করো:**

```python
# apps.py ready()-তে:
try:
    from api.support.registry import support_registry
    from api.support.integrations.project_specific.discord_backend import DiscordNotificationBackend
    support_registry.register_notification_backend('discord', DiscordNotificationBackend())
except Exception as e:
    logger.debug(f'Discord backend: {e}')
```

---

## 📊 USE CASE 6: নতুন Celery Task যোগ করা

**Core `tasks.py` touch করতে হবে না।**

```python
# api/support/integrations/project_specific/custom_tasks.py

import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task
    
    @shared_task(
        bind=True,
        name='support.custom.weekly_dispute_report',
        max_retries=2,
    )
    def weekly_dispute_report(self, tenant_id: int = None):
        """
        সাপ্তাহিক dispute report তৈরি করে admin-কে email করে।
        Celery beat schedule-এ add করো।
        """
        try:
            from support.reports import reports_service
            report = reports_service.get_dispute_report(days=7)
            
            from support.models import SupportSettings
            settings_obj = SupportSettings.objects.filter(id=1).first()
            if settings_obj and settings_obj.support_admin_email:
                from django.core.mail import send_mail
                send_mail(
                    subject = 'Weekly Dispute Report',
                    message = str(report),
                    from_email = 'support@site.com',
                    recipient_list = [settings_obj.support_admin_email],
                )
            return report
        except Exception as exc:
            raise self.retry(exc=exc, countdown=3600)

except ImportError:
    logger.warning('Celery not available')
```

**Celery Beat-এ add করো:**

```python
# celery_beat_config.py → SUPPORT_BEAT_SCHEDULE dict-এ add:
SUPPORT_BEAT_SCHEDULE['support-weekly-dispute-report'] = {
    'task':     'support.custom.weekly_dispute_report',
    'schedule': {'crontab': {'day_of_week': 1, 'hour': 9, 'minute': 0}},  # Monday 9 AM
}
```

```python
# apps.py ready()-তে import করো:
try:
    from api.support.integrations.project_specific import custom_tasks  # noqa
except Exception:
    pass
```

---

## 🏷️ USE CASE 7: নতুন Admin Action যোগ করা

```python
# api/support/integrations/project_specific/custom_admin_actions.py

from django.contrib import messages
from django.utils import timezone


def bulk_send_csat_survey(modeladmin, request, queryset):
    """
    Selected resolved tickets-এ CSAT survey পাঠায়।
    admin_actions.py-তে না গিয়ে এখানে define করো।
    """
    sent = 0
    for ticket in queryset.filter(status='resolved', satisfaction_rating__isnull=True):
        try:
            from support.notifications import notification_service
            notification_service.notify_ticket_resolved(ticket)
            sent += 1
        except Exception:
            pass
    modeladmin.message_user(request, f'CSAT survey sent to {sent} tickets.', messages.SUCCESS)

bulk_send_csat_survey.short_description = '📊 Send CSAT survey to selected'
```

**Admin-এ register:**

```python
# admin.py-র SupportTicketAdmin-এ এই লাইন যোগ করলেই হয়:
# (admin.py modify করছি না — override করছি)

# api/support/integrations/project_specific/admin_extension.py

from django.contrib import admin
from support.admin import SupportTicketAdmin
from support.models import SupportTicket
from support.integrations.project_specific.custom_admin_actions import bulk_send_csat_survey

# Monkey-patch existing admin actions
original_actions = getattr(SupportTicketAdmin, 'actions', []) or []
SupportTicketAdmin.actions = list(original_actions) + [bulk_send_csat_survey]
```

```python
# apps.py ready()-তে:
try:
    from api.support.integrations.project_specific import admin_extension  # noqa
except Exception:
    pass
```

---

## 🔗 USE CASE 8: নতুন API Endpoint যোগ করা

**views.py ও urls.py modify না করে।**

```python
# api/support/integrations/project_specific/custom_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_rewards(request):
    """GET /api/support/my-rewards/ — user-এর support rewards."""
    try:
        from api.rewards.services import reward_service
        rewards = reward_service.get_for_user(request.user)
        return Response({'rewards': rewards})
    except Exception:
        return Response({'rewards': []})
```

**urls.py-তে না গিয়ে — Django URL include দিয়ে:**

```python
# api/support/integrations/project_specific/custom_urls.py

from django.urls import path
from . import custom_views

custom_urlpatterns = [
    path('my-rewards/', custom_views.get_my_rewards, name='support-my-rewards'),
]
```

```python
# তোমার project-এর main urls.py-তে:
from api.support.integrations.project_specific.custom_urls import custom_urlpatterns

urlpatterns = [
    path('api/support/', include('api.support.urls')),
    path('api/support/', include(custom_urlpatterns)),  # নতুন URLs
]
```

---

## 🧪 USE CASE 9: নতুন Test যোগ করা

```python
# api/support/tests/test_custom_features.py  ← নতুন file

from django.test import TestCase
from unittest.mock import patch


class CustomRewardTest(TestCase):
    
    def test_dispute_approved_triggers_reward(self):
        """
        Dispute approve হলে reward দেওয়া হয় কিনা test করো।
        """
        from django.contrib.auth import get_user_model
        from support.models import OfferDispute
        from support.integrations.event_bus import SupportEventBus
        
        User    = get_user_model()
        user    = User.objects.create_user(username='t', email='t@t.com', password='p')
        dispute = OfferDispute.objects.create(user=user, offer_id='OFF1', expected_amount=50)
        
        reward_granted = []
        
        # Test event listener
        bus = SupportEventBus()
        @bus.on('dispute.approved')
        def test_handler(event_type, dispute=None, **kwargs):
            reward_granted.append(True)
        
        bus.publish('dispute.approved', dispute=dispute)
        self.assertEqual(len(reward_granted), 1)
```

---

## 📋 USE CASE 10: নতুন Management Command যোগ করা

```python
# api/support/management/commands/sync_subscription_sla.py  ← নতুন file

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync SLA deadlines based on user subscription plans'
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
    
    def handle(self, *args, **options):
        from support.models import SupportTicket
        from support.integrations.project_specific.subscription_sla import subscription_sla
        
        tickets  = SupportTicket.objects.filter(
            status__in=['open', 'in_progress', 'waiting_user']
        ).select_related('user')
        
        updated = 0
        for ticket in tickets:
            if not options['dry_run']:
                ok = subscription_sla.adjust_sla_for_subscription(ticket)
                if ok:
                    updated += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'{"Would update" if options["dry_run"] else "Updated"} {updated} tickets'
            )
        )
```

---

## 🗂️ Extension File Naming Convention

```
api/support/
├── integrations/
│   └── project_specific/
│       ├── {app_name}_adapter.py      # অন্য app-এর adapter
│       ├── {app_name}_bridge.py       # data transformation
│       ├── {feature}_handler.py       # event handler
│       ├── {feature}_backend.py       # plugin backend
│       └── {feature}_hook.py          # lifecycle hook
├── management/
│   └── commands/
│       └── {task_name}.py             # management command
└── tests/
    └── test_{feature}.py              # feature tests
```

---

## ⚡ Quick Reference: কোথায় কী যোগ করবো

| করতে চাই | File |
|----------|------|
| Ticket lifecycle hook | `integrations/project_specific/{name}_hook.py` + `apps.py` |
| অন্য app-এর data read | `integrations/project_specific/{app}_adapter.py` |
| Event-driven logic | `integrations/project_specific/{name}_handler.py` (event_bus.on) |
| Notification channel | `integrations/project_specific/{channel}_backend.py` + registry |
| Background job | `integrations/project_specific/custom_tasks.py` + celery_beat_config |
| Admin action | `integrations/project_specific/custom_admin_actions.py` + admin_extension |
| New API endpoint | `integrations/project_specific/custom_views.py` + custom_urls.py |
| Feature toggle | `feature_flags.py` → DEFAULTS dict |
| Scheduled task | `celery_beat_config.py` → SUPPORT_BEAT_SCHEDULE |
| Django signal | `signals_{topic}.py` (নতুন file) |
| Management cmd | `management/commands/{name}.py` |
| Test | `tests/test_{feature}.py` |

---

## ✅ Checklist: নতুন Feature যোগ করার আগে

```
□ Feature flag add করা হয়েছে? (feature_flags.py)
□ Core file (models/views/services) modify করা হয়নি?
□ অন্য app-এর field সরাসরি write করা হয়নি?
□ Adapter দিয়ে অন্য app call করা হয়েছে?
□ Error handling আছে (try/except with logger)?
□ Test file তৈরি করা হয়েছে?
□ apps.py ready()-তে register করা হয়েছে?
□ EXTENSION_GUIDE update করা হয়েছে (changelog)?
```

---

## 🚨 Anti-patterns (কখনো করবে না)

```python
# ❌ WRONG — core file modify
# services.py-তে:
def create(self, user, data):
    # ... existing code ...
    send_discord_notification(ticket)  # এটা services.py-তে করবে না

# ✅ CORRECT — hook/event দিয়ে
# integrations/project_specific/discord_hook.py:
@event_bus.on('ticket.created')
def send_discord(event_type, ticket=None, **kwargs):
    send_discord_notification(ticket)
```

```python
# ❌ WRONG — অন্য app-এর field সরাসরি
from api.wallet.models import Wallet
wallet = Wallet.objects.get(user=user)
wallet.balance += 100  # ❌ wallet app-এর territory
wallet.save()

# ✅ CORRECT — adapter দিয়ে call
from support.integrations.integ_adapter import wallet_adapter
wallet_adapter.credit(user, amount=100, reason='dispute_approved')
```

```python
# ❌ WRONG — hardcode
if ticket.priority == 'urgent':
    send_pagerduty_alert()  # models.py বা services.py-তে

# ✅ CORRECT — feature flag + hook
from support.feature_flags import is_enabled
if is_enabled('SUPPORT_PAGERDUTY_ALERTS'):
    # integrations/project_specific/pagerduty_hook.py-তে
    @event_bus.on('sla.breach')
    def pagerduty_on_breach(event_type, ticket=None, **kwargs):
        if is_enabled('SUPPORT_PAGERDUTY_ALERTS'):
            send_pagerduty_alert(ticket)
```

---

## 🎯 Summary

```
নতুন feature = নতুন file (integrations/project_specific/)
             + apps.py-তে 3 লাইন import
             + feature flag (optional)

Core code    = কখনো touch করবে না
             = শুধু read করবে (reference এর জন্য)
```

> **এই pattern follow করলে সিস্টেম 5 বছর চলবে — core একটি লাইনও change ছাড়া।**
