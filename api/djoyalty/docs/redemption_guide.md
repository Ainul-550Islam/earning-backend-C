# Redemption Guide

## Redemption Types

| Type | Description |
|---|---|
| `cashback` | Points → cash value |
| `voucher` | Points → discount voucher |
| `product` | Points → free product |
| `gift` | Points → gift item |
| `donation` | Points → charity donation |

## Minimum Redemption
Default: `MIN_REDEMPTION_POINTS = 100`

## Redeem Points
```http
POST /api/loyalty/redemptions/redeem/
{
  "customer_id": 1,
  "points": 500,
  "redemption_type": "cashback"
}
Response: {
  "id": 42,
  "status": "pending",
  "points_used": "500.00",
  "reward_value": "5.00"
}
```

## Approval Flow
1. Customer submits request → `pending`
2. Admin reviews → `approved` / `rejected`
3. System fulfills → `fulfilled`

Auto-approve for requests ≤ `REDEMPTION_AUTO_APPROVE_THRESHOLD` (1000 pts).

```http
POST /api/loyalty/redemptions/42/approve/
POST /api/loyalty/redemptions/42/reject/
{ "reason": "Suspicious activity" }
```

## Vouchers

### Generate Voucher
```http
POST /api/loyalty/vouchers/generate/
{
  "customer_id": 1,
  "voucher_type": "percent",
  "discount_value": 15,
  "validity_days": 30
}
```

### Use Voucher
```http
POST /api/loyalty/vouchers/use/
{
  "code": "ABCD1234",
  "customer_id": 1,
  "order_reference": "ORD-2024-001"
}
```

### Validate Voucher
```http
GET /api/loyalty/vouchers/validate/?code=ABCD1234
Response: { "valid": true, "voucher_type": "percent", "discount_value": "15.00" }
```

## Gift Cards

### Issue Gift Card
```http
POST /api/loyalty/gift-cards/issue/
{
  "value": 500,
  "customer_id": 1,
  "validity_days": 365
}
```

### Redeem Gift Card
```http
POST /api/loyalty/gift-cards/redeem/
{
  "code": "ABCD-1234-EFGH-5678",
  "amount": 200
}
```

## Cashout (Points → Bank/Mobile)

### Setup Bank Account
```http
POST /api/loyalty/cashout/bank-accounts/
{
  "bank_name": "Dutch-Bangla Bank",
  "account_number": "1234567890",
  "account_holder_name": "John Doe"
}
```

### Cashout via bKash
```http
POST /api/loyalty/cashout/request/
{
  "customer_id": 1,
  "points_to_redeem": 1000,
  "cashout_method": "mobile_wallet",
  "mobile_wallet_id": 3
}
```

Default rate: **100 points = 1 BDT**

## Reward Catalog
```http
GET /api/loyalty/customers/1/available_rewards/
```
Shows all rewards the customer can currently afford.
