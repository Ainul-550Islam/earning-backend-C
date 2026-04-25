# Notification System — Extension Guide
## নতুন Feature যোগ করার সম্পূর্ণ Guide

> "এক কাজের জন্য একটাই মালিক" — এই guide অনুসরণ করলে **core notification code কখনো touch করতে হবে না।**

---

## 📋 সূচিপত্র

1. [নতুন Module যোগ (Zero-config)](#1-নতুন-module-যোগ)
2. [নতুন Notification Channel যোগ](#2-নতুন-channel-যোগ)
3. [নতুন Notification Type যোগ](#3-নতুন-notification-type-যোগ)
4. [নতুন Template যোগ](#4-নতুন-template-যোগ)
5. [নতুন Analytics Metric যোগ](#5-নতুন-analytics-metric-যোগ)
6. [নতুন Journey যোগ](#6-নতুন-journey-যোগ)
7. [নতুন Workflow যোগ](#7-নতুন-workflow-যোগ)
8. [Custom Hook যোগ](#8-custom-hook-যোগ)
9. [Custom Segment Filter যোগ](#9-custom-segment-filter-যোগ)
10. [নতুন Webhook Provider যোগ](#10-নতুন-webhook-provider-যোগ)
11. [Feature Flag দিয়ে Control](#11-feature-flag-দিয়ে-control)
12. [চেকলিস্ট — কোনো কিছু ভুলেছি?](#12-checklist)

---

## 1. নতুন Module যোগ

**উদাহরণ:** `api/subscription/` module যোগ করতে হবে এবং subscription expire হলে notification পাঠাতে হবে।

### শুধু একটি ফাইল তৈরি করুন:

```python
# api/subscription/integ_config.py
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class SubscriptionIntegConfig(ModuleConfig):
    module_name = 'subscription'
    version = '1.0.0'
    description = 'Subscription & Premium Plans'

    signal_maps = [
        SignalMap(
            model_path='subscription.UserSubscription',
            field='status',
            value='expired',
            event_type='subscription.expired',
            user_field='user_id',
            data_fields=['plan_name', 'expired_at', 'renewal_amount'],
        ),
        SignalMap(
            model_path='subscription.UserSubscription',
            field='status',
            value='active',
            event_type='subscription.activated',
            user_field='user_id',
            data_fields=['plan_name', 'expires_at'],
            on_created=True,
            on_update=True,
        ),
    ]

    event_maps = [
        EventMap(
            event_type='subscription.expired',
            notification_type='announcement',
            title_template='Subscription Expired ⚠️',
            message_template='আপনার {plan_name} subscription মেয়াদ শেষ হয়েছে। Renew করুন!',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='subscription.activated',
            notification_type='announcement',
            title_template='Subscription Active ✅',
            message_template='{plan_name} সক্রিয় হয়েছে। {expires_at} পর্যন্ত উপভোগ করুন!',
            channel='in_app',
            priority='medium',
        ),
    ]

    health_checks = [
        HealthCheck(name='subscription_db', model_path='subscription.UserSubscription')
    ]
```

**সেটাই!** Auto-discovery engine বাকি সব করবে। Django restart করুন।

---

## 2. নতুন Channel যোগ

**উদাহরণ:** `WhatsApp Business API` provider যোগ করতে হবে।

### Step 1: Provider class তৈরি করুন

```python
# api/notifications/services/providers/WhatsAppBusinessProvider.py
from typing import Dict
from django.conf import settings

class WhatsAppBusinessProvider:
    """WhatsApp Business API notification provider."""

    def __init__(self):
        self._token = getattr(settings, 'WHATSAPP_BUSINESS_TOKEN', '')
        self._phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', '')
        self._available = bool(self._token and self._phone_id)

    def is_available(self) -> bool:
        return self._available

    def send(self, notification, phone: str = '', **kwargs) -> Dict:
        if not self._available:
            return {'success': False, 'error': 'Not configured'}

        # Your WhatsApp Business API call here
        import requests
        resp = requests.post(
            f'https://graph.facebook.com/v17.0/{self._phone_id}/messages',
            headers={'Authorization': f'Bearer {self._token}'},
            json={
                'messaging_product': 'whatsapp',
                'to': phone,
                'type': 'text',
                'text': {'body': f'{notification.title}\n\n{notification.message}'}
            }
        )
        return {'success': resp.status_code == 200, 'provider': 'whatsapp_business'}

    def health_check(self) -> str:
        return 'healthy' if self._available else 'unhealthy'

wa_business_provider = WhatsAppBusinessProvider()
```

### Step 2: Dispatcher এ register করুন (dispatcher patch)

```python
# api/notifications/services/providers/__init__.py এ যোগ করুন:
from .WhatsAppBusinessProvider import wa_business_provider  # noqa
```

### Step 3: Plugin registry তে যোগ করুন

```python
# api/notifications/plugins.py এর register_builtin_providers() তে যোগ করুন:
try:
    from .providers.WhatsAppBusinessProvider import wa_business_provider
    class WABusinessPlugin(ProviderPlugin):
        name = 'whatsapp_business'
        channel = 'whatsapp_business'
        def is_available(self): return wa_business_provider.is_available()
        def send(self, notification, **kwargs): return wa_business_provider.send(notification, **kwargs)
    plugin_registry.register(WABusinessPlugin())
except Exception:
    pass
```

### Step 4: choices.py তে channel যোগ করুন

```python
# api/notifications/choices.py CHANNEL_CHOICES তে যোগ করুন:
('whatsapp_business', 'WhatsApp Business API'),
```

### Step 5: NotificationDispatcher তে route করুন

```python
# api/notifications/services/NotificationDispatcher.py dispatch_map তে যোগ করুন:
'whatsapp_business': self._dispatch_whatsapp_business,

# এবং method যোগ করুন:
def _dispatch_whatsapp_business(self, notification) -> Dict:
    from .providers.WhatsAppBusinessProvider import wa_business_provider
    if wa_business_provider.is_available():
        result = wa_business_provider.send(notification)
        if result.get('success'):
            notification.mark_as_sent()
        return {'success': result.get('success', False), 'results': [result]}
    return {'success': False, 'results': [], 'error': 'WABusiness not available'}
```

---

## 3. নতুন Notification Type যোগ

**উদাহরণ:** `subscription_renewal_reminder` type যোগ করতে হবে।

### Step 1: choices.py তে type যোগ করুন

```python
# api/notifications/choices.py NOTIFICATION_TYPE_CHOICES তে যোগ করুন:
('subscription_renewal_reminder', 'Subscription Renewal Reminder'),
('subscription_upgraded',         'Subscription Upgraded'),
```

### Step 2: registry.py তে default config যোগ করুন

```python
# api/notifications/registry.py _register_defaults() এ যোগ করুন:
# (type, channel, priority, push, email, sms)
('subscription_renewal_reminder', 'in_app', 'high', True, True, False),
('subscription_upgraded',         'in_app', 'high', True, True, False),
```

### Step 3: (Optional) Notification sound যোগ করুন

```python
# api/notifications/logic.py get_notification_sound() sound_map তে যোগ করুন:
'subscription_renewal_reminder': 'reminder',
'subscription_upgraded': 'success',
```

### Step 4: (Optional) Icon যোগ করুন

```python
# api/notifications/helpers.py get_notification_icon() icons তে যোগ করুন:
'subscription_renewal_reminder': '⏰',
'subscription_upgraded': '⭐',
```

**Migration দরকার নেই।** Notification type শুধু একটি CharField।

---

## 4. নতুন Template যোগ করুন

### Option A: Django Admin দিয়ে (Recommended)

```
/admin/notifications/notificationtemplate/add/
```

### Option B: Management Command দিয়ে

```python
# api/notifications/management/commands/seed_templates.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        from notifications.models import NotificationTemplate
        NotificationTemplate.objects.get_or_create(
            name='subscription_renewal_reminder',
            defaults={
                'template_type': 'subscription_renewal_reminder',
                'channel': 'in_app',
                'title_en': 'Subscription Expiring Soon! ⏰',
                'title_bn': 'Subscription শেষ হচ্ছে! ⏰',
                'message_en': 'Your {plan_name} expires in {days_left} days. Renew now!',
                'message_bn': 'আপনার {plan_name} {days_left} দিন পর শেষ হবে। এখনই renew করুন!',
                'is_active': True,
            }
        )
        self.stdout.write('Templates seeded!')
```

### Option C: Liquid Template syntax ব্যবহার করুন

```
Title:   Subscription শেষ হচ্ছে! {{ plan_name | upcase }}
Message: আপনার balance {{ balance | money }}। 
         {% if days_left <= 3 %}জরুরি: মাত্র {{ days_left }} দিন বাকি!{% endif %}
```

---

## 5. নতুন Analytics Metric যোগ

**উদাহরণ:** Subscription cancellation rate track করতে হবে।

```python
# api/notifications/analytics.py তে function যোগ করুন:
def get_subscription_notification_effectiveness(*, days=30):
    """Track if subscription notifications reduce churn."""
    from notifications.models import Notification
    from django.db.models import Count, Q

    # Users who received subscription_renewal_reminder
    notified = set(
        Notification.objects.filter(
            notification_type='subscription_renewal_reminder',
            created_at__gte=timezone.now() - timedelta(days=days),
        ).values_list('user_id', flat=True)
    )

    # Of those, how many renewed? (check if wallet_credited or subscription_activated received)
    renewed = set(
        Notification.objects.filter(
            user_id__in=notified,
            notification_type='subscription_activated',
            created_at__gte=timezone.now() - timedelta(days=days),
        ).values_list('user_id', flat=True)
    )

    return {
        'notified_users': len(notified),
        'renewed_users': len(renewed),
        'renewal_rate': round(len(renewed) / max(len(notified), 1) * 100, 2),
    }
```

---

## 6. নতুন Journey যোগ

```python
# api/notifications/services/JourneyService.py এর _register_builtin_journeys() তে যোগ করুন:

self.JOURNEYS['subscription_renewal'] = Journey(
    journey_id='subscription_renewal',
    name='Subscription Renewal Drip',
    description='Remind users to renew subscription: 7d, 3d, 1d before expiry',
    steps=[
        JourneyStep(
            step_id='reminder_7d',
            name='7-Day Reminder',
            channel='email',
            notification_type='subscription_renewal_reminder',
            title_template='⏰ Subscription শেষ হচ্ছে ৭ দিনে',
            message_template='আপনার {plan_name} ৭ দিন পর expire হবে। এখনই renew করুন!',
            delay_days=0,
        ),
        JourneyStep(
            step_id='reminder_3d',
            name='3-Day Urgent Reminder',
            channel='push',
            notification_type='subscription_renewal_reminder',
            title_template='⚠️ মাত্র ৩ দিন বাকি!',
            message_template='{plan_name} expire হতে মাত্র ৩ দিন। Renew করুন!',
            delay_days=4,  # 4 days after step 1 = D-3
            priority='high',
        ),
        JourneyStep(
            step_id='reminder_1d',
            name='Last Day Reminder',
            channel='sms',
            notification_type='subscription_renewal_reminder',
            title_template='আজই শেষ দিন!',
            message_template='আপনার subscription আজ expire হবে। এখনই: {renewal_url}',
            delay_days=2,  # 2 days after step 2 = D-1
            priority='urgent',
        ),
    ]
)
```

**Trigger করুন:**
```python
from notifications.services.JourneyService import journey_service
journey_service.enroll_user(user, 'subscription_renewal', {
    'plan_name': 'Premium Plan',
    'days_left': 7,
    'renewal_url': 'https://yoursite.com/renew',
})
```

---

## 7. নতুন Workflow যোগ

```python
# api/notifications/workflow.py এর _register_builtin_workflows() তে যোগ করুন:

@self.workflow(
    'subscription_expired_winback',
    name='Subscription Expired Win-Back',
    trigger_events=['subscription.expired'],
    max_executions=1,
    cooldown_hours=24 * 30,  # Once per month
)
def subscription_expired(user, data: dict):
    plan_name = data.get('plan_name', 'Premium')
    return WorkflowActions.send_notification(
        user=user,
        notification_type='special_offer',
        title='🎁 50% ছাড়ে Subscription নিন!',
        message=f'{plan_name} expire হয়েছে। ৭ দিনের মধ্যে renew করলে 50% ছাড় পাবেন!',
        channel='in_app',
        priority='high',
    )
```

**Trigger হবে automatically** যখন EventBus এ `subscription.expired` event publish হবে।

---

## 8. Custom Hook যোগ

```python
# আপনার module এর apps.py তে:
from notifications.hooks import pipeline

@pipeline.hook('pre_send', priority=4)
def check_subscription_notification_allowed(notification, context: dict):
    """Block marketing notifications to expired subscription users."""
    import logging
    logger = logging.getLogger(__name__)

    user = getattr(notification, 'user', None)
    priority = getattr(notification, 'priority', 'medium')

    # Critical notifications always go through
    if priority in ('critical', 'urgent'):
        return notification, context

    # Check subscription status
    if user:
        try:
            from subscription.models import UserSubscription
            is_expired = UserSubscription.objects.filter(
                user=user, status='expired'
            ).exists()
            if is_expired:
                notif_type = getattr(notification, 'notification_type', '')
                # Block marketing, allow transactional
                MARKETING_TYPES = {'promotion', 'special_offer', 'flash_sale', 'limited_offer'}
                if notif_type in MARKETING_TYPES:
                    context['blocked_by'] = 'subscription_expired'
                    from notifications.hooks import StopPipeline
                    raise StopPipeline(f'Marketing blocked for expired subscriber #{user.pk}')
        except StopPipeline:
            raise
        except Exception as exc:
            logger.debug(f'subscription hook: {exc}')

    return notification, context
```

---

## 9. Custom Segment Filter যোগ

```python
# api/notifications/services/SegmentService.py evaluate_realtime() তে যোগ করুন:
# অথবা আপনার module এর integ_config.py তে adapter দিয়ে:

class SubscriptionAdapter(BaseAdapter):
    name = 'subscription'

    def _do_send(self, payload, **kwargs):
        action = payload.get('action', '')

        if action == 'get_active_subscriber_ids':
            from subscription.models import UserSubscription
            ids = list(
                UserSubscription.objects.filter(status='active')
                .values_list('user_id', flat=True)
            )
            return {'success': True, 'data': {'user_ids': ids}}

        if action == 'get_expiring_subscriber_ids':
            from django.utils import timezone
            from datetime import timedelta
            days = payload.get('days', 7)
            cutoff = timezone.now() + timedelta(days=days)
            ids = list(
                UserSubscription.objects.filter(
                    status='active',
                    expires_at__lte=cutoff,
                ).values_list('user_id', flat=True)
            )
            return {'success': True, 'data': {'user_ids': ids}}

        return {'success': True, 'data': {}}
```

**Campaign এ use করুন:**
```python
# Campaign target_segment:
{
    "type": "custom",
    "source": "subscription",
    "action": "get_expiring_subscriber_ids",
    "days": 7,
}
```

---

## 10. নতুন Webhook Provider যোগ

```python
# api/notifications/integration_system/example_configs/subscription_integ_config.py তে:

webhook_maps = [
    WebhookMap(
        provider='stripe',
        event_types=['customer.subscription.deleted'],
        event_output='subscription.expired',
    ),
    WebhookMap(
        provider='stripe',
        event_types=['customer.subscription.created'],
        event_output='subscription.activated',
    ),
]
```

---

## 11. Feature Flag দিয়ে Control

```python
# settings.py তে:
NOTIFICATION_FEATURES = {
    'SUBSCRIPTION_NOTIFICATIONS': True,
    'SUBSCRIPTION_EMAIL_REMINDER': True,
    'SUBSCRIPTION_SMS_REMINDER': False,  # এখনো SMS চালু করিনি
}

# আপনার code এ:
from notifications.feature_flags import flags

if flags.is_enabled('SUBSCRIPTION_SMS_REMINDER'):
    # SMS send করুন
    pass

# Runtime এ toggle করুন (server restart ছাড়াই):
flags.enable('SUBSCRIPTION_SMS_REMINDER')   # চালু
flags.disable('SUBSCRIPTION_SMS_REMINDER')  # বন্ধ
```

---

## 12. Checklist

নতুন feature যোগ করার সময় এই checklist check করুন:

### নতুন Module যোগ:
- [ ] `api/your_module/integ_config.py` তৈরি করা হয়েছে
- [ ] `SignalMap` সব relevant model events cover করে
- [ ] `EventMap` সব notification types define করে
- [ ] `health_checks` যোগ করা হয়েছে
- [ ] Django restart করা হয়েছে (auto-discovery চলবে)

### নতুন Channel যোগ:
- [ ] `services/providers/YourProvider.py` তৈরি
- [ ] `is_available()` এবং `send()` implement করা
- [ ] `providers/__init__.py` তে import করা
- [ ] `plugins.py` তে register করা
- [ ] `choices.py` CHANNEL_CHOICES তে যোগ
- [ ] `NotificationDispatcher.dispatch_map` তে যোগ
- [ ] `constants.py` NotificationChannels তে যোগ

### নতুন Notification Type যোগ:
- [ ] `choices.py` NOTIFICATION_TYPE_CHOICES তে যোগ
- [ ] `registry.py` _register_defaults() তে default config
- [ ] (Optional) `logic.py` sound map তে যোগ
- [ ] (Optional) `helpers.py` icon map তে যোগ

### নতুন Journey:
- [ ] `JourneyService._register_builtin_journeys()` তে যোগ
- [ ] প্রতিটি step এ সঠিক `delay_days` দেওয়া হয়েছে
- [ ] `exit_if` condition দেওয়া হয়েছে যাতে irrelevant user skip হয়

### নতুন Workflow:
- [ ] `WorkflowEngine._register_builtin_workflows()` তে যোগ
- [ ] `trigger_events` সঠিকভাবে set করা
- [ ] `cooldown_hours` reasonable value দেওয়া

---

## ⚡ Quick Reference — কোথায় কী যোগ করব

| কী যোগ করতে চাই | কোথায় যোগ করব | কতক্ষণ লাগবে |
|---|---|---|
| নতুন Django module notification | `module/integ_config.py` | ১৫ মিনিট |
| নতুন push/SMS/email provider | `services/providers/YourProvider.py` | ৩০-৬০ মিনিট |
| নতুন notification type | `choices.py` + `registry.py` | ৫ মিনিট |
| নতুন email template | Django Admin বা `seed_templates.py` | ১০ মিনিট |
| নতুন analytics metric | `analytics.py` তে function যোগ | ২০-৩০ মিনিট |
| নতুন journey | `JourneyService` তে যোগ | ২০ মিনিট |
| নতুন workflow | `workflow.py` তে decorator | ১০ মিনিট |
| নতুন send rule | `hooks.py` তে hook | ১০ মিনিট |
| নতুন segment filter | adapter `_do_send()` তে action | ২০ মিনিট |
| Feature on/off | `NOTIFICATION_FEATURES` settings | ১ মিনিট |

---

## 🔥 Golden Rules

1. **Core notification code কখনো touch করবেন না** — সব extension point আছে
2. **`integ_config.py` = new module এর complete wiring** — ফাইলটি তৈরি হলেই system জানবে
3. **`hooks.py` = send pipeline interceptor** — business rule বদলাতে hook ব্যবহার করুন
4. **`feature_flags.py` = runtime toggle** — code deploy ছাড়াই feature on/off করুন
5. **`workflow.py` = event-based automation** — trigger করুন, manually send করবেন না
6. **`analytics.py` = metric collection** — নতুন metric যোগ করুন, existing code ভাঙবেন না

---

*Last updated: এই system এক বার setup হলে নতুন module যোগ করতে শুধু `integ_config.py` তৈরি করতে হবে।*
