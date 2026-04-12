# Site Integration Guide

## Step 1: Register Your Site

```bash
POST /api/publisher-tools/sites/
{
    "name": "My Blog",
    "domain": "myblog.com",
    "url": "https://myblog.com",
    "category": "blog",
    "language": "en",
    "content_rating": "G"
}
```

## Step 2: Verify Domain Ownership

### Method 1: ads.txt (Recommended)
Add this line to `https://yourdomain.com/ads.txt`:
```
ads.publishertools.io, PUB000001, DIRECT, f08c47fec0942fa0
```

### Method 2: HTML Meta Tag
Add to your `<head>` section:
```html
<meta name="publisher-verification" content="YOUR_VERIFICATION_TOKEN">
```

### Method 3: DNS TXT Record
Add DNS TXT record:
- **Host**: `@` or `yourdomain.com`
- **Value**: `publisher-verification=YOUR_TOKEN`

### Trigger Verification
```bash
POST /api/publisher-tools/sites/{site_id}/verify/
{
    "method": "ads_txt"
}
```

## Step 3: Add Ad Tag to Site

```html
<!-- Publisher Tools Ad Tag -->
<script async src="https://cdn.publishertools.io/pt.js"></script>
<div id="pt-ad-UNIT000001"></div>
<script>
  ptq.push({unitId: 'UNIT000001', container: 'pt-ad-UNIT000001'});
</script>
```

## Site Quality Requirements

| Requirement | Minimum |
|-------------|---------|
| Content Rating | G or PG |
| Viewability | > 50% |
| IVT Rate | < 20% |
| Page Speed | > 50 (Google PSI) |
| Privacy Policy | Required |
| Terms of Service | Required |

## ads.txt Requirements
- Must be accessible at `https://yourdomain.com/ads.txt`
- Must include the Publisher Tools line
- Plain text format
- Updated within 48 hours of changes

## Content Prohibited
- Adult / pornographic content
- Hate speech or discrimination
- Violence or gore
- Illegal content
- Malware or phishing
- Copyright infringement
