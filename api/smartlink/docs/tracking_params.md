# SmartLink Tracking Parameters Guide

## Sub ID Parameters (sub1–sub5)

SmartLink supports 5 tracking sub-parameters that pass through the redirect chain to the offer URL.

### URL Format
```
https://go.example.com/abc123/?sub1=VALUE&sub2=VALUE&sub3=VALUE&sub4=VALUE&sub5=VALUE
```

### Parameter Aliases (all map to sub1–sub5)

| Alias | Maps To | Common Use |
|---|---|---|
| `sub1` / `s1` / `aff_sub` / `source` | sub1 | Campaign ID / Source |
| `sub2` / `s2` / `aff_sub2` / `campaign` | sub2 | Ad Set / Campaign Name |
| `sub3` / `s3` / `aff_sub3` / `adgroup` | sub3 | Ad Group / Creative |
| `sub4` / `s4` / `aff_sub4` / `keyword` | sub4 | Keyword / Placement |
| `sub5` / `s5` / `aff_sub5` / `placement` | sub5 | Custom / Publisher Ref |

### Example Postback Configuration

When a conversion fires, advertisers send back sub1 to identify the click:
```
Offer Postback URL: https://go.example.com/postback/?click_id={sub1}&payout={payout}&offer_id={offer_id}&token={token}
```

### Publisher Tracking Example

Facebook Ads → SmartLink → Offer:
```
https://go.example.com/abc123/?sub1={campaign.id}&sub2={adset.id}&sub3={ad.id}&sub4={{site_source_name}}
```

Google Ads → SmartLink → Offer:
```
https://go.example.com/abc123/?sub1={campaignid}&sub2={adgroupid}&sub3={creative}&sub4={keyword}&sub5={placement}
```

### Value Constraints
- Max length: 255 characters per sub
- Allowed: `[a-zA-Z0-9_-]`
- All other characters are stripped (sanitized automatically)

---

## Custom Parameters

Any URL parameter not in the reserved list is captured as a custom parameter:
```
https://go.example.com/abc123/?sub1=camp1&utm_source=google&utm_medium=cpc
```
→ `utm_source` and `utm_medium` are stored in `ClickMetadata.custom_params` (JSON field).

---

## Macro Replacement

The following macros are available in offer URLs and postback URLs:

| Macro | Value |
|---|---|
| `{click_id}` | Click primary key |
| `{smartlink_slug}` | SmartLink slug |
| `{offer_id}` | Offer ID |
| `{publisher_id}` | Publisher ID |
| `{country}` | 2-letter ISO country code |
| `{device}` | mobile / tablet / desktop |
| `{os}` | android / ios / windows / mac |
| `{sub1}` through `{sub5}` | Sub ID values |
| `{payout}` | Conversion payout amount |
