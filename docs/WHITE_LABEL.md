# 🏢 White-label Setup Guide

## How White-label Works

```
Your Server (one backend)
├── Tenant A → myapp.com → Blue theme, logo A
├── Tenant B → theirapp.com → Red theme, logo B
└── Tenant C → anotherdomain.com → Green theme, logo C

Each tenant has:
✅ Own users (data isolated)
✅ Own wallet transactions
✅ Own branding (logo, colors)
✅ Own feature settings
✅ Own payout rules
✅ Own API key
```

---

## Creating a New Client (Tenant)

### Via Command Line
```bash
python manage.py seed_tenant
```

### Via Admin Panel
1. Go to `/admin/`
2. Click **Tenants → Add Tenant**
3. Fill in: Name, Domain, Plan
4. Save → API Key auto-generated

### Via API
```bash
POST /api/tenants/
Authorization: Bearer <admin-token>

{
  "name": "Client Company",
  "domain": "client-domain.com",
  "plan": "pro",
  "admin_email": "admin@client.com",
  "primary_color": "#FF5733",
  "secondary_color": "#333333",
  "max_users": 1000
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Client Company",
  "api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "plan": "pro"
}
```

---

## Configuring Client Branding

```bash
PATCH /api/tenants/1/update_branding/
Authorization: Bearer <admin-token>
Content-Type: multipart/form-data

name=ClientApp
primary_color=#FF5733
secondary_color=#222222
logo=<image-file>
```

---

## Configuring Client Features

```bash
PATCH /api/tenants/1/update_features/
Authorization: Bearer <admin-token>

{
  "app_name": "ClientApp",
  "enable_referral": true,
  "enable_offerwall": true,
  "enable_kyc": false,
  "enable_leaderboard": true,
  "enable_chat": false,
  "min_withdrawal": 10.00,
  "withdrawal_fee_percent": 2.5,
  "support_email": "help@client.com",
  "privacy_policy_url": "https://client.com/privacy",
  "terms_url": "https://client.com/terms",
  "android_package_name": "com.client.earningapp",
  "firebase_server_key": "your-firebase-key"
}
```

---

## React Native App Using Tenant API Key

```javascript
// All API calls include tenant API key in header
const headers = {
  'X-API-Key': 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
  'Content-Type': 'application/json',
};

// App startup — load branding from server
const loadBranding = async () => {
  const res = await fetch(`${BASE_URL}/api/tenants/my_tenant/`, { headers });
  const data = await res.json();
  
  // Apply tenant branding to app
  setTheme({
    primary: data.primary_color,    // "#FF5733"
    secondary: data.secondary_color, // "#222222"
    logo: data.logo,                 // "https://..."
    appName: data.app_name,          // "ClientApp"
  });
  
  // Enable/disable features
  setFeatures({
    referral: data.enable_referral,
    offerwall: data.enable_offerwall,
    kyc: data.enable_kyc,
    leaderboard: data.enable_leaderboard,
  });
};
```

---

## Plan Limits

| Plan | Max Users | Monthly Price |
|------|-----------|---------------|
| Basic | 100 | $49 |
| Pro | 1,000 | $99 |
| Enterprise | Unlimited | $299 |

### Checking if user limit reached
```bash
GET /api/tenants/1/dashboard/

Response:
{
  "total_users": 95,
  "user_limit": 100,
  "user_limit_reached": false,
  "billing_status": "active"
}
```

---

## Tenant Dashboard Stats

```bash
GET /api/tenants/1/dashboard/
Authorization: Bearer <admin-token>

Response:
{
  "tenant": "Client Company",
  "plan": "pro",
  "total_users": 523,
  "active_users": 498,
  "user_limit": 1000,
  "user_limit_reached": false,
  "billing_status": "active",
  "trial_ends_at": null,
  "subscription_ends_at": "2026-12-31T00:00:00Z"
}
```

---

## Regenerating API Key

```bash
POST /api/tenants/1/regenerate_api_key/
Authorization: Bearer <admin-token>

Response:
{
  "api_key": "new-uuid-key-here"
}
```

---

## Suspending a Tenant

```bash
POST /api/tenants/1/toggle_active/
Authorization: Bearer <admin-token>

Response:
{
  "success": true,
  "is_active": false,
  "message": "Tenant suspended"
}
```
