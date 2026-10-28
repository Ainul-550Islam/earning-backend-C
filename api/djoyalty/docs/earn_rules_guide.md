# Earn Rules Guide

## Rule Types

| Type | Description | Example |
|---|---|---|
| `fixed` | Fixed points per trigger | Login = 5 pts |
| `percentage` | % of spend amount | 1% of spend |
| `multiplier` | Spend × multiplier | Spend × 2 = pts |

## Trigger Events

| Trigger | When |
|---|---|
| `purchase` | Customer makes a purchase |
| `offer` | Completes an offer/CPA |
| `login` | Daily login |
| `referral` | Refers a new customer |
| `birthday` | On birthday date |
| `signup` | First account creation |
| `review` | Leaves a review |
| `social_share` | Shares on social media |

## Seed Default Rules
```bash
python manage.py seed_earn_rules
python manage.py seed_earn_rules --reset
```

## Default Rules Included
- Standard Purchase Earn: 1pt per 1 BDT
- First Purchase Bonus: +100 pts
- Referral Signup: +200 pts
- Login Bonus: +5 pts/day
- Birthday Bonus: +500 pts
- Welcome Signup: +50 pts

## Tier Multiplier Override

Per-rule, per-tier multiplier can override the global tier multiplier:

```python
from djoyalty.models.earn_rules import EarnRuleTierMultiplier
EarnRuleTierMultiplier.objects.create(
    rule=rule, tier=gold_tier, multiplier=Decimal('2.0')
)
```

## Earn Rule Conditions

Additional conditions can restrict when a rule applies:

```python
EarnRuleCondition.objects.create(
    rule=rule,
    condition_type='min_amount',  # min_amount | tier | day | offer
    operator='gte',
    value='500',
)
```

## API: Earn Points
```http
POST /api/loyalty/points/earn/
Authorization: Bearer <token>
{
  "customer_id": 1,
  "spend_amount": "750.00"
}
```

## Bonus Events
```http
POST /api/loyalty/bonus-events/award/
Authorization: Bearer <admin-token>
{
  "customer_id": 1,
  "points": 200,
  "reason": "Special VIP bonus"
}
```
