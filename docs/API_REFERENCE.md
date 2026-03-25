# 📡 API Reference

> **Interactive Docs**: `https://your-domain.com/api/docs/`
> All endpoints require `X-API-Key` header for tenant identification.

---

## Authentication

### Register
```
POST /api/auth/register/
```
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "referral_code": "ABC123"
}
```
**Response:**
```json
{
  "user": { "id": 1, "email": "john@example.com" },
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

---

### Login
```
POST /api/auth/login/
```
```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```
**Response:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "username": "john_doe"
  }
}
```

---

### Refresh Token
```
POST /api/auth/token/refresh/
```
```json
{ "refresh": "eyJ..." }
```

---

### Verify OTP
```
POST /api/auth/otp/verify/
```
```json
{
  "email": "john@example.com",
  "code": "123456",
  "otp_type": "registration"
}
```

---

## Wallet

### Get Balance
```
GET /api/wallet/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "current_balance": "45.50",
  "pending_balance": "12.00",
  "total_earned": "200.00",
  "total_withdrawn": "142.50",
  "frozen_balance": "0.00",
  "bonus_balance": "5.00",
  "currency": "BDT"
}
```

---

### Transaction History
```
GET /api/wallet/transactions/?page=1&page_size=20
Authorization: Bearer <token>
```

---

### Request Withdrawal
```
POST /api/wallet/withdraw/
Authorization: Bearer <token>
```
```json
{
  "amount": "50.00",
  "payment_method": "bkash",
  "account_number": "01XXXXXXXXX"
}
```

---

## Offers & Tasks

### List Offers
```
GET /api/offers/?category=survey&page=1
Authorization: Bearer <token>
```

---

### Complete Offer
```
POST /api/offers/{id}/complete/
Authorization: Bearer <token>
```
```json
{
  "screenshot": "<base64 or file>",
  "proof_url": "https://..."
}
```

---

### List Tasks
```
GET /api/tasks/
Authorization: Bearer <token>
```

---

### Submit Task
```
POST /api/tasks/{id}/submit/
Authorization: Bearer <token>
```
```json
{
  "proof": "screenshot or url",
  "notes": "optional notes"
}
```

---

## Referral

### Get Referral Info
```
GET /api/referral/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "referral_code": "JOHN50",
  "referral_link": "https://app.com/join/JOHN50",
  "total_referrals": 12,
  "total_earned": "60.00",
  "pending_earned": "10.00"
}
```

---

### Apply Referral Code
```
POST /api/referral/apply/
Authorization: Bearer <token>
```
```json
{ "code": "FRIEND123" }
```

---

## Gamification

### Leaderboard
```
GET /api/gamification/leaderboard/?period=weekly
Authorization: Bearer <token>
```
**Response:**
```json
{
  "results": [
    { "rank": 1, "username": "top_user", "points": 5000, "earnings": "250.00" },
    { "rank": 2, "username": "second_user", "points": 4500, "earnings": "225.00" }
  ]
}
```

---

### User Points
```
GET /api/gamification/points/
Authorization: Bearer <token>
```

---

### User Badges
```
GET /api/gamification/badges/
Authorization: Bearer <token>
```

---

## Notifications

### List Notifications
```
GET /api/notifications/?is_read=false
Authorization: Bearer <token>
```

---

### Register Device Token (FCM)
```
POST /api/notifications/device-token/
Authorization: Bearer <token>
```
```json
{
  "token": "fcm-device-token-here",
  "platform": "android"
}
```

---

### Mark as Read
```
PATCH /api/notifications/{id}/
Authorization: Bearer <token>
```
```json
{ "is_read": true }
```

---

## KYC

### Submit KYC
```
POST /api/kyc/submit/
Authorization: Bearer <token>
Content-Type: multipart/form-data
```
```
document_type=nid
front_image=<file>
back_image=<file>
```

---

### KYC Status
```
GET /api/kyc/status/
Authorization: Bearer <token>
```
**Response:**
```json
{
  "status": "pending",
  "submitted_at": "2026-03-24T10:00:00Z",
  "reviewed_at": null
}
```

---

## White-label (Tenant)

### Get App Branding
```
GET /api/tenants/my_tenant/
X-API-Key: <tenant-api-key>
```
**Response:**
```json
{
  "name": "MyEarningApp",
  "app_name": "MyEarningApp",
  "logo": "https://cdn.example.com/logo.png",
  "primary_color": "#FF5733",
  "secondary_color": "#222222",
  "plan": "pro",
  "enable_referral": true,
  "enable_offerwall": true,
  "enable_kyc": true,
  "enable_leaderboard": true,
  "min_withdrawal": "10.00"
}
```

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Bad Request — check request body |
| 401 | Unauthorized — invalid/expired token |
| 403 | Forbidden — no permission |
| 404 | Not Found |
| 429 | Too Many Requests — rate limited |
| 500 | Server Error |

**Error format:**
```json
{
  "error": "Error message here",
  "detail": "More details if available"
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Login | 5/minute per IP |
| Register | 3/minute per IP |
| OTP | 3/minute per user |
| General API | 100/minute per user |
| Offer complete | 10/minute per user |
