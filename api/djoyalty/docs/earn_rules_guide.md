# Earn Rules Guide — Djoyalty

## Overview
Earn Rules নির্ধারণ করে কখন এবং কতটুকু points earn হবে।
প্রতিটি rule এর trigger, type, conditions এবং priority থাকে।

## Rule Types
| Type | Description | Example |
|---|---|---|
| `fixed` | Flat points, trigger এ | Signup = 100 pts |
| `percentage` | Spend এর % | 1% of spend = 1 pt per 100 |
| `multiplier` | Spend × multiplier | 2× spend amount |
| `bonus` | Extra bonus on top | +50 pts extra |
| `category` | Category-specific | Electronics 2× |

## Triggers
| Trigger | When fires |
|---|---|
| `purchase` | Every purchase/transaction |
| `signup` | Customer registration |
| `birthday` | Customer's birthday |
| `referral` | Successful referral |
| `review` | Writing a review |
| `checkin` | Physical checkin |
| `custom` | Custom event via API |

## Rule Evaluation Order
1. Active rules ফিল্টার (is_active=True, valid_from/until range)
2. Trigger match করো
3. Tier eligibility check (applicable_tiers)
4. Priority descending sort (highest priority first)
5. **First matching rule applies** (waterfall)
6. Conditions check (EarnRuleCondition)
7. Tier multiplier apply (EarnRuleTierMultiplier)
8. Points calculate করো

## Setup via Management Command
```bash
python manage.py seed_earn_rules
```

Default rules:
- Standard Purchase Rule: 1 pt per 1 unit spend
- Sign Up Bonus: 100 pts one-time
- Birthday Bonus: 200 pts annually
- Referral Bonus (Referrer): 150 pts
- Review Reward: 25 pts

## Creating Custom Rules (Admin Panel)
1. Django Admin → Earn Rules → Add
2. Set name, rule_type, trigger
3. Set points_value and multiplier
4. Set min_spend if needed
5. Set valid_from/valid_until for time-limited promos
6. Set priority (higher = evaluated first)
7. Optionally restrict to specific tiers (applicable_tiers JSON array)

## API
```
GET  /api/djoyalty/earn-rules/         # All rules
GET  /api/djoyalty/earn-rules/active/  # Currently active
POST /api/djoyalty/bonus-events/award/ # Manual bonus award
```

## Celery Tasks
```
djoyalty.deactivate_expired_earn_rules  # Daily: deactivate past valid_until
djoyalty.activate_scheduled_earn_rules  # Daily: activate past valid_from
```
