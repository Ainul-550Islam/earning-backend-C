# Getting Started — Publisher Tools

## What is Publisher Tools?

Publisher Tools is a **complete ad monetization platform** for publishers — comparable to CPAlead, AdMob, and PropellerAds. It gives you everything needed to monetize websites, mobile apps, and digital content through multiple ad formats and revenue models.

**Revenue models supported:**
- CPM (Cost Per Mille) — display ads
- CPC (Cost Per Click) — search/contextual ads
- CPA (Cost Per Action) — affiliate/offerwall
- CPI (Cost Per Install) — mobile installs
- CPV (Cost Per View) — video ads

---

## Quick Start (5 Steps)

### Step 1: Create Your Publisher Account

```bash
POST /api/publisher-tools/publishers/
Content-Type: application/json
Authorization: Bearer {your_token}

{
    "display_name": "My Media Company",
    "business_type": "company",
    "contact_email": "contact@mymedia.com",
    "country": "Bangladesh",
    "agree_to_terms": true
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "publisher_id": "PUB000001",
        "status": "pending",
        "api_key": "pt_live_xxxxxxxx"
    }
}
```

### Step 2: Register Your Site or App

**Website:**
```bash
POST /api/publisher-tools/sites/
{
    "name": "Tech Blog BD",
    "domain": "techblogbd.com",
    "url": "https://techblogbd.com",
    "category": "technology"
}
```

**Mobile App:**
```bash
POST /api/publisher-tools/apps/
{
    "name": "My Game",
    "platform": "android",
    "package_name": "com.mygame.app",
    "category": "games"
}
```

### Step 3: Verify Ownership

Add to `https://techblogbd.com/ads.txt`:
```
ads.publishertools.io, PUB000001, DIRECT, f08c47fec0942fa0
```

Then trigger verification:
```bash
POST /api/publisher-tools/sites/{site_id}/verify/
{ "method": "ads_txt" }
```

### Step 4: Create Ad Units

```bash
POST /api/publisher-tools/ad-units/
{
    "name": "Homepage Banner",
    "inventory_type": "site",
    "site": "{site_id}",
    "format": "banner",
    "width": 728,
    "height": 90,
    "floor_price": "0.50"
}
```

### Step 5: Add Ad Tag to Your Site

```html
<!-- Publisher Tools — Async Ad Tag -->
<script async src="https://cdn.publishertools.io/pt.js"
        data-publisher-id="PUB000001"></script>

<!-- Ad placement -->
<div id="pt-ad-UNIT000001"></div>
<script>
  window.ptq = window.ptq || [];
  ptq.push({ unitId: 'UNIT000001', container: 'pt-ad-UNIT000001' });
</script>
```

---

## Authentication

### Option 1: Bearer Token (Recommended for web)
```
Authorization: Bearer {your_jwt_access_token}
```

### Option 2: API Key (For server-to-server)
```
X-Publisher-Tools-Key: {api_key}
X-Publisher-Tools-Secret: {api_secret}
```

Regenerate API key anytime:
```bash
POST /api/publisher-tools/publishers/{id}/regenerate_api_key/
```

---

## Supported Ad Formats

| Format | Web | Android | iOS | eCPM Range |
|--------|-----|---------|-----|-----------|
| Banner (728×90) | ✅ | ✅ | ✅ | $0.30–$2 |
| Rectangle (300×250) | ✅ | ✅ | ✅ | $0.50–$3 |
| Mobile Banner (320×50) | ✅ | ✅ | ✅ | $0.20–$1 |
| Interstitial | ✅ | ✅ | ✅ | $2–$10 |
| Rewarded Video | — | ✅ | ✅ | $5–$15 |
| Native | ✅ | ✅ | ✅ | $1–$8 |
| Offerwall | — | ✅ | ✅ | $3–$12 |
| Video (Outstream) | ✅ | — | — | $2–$8 |

---

## Payment Methods (Bangladesh Publishers)

| Method | Min Payout | Speed |
|--------|-----------|-------|
| bKash | $5 (~550৳) | 1-2 days |
| Nagad | $5 (~550৳) | 1-2 days |
| Rocket | $5 (~550৳) | 1-2 days |
| PayPal | $10 | 1-3 days |
| Payoneer | $50 | 2-5 days |
| Bank Transfer | $100 | 5-10 days |
| USDT (TRC-20) | $10 | Same day |

---

## Revenue Share

| Tier | Share | Minimum Monthly |
|------|-------|----------------|
| Standard | 70% | Any |
| Premium | 75% | $500+ |
| Enterprise | 80%+ | Custom |

---

## SDK Integration

### Android
```gradle
implementation 'io.publishertools:android-sdk:1.0.0'
```
```java
// In Application.onCreate()
PublisherTools.initialize(this, "PUB000001");
```

### iOS
```ruby
pod 'PublisherToolsSDK'
```
```swift
PublisherTools.initialize(publisherId: "PUB000001")
```

### React / Next.js
```bash
npm install @publisher-tools/react-sdk
```
```jsx
import { AdUnit } from '@publisher-tools/react-sdk';
<AdUnit unitId="UNIT000001" format="banner" />
```

---

## Dashboard Access

After approval, access your full dashboard:
- 📊 **Real-time earnings** — Live impression/click/revenue data
- 🌍 **Geo analytics** — Revenue by country, device, time
- 🛡️ **IVT monitoring** — Invalid traffic alerts
- 💰 **Invoice history** — Monthly statements
- ⚙️ **Mediation control** — Waterfall & header bidding

---

## Rate Limits

| Plan | API Calls/min |
|------|-------------|
| Standard | 60 |
| Premium | 120 |
| Enterprise | Unlimited |

---

## Support

- 📧 Email: publisher-support@publishertools.io
- 📖 Docs: https://docs.publishertools.io
- 💬 Chat: Available in dashboard (Premium+)
- 🕐 Response: Standard 48h, Premium 24h, Enterprise 4h
