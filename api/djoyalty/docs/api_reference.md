# API Reference

Base URL: `/api/loyalty/`
Authentication: `Authorization: Bearer <token>` or Session

## Authentication Levels
- **Public**: `GET` read-only endpoints
- **Authenticated**: Standard user
- **Admin**: `IsLoyaltyAdmin` (staff/superuser)
- **Partner API**: `X-Loyalty-API-Key: <key>` header

---

## Customers

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/customers/` | Auth | List customers |
| POST | `/customers/` | Auth | Create customer |
| GET | `/customers/{id}/` | Auth | Customer detail |
| GET | `/customers/{id}/stats/` | Auth | Full stats |
| GET | `/customers/{id}/ledger/` | Auth | Points history |
| POST | `/customers/{id}/deactivate/` | Admin | Soft delete |
| POST | `/customers/{id}/reactivate/` | Admin | Reactivate |

---

## Points

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/points/?customer_id=X` | Auth | Balance |
| GET | `/points/balance/?customer_id=X` | Auth | Quick balance |
| POST | `/points/earn/` | Auth | Earn points |
| POST | `/points/adjust/` | Admin | Manual adjust |
| GET | `/ledger/?customer=X` | Auth | Ledger history |
| POST | `/transfers/transfer/` | Auth | P2P transfer |
| GET | `/conversions/calculate/` | Auth | Rate calculator |

---

## Tiers

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/tiers/` | Auth | All tiers |
| GET | `/user-tiers/my_tier/?customer_id=X` | Auth | My tier info |
| POST | `/user-tiers/evaluate/` | Auth | Re-evaluate |
| GET | `/user-tiers/history/?customer_id=X` | Auth | Tier history |
| GET | `/user-tiers/progress/?customer_id=X` | Auth | Upgrade progress |
| POST | `/user-tiers/force_upgrade/` | Admin | Force upgrade |
| POST | `/user-tiers/force_downgrade/` | Admin | Force downgrade |

---

## Earn Rules

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/earn-rules/` | Auth | All rules |
| GET | `/earn-rules/active/` | Auth | Active rules |
| POST | `/earn-rules/` | Admin | Create rule |
| POST | `/bonus-events/award/` | Admin | Manual bonus |

---

## Redemption

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/redemptions/redeem/` | Auth | Redeem points |
| GET | `/redemptions/?customer=X` | Auth | History |
| POST | `/redemptions/{id}/approve/` | Admin | Approve |
| POST | `/redemptions/{id}/reject/` | Admin | Reject |
| POST | `/vouchers/generate/` | Admin | Issue voucher |
| POST | `/vouchers/use/` | Auth | Use voucher |
| GET | `/vouchers/validate/?code=X` | Auth | Validate |
| POST | `/gift-cards/issue/` | Admin | Issue card |
| POST | `/gift-cards/redeem/` | Auth | Redeem card |

---

## Engagement

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/streaks/record_activity/` | Auth | Record activity |
| GET | `/badges/` | Auth | All badges |
| GET | `/badges/my_badges/?customer_id=X` | Auth | My badges |
| POST | `/challenges/{id}/join/` | Auth | Join challenge |
| POST | `/challenges/{id}/update_progress/` | Auth | Update progress |
| GET | `/leaderboard/top/` | Auth | Top customers |
| GET | `/milestones/my_milestones/?customer_id=X` | Auth | My milestones |

---

## Campaigns

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/campaigns/active/` | Auth | Active campaigns |
| POST | `/campaigns/{id}/join/` | Auth | Join campaign |

---

## Partners (Coalition)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/partners/` | Auth | All partners |
| POST | `/partners/{id}/earn/` | Partner API Key | Earn at partner |
| GET | `/partners/coalition_history/` | Auth | Coalition history |
| POST | `/partners/reverse_earn/` | Admin | Reverse earn |
| GET | `/partners/{id}/stats/` | Admin | Partner stats |

---

## Admin

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/admin/customer_overview/` | Admin | Customer detail |
| POST | `/admin/recalculate_tier/` | Admin | Force tier recalc |
| GET | `/admin/fraud_logs/` | Admin | Fraud log list |
| POST | `/insights/generate/` | Admin | Generate report |

---

## Public API (Partner Integration)

```
Header: X-Loyalty-API-Key: <partner_api_key>
```

| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/balance/?customer_code=X` | Get balance |
| POST | `/public/earn/` | Earn points |

---

## Error Codes

| Code | Meaning |
|---|---|
| `INSUFFICIENT_POINTS` | Not enough points |
| `REDEMPTION_MINIMUM_NOT_MET` | Below minimum |
| `VOUCHER_EXPIRED` | Voucher expired |
| `VOUCHER_ALREADY_USED` | Already redeemed |
| `CAMPAIGN_INACTIVE` | Campaign not active |
| `PARTNER_NOT_FOUND` | Invalid API key |
| `FRAUD_DETECTED` | Transaction blocked |
| `TIER_NOT_FOUND` | Invalid tier name |

---

## Webhook Events

Subscribe via `WebhookRegistry.register()`:

```python
from djoyalty.webhooks.webhook_registry import WebhookRegistry
WebhookRegistry.register(
    url='https://yoursite.com/webhooks/loyalty',
    events=['points.earned', 'tier.upgraded', 'badge.unlocked'],
    secret='your_signing_secret',
)
```

Events: `points.earned`, `points.burned`, `points.expired`, `tier.changed`,
`badge.unlocked`, `streak.milestone`, `redemption.status_changed`,
`campaign.joined`, `challenge.completed`, `voucher.used`, `fraud.detected`
