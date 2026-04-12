# Fraud Detection Rules

## Score Thresholds

| Score | Action |
|---|---|
| 0–39 | Allow |
| 40–59 | Allow + flag for review |
| 60–79 | Reject + log FraudAttemptLog |
| 80–89 | Reject + alert ops |
| 90–100 | Reject + auto-blacklist IP |

## Velocity Rules

| Rule | Threshold | Window | Action |
|---|---|---|---|
| IP conversions | > 5 | 60 seconds | Hard block |
| IP conversions | > 50 | 1 hour | Flag |
| IP conversions | > 200 | 24 hours | Hard block |
| User conversions | > 20 | 1 hour | Flag |
| Network postbacks | > rate_limit/min | 60 seconds | Hard block |
| Device clicks | > 30 | 1 hour | Flag |

## Bot Detection

The following User-Agent patterns are blocked:
- Known crawlers: Googlebot, Bingbot, etc.
- Automation tools: curl, wget, python-requests, etc.
- Headless browsers: PhantomJS, Headless Chrome, Selenium
- Empty/missing User-Agent

## Fraud Score Weights

| Signal | Score | Weight |
|---|---|---|
| Blacklisted IP | 100 | 2.0 (instant block) |
| Bot User-Agent | 95 | 1.5 |
| Emulator device | 85 | 1.5 |
| Proxy/VPN/Tor | 65 | 1.2 |
| Fast conversion (< 3s) | 95 | 1.5 |
| Fast conversion (< 30s) | 50 | 1.0 |
| High velocity IP | 70–80 | 1.0 |

## Configuring Custom Thresholds

```python
POSTBACK_ENGINE = {
    "FRAUD_FLAG_THRESHOLD": 60,
    "FRAUD_BLOCK_THRESHOLD": 80,
    "FRAUD_AUTO_BLACKLIST": 90,
    "MAX_IP_CONVERSIONS_PER_MINUTE": 5,
    "MAX_IP_CONVERSIONS_PER_HOUR": 50,
}
```
