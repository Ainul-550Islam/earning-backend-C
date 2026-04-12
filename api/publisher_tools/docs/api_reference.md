# API Reference

## Base URL
```
https://publishertools.io/api/publisher-tools/
```

## Authentication

### Bearer Token (Session)
```
Authorization: Bearer {your_access_token}
```

### API Key
```
X-Publisher-Tools-Key: {api_key}
X-Publisher-Tools-Secret: {api_secret}
```

## Response Format

### Success
```json
{
    "success": true,
    "data": { ... },
    "message": "Optional message"
}
```

### Error
```json
{
    "success": false,
    "message": "Error description",
    "code": "error_code",
    "errors": { "field": ["Error detail"] }
}
```

### Paginated
```json
{
    "count": 100,
    "next": "https://...?page=2",
    "previous": null,
    "results": [...]
}
```

## Core Endpoints

### Publishers
| Method | Endpoint | Description |
|--------|---------|------------|
| GET | /publishers/ | List all publishers (admin) |
| POST | /publishers/ | Register publisher |
| GET | /publishers/{id}/ | Get publisher detail |
| PATCH | /publishers/{id}/ | Update publisher |
| GET | /publishers/{id}/stats/ | Dashboard stats |
| POST | /publishers/{id}/approve/ | Approve (admin) |
| POST | /publishers/{id}/regenerate_api_key/ | New API key |

### Sites
| Method | Endpoint | Description |
|--------|---------|------------|
| POST | /sites/ | Register site |
| GET | /sites/{id}/ | Site detail |
| POST | /sites/{id}/verify/ | Trigger verification |
| GET | /sites/{id}/analytics/ | Site analytics |

### Ad Units
| Method | Endpoint | Description |
|--------|---------|------------|
| POST | /ad-units/ | Create ad unit |
| GET | /ad-units/{id}/tag_code/ | Get JS tag |
| GET | /ad-units/{id}/performance/ | Performance stats |
| POST | /ad-units/{id}/pause/ | Pause unit |
| POST | /ad-units/{id}/activate/ | Activate unit |

### Earnings
| Method | Endpoint | Description |
|--------|---------|------------|
| GET | /earnings/ | List earnings |
| GET | /earnings/summary/ | Aggregated summary |
| GET | /earnings/by_country/ | Country breakdown |

### Analytics
| Method | Endpoint | Description |
|--------|---------|------------|
| GET | /analytics/?metric=revenue&dimension=date | Chart data |
| POST | /reports/custom/ | Custom report |
| GET | /reports/?type=daily | Pre-built reports |

## Pagination Parameters
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 200)
- `ordering`: Field to sort by (prefix with `-` for descending)

## Filter Parameters
Most list endpoints support:
- `status`: Filter by status
- `start_date` / `end_date`: Date range
- `search`: Text search
- `publisher_id`: Filter by publisher (admin only)

## Rate Limits

| Plan | Requests/min | Requests/day |
|------|-------------|-------------|
| Standard | 60 | 10,000 |
| Premium | 120 | 50,000 |
| Enterprise | Unlimited | Unlimited |

Rate limit headers:
- `X-RateLimit-Limit`: Requests allowed per minute
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## HTTP Status Codes
- `200` OK — Successful GET/PATCH
- `201` Created — Successful POST
- `204` No Content — Successful DELETE
- `400` Bad Request — Validation error
- `401` Unauthorized — Missing/invalid auth
- `403` Forbidden — Insufficient permissions
- `404` Not Found — Resource not found
- `429` Too Many Requests — Rate limited
- `500` Server Error — Internal error

## Webhooks
Configure at: `POST /webhooks/`

Available events:
- `impression.served`
- `click.valid` / `click.fraud_detected`
- `conversion.install` / `conversion.purchase`
- `invoice.created` / `invoice.paid`
- `fraud.high_risk_detected`
- `alert.*`

Signature verification:
```python
import hmac, hashlib
expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
is_valid = hmac.compare_digest(f'sha256={expected}', received_signature)
```
