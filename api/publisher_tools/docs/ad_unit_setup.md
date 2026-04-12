# Ad Unit Setup Guide

## Ad Formats Overview

| Format | Best For | Typical eCPM |
|--------|---------|-------------|
| Rewarded Video | Games, apps | $5-15 |
| Interstitial | Apps, games | $3-10 |
| Native | News, blogs | $2-8 |
| Video (Outstream) | News, blogs | $3-8 |
| Rectangle (300x250) | All sites | $1-5 |
| Leaderboard (728x90) | Desktop | $0.5-3 |
| Mobile Banner (320x50) | Mobile apps | $0.3-2 |

## Creating an Ad Unit

```bash
POST /api/publisher-tools/ad-units/
{
    "name": "Homepage Leaderboard",
    "inventory_type": "site",
    "site": "SITE000001",
    "format": "leaderboard",
    "width": 728,
    "height": 90,
    "is_responsive": true,
    "floor_price": "0.50"
}
```

## Floor Price Best Practices
- Set floor price = 70-80% of your average eCPM
- Too high = low fill rate
- Too low = leaving money on the table
- Use geo-based floors (US/EU worth 3-5x Bangladesh)

## Responsive Ads
```javascript
// Auto-size based on container
ptq.push({
    unitId: 'UNIT000001',
    container: 'ad-container',
    responsive: true,
    // Will use: 728x90 on desktop, 320x50 on mobile
});
```

## Frequency Capping
Recommended settings:
- **Banner**: max 10/day, 3/session
- **Interstitial**: max 3/day, 2/session
- **Rewarded Video**: max 5/day, 3/session

## Targeting Rules

### Geographic Targeting
```bash
POST /api/publisher-tools/ad-units/{unit_id}/targeting/
{
    "target_countries": ["US", "GB", "CA", "AU"],
    "device_type": "all",
    "is_active": true
}
```

### Device Targeting
- `mobile`: Phones only
- `tablet`: Tablets only
- `desktop`: Desktop browsers
- `all`: All devices

## Testing Your Ad Unit
1. Enable test mode: `"is_test_mode": true`
2. Add test device: Settings → Test Devices
3. Verify ad renders correctly
4. Check impression fires in dashboard
5. Disable test mode before going live
