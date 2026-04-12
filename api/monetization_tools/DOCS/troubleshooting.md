# Troubleshooting Guide

## Common Issues

---

### 1. Postback Not Processing

**Symptom:** Offer completions not being credited to users.

**Check:**
```bash
# Check unprocessed postback queue
python manage.py shell -c "
from api.monetization_tools.models import PostbackLog
print('Unprocessed:', PostbackLog.objects.filter(status='received').count())
print('Errors:',      PostbackLog.objects.filter(status='error').count())
"
```

**Common Causes:**
- Celery worker not running → `celery -A config worker -l info`
- Invalid signature → Check `postback_secret` in AdNetwork settings
- Missing `txn_id` in postback payload → Review network postback config
- Duplicate postback → Already processed, this is expected

**Fix:**
```bash
python SCRIPTS/health_check.py --check postback
python api/monetization_tools/SCRIPTS/sync_ad_networks.py --date yesterday
```

---

### 2. Low Fill Rate

**Symptom:** Fill rate below 50% for an ad unit.

**Check:**
```python
from api.monetization_tools.AD_PERFORMANCE.fill_rate_analyzer import FillRateAnalyzer
low = FillRateAnalyzer.low_fill_units(days=7)
```

**Common Causes:**
- Floor price too high → Lower floor or remove floor config
- No active waterfall entries → Add networks to WaterfallConfig
- Network timeout too low → Increase `timeout_ms` for slow networks
- No demand in target geo → Add geo-specific lower floor prices

**Fix:**
```bash
python SCRIPTS/optimize_waterfall.py --action floors --days 14
python SCRIPTS/update_ad_config.py --action auto_optimize
```

---

### 3. Revenue Discrepancy

**Symptom:** Our revenue numbers don't match network reports.

**Check:**
```python
from api.monetization_tools.models import AdNetworkDailyStat
high_disc = AdNetworkDailyStat.objects.filter(discrepancy_pct__gte=10).order_by('-date')
```

**Common Causes:**
- Duplicate postbacks (we count twice)
- Postback validation failures (we reject valid completions)
- Time zone mismatch between our server and network reports
- Currency conversion differences

**Fix:**
```bash
python SCRIPTS/sync_ad_networks.py --date 2024-01-15
python SCRIPTS/calculate_revenue.py --date 2024-01-15
```

---

### 4. Cache Issues

**Symptom:** Stale data being returned (old offers, old subscription plans, etc.)

**Fix:**
```bash
# Clear specific cache type
python SCRIPTS/clean_ad_cache.py --type offerwall
python SCRIPTS/clean_ad_cache.py --type subscriptions
python SCRIPTS/clean_ad_cache.py --type config

# Clear all caches (use with caution in production)
python SCRIPTS/clean_ad_cache.py --type all --warm
```

---

### 5. A/B Test Not Assigning Users

**Symptom:** All users get the same variant or test is not running.

**Check:**
```python
from api.monetization_tools.models import ABTest, ABTestAssignment
test = ABTest.objects.get(name="My Test")
print("Status:", test.status)
print("Variants:", test.variants)
print("Traffic split:", test.traffic_split)
print("Assignments:", ABTestAssignment.objects.filter(test=test).count())
```

**Common Causes:**
- Test status is not "running" → Start the test
- `traffic_split` is 0 → Set to 100 for all traffic
- Variants have 0 weight → Set weights > 0
- No users in traffic bucket → Increase traffic_split

---

### 6. Subscription Not Renewing

**Symptom:** User subscription expired but auto-renewal didn't trigger.

**Check:**
```python
from api.monetization_tools.models import RecurringBilling
from django.utils import timezone
overdue = RecurringBilling.objects.filter(
    status='scheduled', scheduled_at__lt=timezone.now()
)
print("Overdue billings:", overdue.count())
```

**Fix:**
```bash
# Check Celery periodic tasks
celery -A config inspect scheduled

# Manually trigger
python manage.py shell -c "
from api.monetization_tools.tasks import process_auto_renewals
process_auto_renewals.delay()
"
```

---

### 7. Fraud Alerts Blocking Legitimate Users

**Symptom:** Valid users getting fraud-blocked due to VPN or shared IP.

**Fix:**
```python
# Resolve specific fraud alert
from api.monetization_tools.models import FraudAlert
from django.utils import timezone

alert = FraudAlert.objects.get(alert_id="...")
alert.resolution      = "cleared"
alert.resolution_note = "False positive — verified user"
alert.resolved_at     = timezone.now()
alert.save()

# Unblock user if blocked
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.filter(pk=user.pk).update(account_level="normal")
```

---

### 8. Health Check Failures

**Run full health check:**
```bash
python SCRIPTS/health_check.py --verbose --json
```

**Common exit codes:**
- `0` = Everything OK
- `1` = Warnings (degraded, not critical)
- `2` = Critical failure (DB or cache unreachable)

---

### 9. Payout Processing Stuck

**Symptom:** Approved payouts not being marked as paid.

**Check:**
```python
from api.monetization_tools.models import PayoutRequest
approved = PayoutRequest.objects.filter(status='approved')
print("Approved payouts pending payment:", approved.count())
```

**Fix:**
```bash
python manage.py shell -c "
from api.monetization_tools.tasks import send_payout_notifications, process_recurring_payouts
send_payout_notifications.delay()
"
```

---

## Log Locations

| Component | Log |
|-----------|-----|
| API requests | `logs/django.log` |
| Celery tasks | `logs/celery.log` |
| Ad sync | `logs/sync_ad_networks.log` |
| Health check | stdout / `logs/health.log` |
| Postback | `logs/postback.log` |

---

## Support Contacts

- **Technical Issues:** devteam@yourcompany.com
- **Ad Network Issues:** Contact respective network support
- **Payment Gateway Issues:** Contact bKash / Nagad / Stripe support
