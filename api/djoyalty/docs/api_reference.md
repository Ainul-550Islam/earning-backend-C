# API Reference — Djoyalty

Base URL: `/api/djoyalty/`
Authentication: Bearer token / Session auth required for all endpoints.

---

## 👥 Customers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/customers/` | List customers (search, filter, paginate) |
| POST | `/customers/` | Create customer |
| GET | `/customers/{id}/` | Customer detail (with transactions + events) |
| PUT/PATCH | `/customers/{id}/` | Update customer |
| DELETE | `/customers/{id}/` | Delete customer |
| GET | `/customers/{id}/stats/` | Transaction + points stats |
| GET | `/customers/{id}/ledger/` | Points ledger history |
| GET | `/customers/newsletter_subscribers/` | Newsletter list |

**Query params:** `?search=`, `?city=`, `?newsletter=true`, `?page=`, `?page_size=`

---

## 💳 Transactions

| Method | Endpoint | Description |
|---|---|---|
| GET | `/transactions/` | List transactions |
| POST | `/transactions/` | Create transaction |
| GET | `/transactions/{id}/` | Transaction detail |
| GET | `/transactions/summary/` | Total stats |

**Query params:** `?customer=`, `?type=full|discount|spending`, `?ordering=-timestamp`

---

## 📅 Events

| Method | Endpoint | Description |
|---|---|---|
| GET | `/events/` | List events |
| POST | `/events/` | Create event |
| GET | `/events/{id}/` | Event detail |
| GET | `/events/by_action/` | Grouped by action |

**Query params:** `?customer=`, `?action=`, `?anonymous=true`

---

## ⭐ Points

| Method | Endpoint | Description |
|---|---|---|
| GET | `/points/` | List all customer point balances |
| GET | `/points/balance/?customer_id=1` | Single customer balance |
| POST | `/points/earn/` | Earn points `{customer_id, spend_amount}` |
| POST | `/points/adjust/` | Admin adjust `{customer_id, points, reason}` (Admin only) |

---

## 📒 Ledger

| Method | Endpoint | Description |
|---|---|---|
| GET | `/ledger/` | All ledger entries |
| GET | `/ledger/{id}/` | Single entry |

**Query params:** `?customer=`, `?txn_type=credit|debit`, `?source=purchase`

---

## 🔄 Transfers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/transfers/` | Transfer history |
| POST | `/transfers/transfer/` | Transfer points `{from_customer_id, to_customer_id, points}` |

---

## 💹 Conversions

| Method | Endpoint | Description |
|---|---|---|
| GET | `/conversions/calculate/?points=100` | Points → currency |
| GET | `/conversions/calculate/?amount=50` | Currency → points |

---

## 🏆 Tiers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tiers/` | All tier definitions |
| GET | `/tiers/{id}/` | Tier detail with benefits |
| GET | `/user-tiers/?customer=1` | Customer's current tier |
| POST | `/user-tiers/evaluate/` | Re-evaluate tier `{customer_id}` |

---

## 📋 Earn Rules

| Method | Endpoint | Description |
|---|---|---|
| GET | `/earn-rules/` | All earn rules |
| POST | `/earn-rules/` | Create rule (Admin) |
| GET | `/earn-rules/active/` | Currently active rules |
| GET | `/bonus-events/?customer=1` | Bonus event history |
| POST | `/bonus-events/award/` | Award bonus `{customer_id, points, reason}` (Admin) |

---

## 🎁 Redemptions

| Method | Endpoint | Description |
|---|---|---|
| GET | `/redemptions/` | All redemption requests |
| POST | `/redemptions/redeem/` | Create request `{customer_id, points, redemption_type}` |
| POST | `/redemptions/{id}/approve/` | Approve (Admin) |
| POST | `/redemptions/{id}/reject/` | Reject `{reason}` (Admin) |

---

## 🎫 Vouchers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/vouchers/` | All vouchers |
| POST | `/vouchers/generate/` | Generate `{customer_id, voucher_type, discount_value}` (Admin) |
| POST | `/vouchers/use/` | Use voucher `{code, customer_id, order_reference}` |
| GET | `/vouchers/validate/?code=ABC` | Validate code |

---

## 🎁 Gift Cards

| Method | Endpoint | Description |
|---|---|---|
| GET | `/gift-cards/` | All gift cards |
| POST | `/gift-cards/issue/` | Issue `{value, customer_id, validity_days}` (Admin) |
| POST | `/gift-cards/redeem/` | Redeem `{code, amount}` |

---

## 🔥 Streaks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/streaks/` | All streaks (leaderboard style) |
| POST | `/streaks/record_activity/` | Record activity `{customer_id}` |

---

## 🏅 Badges

| Method | Endpoint | Description |
|---|---|---|
| GET | `/badges/` | All badge definitions |
| GET | `/badges/my_badges/?customer_id=1` | Customer's earned badges |

---

## ⚡ Challenges

| Method | Endpoint | Description |
|---|---|---|
| GET | `/challenges/` | All challenges |
| POST | `/challenges/{id}/join/` | Join `{customer_id}` |
| POST | `/challenges/{id}/update_progress/` | Update `{customer_id, value}` |

---

## 🏆 Leaderboard

| Method | Endpoint | Description |
|---|---|---|
| GET | `/leaderboard/top/?limit=10&period=all` | Top customers |

---

## 📣 Campaigns

| Method | Endpoint | Description |
|---|---|---|
| GET | `/campaigns/` | All campaigns |
| GET | `/campaigns/active/` | Currently running |
| POST | `/campaigns/{id}/join/` | Join `{customer_id}` |

---

## 📊 Insights (Admin)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/insights/` | All insight reports |
| POST | `/insights/generate/` | Generate today's report |

---

## 🔐 Admin Loyalty (Admin Only)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin-loyalty/customer_overview/?customer_id=1` | Full customer overview |
| POST | `/admin-loyalty/recalculate_tier/` | Force tier recalculate |
| GET | `/admin-loyalty/fraud_logs/` | Fraud logs |

---

## 🌐 Public API (Partner Merchants)

Header required: `X-Loyalty-API-Key: <partner_api_key>`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/balance/?customer_code=ABC` | Check balance |
| POST | `/public/earn/` | Earn via partner `{customer_code, spend_amount}` |

---

## Pagination
All list endpoints support:
- `?page=1&page_size=20` (default)
- `?limit=20&offset=0` (some endpoints)

## Response Format
```json
{
  "count": 100,
  "total_pages": 5,
  "current_page": 1,
  "next": "https://...",
  "previous": null,
  "results": [...]
}
```

## Error Format
```json
{
  "error": "insufficient_points",
  "message": "Insufficient loyalty points.",
  "available": "50",
  "required": "100"
}
```
