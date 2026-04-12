# Network Integration Guide

## Quick Setup for New Network

1. Create `AdNetworkConfig` in Admin
2. Set `network_key` (e.g. `cpalead`)
3. Set `secret_key` for HMAC verification
4. Add server IP addresses to `ip_whitelist`
5. Configure `postback_url_template` for outbound confirmation

## Postback URL Format

Give the network this URL:
```
https://yourdomain.com/api/postback_engine/postback/{network_key}/
```

With macros from their platform (e.g. CPALead):
```
https://yourdomain.com/api/postback_engine/postback/cpalead/?sub1={sub1}&amount={amount}&oid={oid}&sid={sid}
```

## Supported Networks

| Network | Key | Status Field | Payout Field |
|---|---|---|---|
| CPALead | `cpalead` | `status` (1/0) | `amount` |
| AdGate Media | `adgate` | `status` | `reward` |
| OfferToro | `offertoro` | `type` (1/2/3) | `amount` |
| Adscend Media | `adscend` | `status` | `amount` |
| Revenue Wall | `revenuewall` | `status` | `payout` |
| AppLovin MAX | `applovin` | (auto-approved) | `amount` |
| Unity Ads | `unity` | (auto-approved) | `value` |
| IronSource | `ironsource` | (auto-approved) | `rewardAmount` |
| AdMob SSV | `admob` | (auto-approved) | `reward_amount` |
| Facebook AN | `facebook` | (auto-approved) | `reward_amount` |
| TikTok | `tiktok` | `complete`/`failed` | `value` |
| Impact | `impact` | `ActionStatus` | `Payout` |
| CAKE | `cake` | `status` | `payout` |
| HasOffers | `hasoffers` | `status` | `payout` |
| LinkTrust | `linktrust` | `status` | `amount` |
| Everflow | `everflow` | `status` | `payout` |

## Field Mapping

Configure custom field mapping in `AdNetworkConfig.field_mapping`:
```json
{
  "lead_id": "custom_uid",
  "payout": "commission",
  "offer_id": "campaign"
}
```

## Signature Verification

Set `signature_algorithm` on the network config:
- `hmac_sha256` — Standard HMAC-SHA256 (recommended)
- `hmac_sha512` — HMAC-SHA512
- `hmac_md5` — HMAC-MD5 (legacy)
- `sha256` — Plain SHA-256 hash (AppLovin)
- `ecdsa` — ECDSA (Google AdMob)
- `none` — Disabled (IP whitelist only)
