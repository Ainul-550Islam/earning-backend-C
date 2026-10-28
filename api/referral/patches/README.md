# 🔑 "এক কাজের জন্য একটাই মালিক — api.referral"

## নিয়ম: অন্য কোনো module এ নিজস্ব referral code থাকবে না

সব referral logic **`api/referral/`** মডিউলে থাকবে।
অন্য module গুলো শুধু **import করে call করবে**।

---

## ✅ সঠিক Pattern (অন্য module থেকে)

```python
# যেকোনো module থেকে referral call করার একমাত্র সঠিক উপায়:
from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge

bridge = get_bridge()

# Signup
bridge.on_signup(new_user=user, referral_code='EARN1234')

# Commission (task/offer complete)
bridge.on_task_earned(user=user, task=task, amount=100)
bridge.on_offer_completed(user=user, offer_id='123', user_net_reward=50)

# Stats
stats = bridge.get_user_referral_summary(user)
code  = bridge.get_referral_code(user)
```

---

## ❌ ভুল Pattern (আর করবেন না)

```python
# ❌ নিজস্ব referral model তৈরি করবেন না
class UserReferral(models.Model): ...

# ❌ নিজস্ব commission calculate করবেন না
commission = earned * Decimal('0.05')

# ❌ Cache-based referral tree ব্যবহার করবেন না
cache.set(f'referral_parent:{user_id}', referrer_id)

# ❌ api.referral.models এ সরাসরি query করবেন না (অন্য module থেকে)
Referral.objects.filter(referrer=user).count()
```

---

## 📁 Patches Directory (এই ফাইলগুলো আপনার project এ replace করুন)

| Patch File | Replace করুন |
|---|---|
| `promotions_services_referral_service.py` | `api/promotions/services/referral_service.py` |
| `promotions_referral_referral_manager.py` | `api/promotions/referral/referral_manager.py` |
| `users_referral_referral_tracker.py` | `api/users/referral/referral_tracker.py` |
| `wallet_referral_commission_fix.py` | `api/wallet/services.py` এর `add_referral_commission` method |
| `offer_inventory_models_patch.py` | `api/offer_inventory/models.py` এর `UserReferral`, `ReferralCommission`, `CommissionTier` classes |

---

## 🗄️ Database Migration Strategy

```bash
# 1. Migrate new referral models
python manage.py migrate referral

# 2. Seed fraud rules
python manage.py seed_referral_fraud_rules

# 3. Fix duplicate data (one-time)
python manage.py shell -c "
from api.referral.INTEGRATION_SYSTEM.sync_manager import ReferralSyncManager
sm = ReferralSyncManager()
# Check conflicts first (dry-run)
print(sm.detect_conflicts())
# Then sync (will migrate offer_inventory.UserReferral → referral.Referral)
print(sm.sync_from_offer_inventory(dry_run=False))
print(sm.fix_promotions_cache_tree())
"

# 4. Rebuild trees
python manage.py rebuild_referral_trees --all
```

---

## ⚡ WebSocket Real-time Setup

```python
# config/routing.py
from api.referral.consumers import get_websocket_urlpatterns

websocket_urlpatterns = get_websocket_urlpatterns()

# settings.py
INSTALLED_APPS += ['channels']
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
    }
}
```

---

## 📊 Current Module Architecture

```
┌─────────────────────────────────────────────────┐
│              api/referral/  (MASTER)             │
│  models/ services/ viewsets/ tasks/              │
│  INTEGRATION_SYSTEM/  consumers.py               │
└──────────────┬──────────────────────────────────┘
               │ (import only — no DB queries)
    ┌──────────┼──────────────────────┐
    │          │                      │
┌───┴───┐  ┌──┴──────┐  ┌────────────┴────┐
│ users │  │promotions│  │offer_inventory  │
│       │  │          │  │                 │
│ bridge│  │ bridge   │  │ bridge          │
└───────┘  └──────────┘  └─────────────────┘
```
