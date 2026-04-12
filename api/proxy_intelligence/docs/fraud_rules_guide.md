# Fraud Rules Configuration Guide

The `FraudRule` model lets you define custom, no-code rules that are
evaluated in real-time against every IP check. Rules fire actions
(block, challenge, flag, alert) when conditions are met.

---

## Rule Structure

Each `FraudRule` has:

| Field | Description |
|-------|-------------|
| `name` | Human-readable name |
| `rule_code` | Unique code used in logs (e.g. `BLOCK_TOR`) |
| `condition_type` | What to check (see below) |
| `condition_value` | JSON config for the condition |
| `action` | What to do: `block`, `challenge`, `flag`, `alert`, `allow` |
| `priority` | Lower = evaluated first |
| `is_active` | Enable/disable without deleting |

---

## Condition Types

### `vpn_detected`
Triggers when the IP is identified as a VPN.
```json
{"condition_value": {}}
```

### `proxy_detected`
Triggers when the IP is identified as any proxy.
```json
{"condition_value": {}}
```

### `tor_detected`
Triggers when the IP is a Tor exit node.
```json
{"condition_value": {}}
```

### `ip_risk_score_gt`
Triggers when the composite risk score exceeds a threshold.
```json
{"condition_value": {"threshold": 70}}
```

### `velocity_exceeded`
Triggers when rate limit is exceeded for the current action.
```json
{"condition_value": {}}
```

### `multi_account`
Triggers when multi-account activity is detected on this IP.
```json
{"condition_value": {}}
```

### `blacklisted`
Triggers when the IP is on the blacklist.
```json
{"condition_value": {}}
```

### `country_code_in`
Triggers when the IP's country is in the provided list.
```json
{"condition_value": {"countries": ["RU", "CN", "KP", "IR"]}}
```

### `abuse_score_gt`
Triggers when AbuseIPDB confidence score exceeds threshold.
```json
{"condition_value": {"threshold": 60}}
```

### `fraud_score_gt`
Triggers when IPQS fraud score exceeds threshold.
```json
{"condition_value": {"threshold": 75}}
```

---

## Actions

| Action | Effect |
|--------|--------|
| `block` | Return HTTP 403. Add to temporary blacklist. |
| `challenge` | Flag for CAPTCHA or 2FA before proceeding. |
| `flag` | Log the event, allow request, mark for review. |
| `alert` | Send real-time alert via configured channels. |
| `allow` | Explicitly allow (overrides lower-priority rules). |

---

## Creating Rules via Django Admin

1. Go to **Admin → Proxy Intelligence → PI Fraud Rules**
2. Click **Add PI Fraud Rule**
3. Fill in the fields and save

---

## Creating Rules via Code

```python
from api.proxy_intelligence.models import FraudRule

# Block all Tor traffic
FraudRule.objects.create(
    name        = 'Block Tor Exit Nodes',
    rule_code   = 'BLOCK_TOR',
    condition_type  = 'tor_detected',
    condition_value = {},
    action      = 'block',
    priority    = 1,
    is_active   = True,
    tenant      = tenant,  # or None for global
)

# Challenge high-risk IPs
FraudRule.objects.create(
    name            = 'Challenge High Risk IPs',
    rule_code       = 'CHALLENGE_HIGH_RISK',
    condition_type  = 'ip_risk_score_gt',
    condition_value = {'threshold': 70},
    action          = 'challenge',
    priority        = 5,
    is_active       = True,
)

# Flag VPN users
FraudRule.objects.create(
    name            = 'Flag VPN Usage',
    rule_code       = 'FLAG_VPN',
    condition_type  = 'vpn_detected',
    condition_value = {},
    action          = 'flag',
    priority        = 10,
    is_active       = True,
)

# Block specific countries
FraudRule.objects.create(
    name            = 'Block High-Risk Countries',
    rule_code       = 'BLOCK_COUNTRY',
    condition_type  = 'country_code_in',
    condition_value = {'countries': ['KP', 'CU']},
    action          = 'block',
    priority        = 3,
    is_active       = True,
)
```

---

## Evaluating Rules in Code

```python
from api.proxy_intelligence.database_models.fraud_rule import FraudRuleManager
from api.proxy_intelligence.models import FraudRule

# Context dict built from an IP check result
context = {
    'is_vpn':              True,
    'is_proxy':            False,
    'is_tor':              False,
    'is_blacklisted':      False,
    'velocity_exceeded':   False,
    'multi_account':       False,
    'risk_score':          75,
}

manager = FraudRule.objects
triggered = FraudRuleManager.evaluate_all(manager, context, tenant=tenant)

for rule in triggered:
    print(f"Rule: {rule['rule']}, Action: {rule['action']}")
```

---

## Recommended Starter Ruleset

```
Priority  Code                    Condition          Action
1         BLOCK_TOR               tor_detected       block
2         BLOCK_CRITICAL_RISK     risk_score_gt:85   block
3         BLOCK_BLACKLISTED       blacklisted        block
5         CHALLENGE_HIGH_RISK     risk_score_gt:65   challenge
8         CHALLENGE_VPN           vpn_detected       challenge
10        FLAG_PROXY              proxy_detected     flag
15        FLAG_VELOCITY           velocity_exceeded  flag
20        FLAG_MULTI_ACCOUNT      multi_account      flag
25        FLAG_DATACENTER         (via services)     flag
99        ALLOW_WHITELIST         (handled first)    allow
```

---

## Rule Tuning Tips

- **Start permissive** — use `flag` before `block` until you trust accuracy
- **Monitor trigger_count** — rules that trigger 0 times may be misconfigured
- **Use tenant rules** for multi-tenant platforms to customise per-customer
- **Check last_triggered** regularly to confirm rules are firing
- **Disable instead of delete** — keep historical context

---

## Performance

- Rules are evaluated synchronously on every full IP check
- Keep the total active rule count under 50 for sub-millisecond evaluation
- Caching means most requests hit Redis, not the rule evaluator
- The middleware uses `quick_check` (cache-only) and only runs rules on `full_check`
