# Webhooks API Reference

This document provides complete API reference for the webhooks system,
including all endpoints, request/response formats, and usage examples.

## 📋 Table of Contents

- [Core Endpoints](#core-endpoints)
- [Advanced Endpoints](#advanced-endpoints)
- [Inbound Endpoints](#inbound-endpoints)
- [Analytics Endpoints](#analytics-endpoints)
- [Replay Endpoints](#replay-endpoints)
- [Admin Endpoints](#admin-endpoints)
- [Authentication](#authentication)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)
- [Webhook Format](#webhook-format)
- [Examples](#examples)

## 🌐 Core Endpoints

### Webhook Endpoints

#### `GET /api/v1/webhooks/endpoints/`
List all webhook endpoints.

**Request:**
```json
{
  "page": 1,
  "page_size": 20,
  "status": "active|paused|disabled|suspended",
  "search": "string"
}
```

**Response:**
```json
{
  "count": 100,
  "next": "https://api.example.com/api/v1/webhooks/endpoints/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "url": "https://example.com/webhook",
      "status": "active",
      "event_types": ["user.created", "wallet.transaction.created"],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/webhooks/endpoints/`
Create a new webhook endpoint.

**Request:**
```json
{
  "url": "https://example.com/webhook",
  "secret": "your-webhook-secret",
  "event_types": ["user.created", "wallet.transaction.created"],
  "http_method": "POST",
  "timeout_seconds": 30,
  "max_retries": 3,
  "ip_whitelist": ["192.168.1.1", "10.0.0.1"],
  "headers": {
    "Content-Type": "application/json",
    "X-Custom-Header": "custom-value"
  }
}
```

**Response:**
```json
{
  "id": 1,
  "url": "https://example.com/webhook",
  "status": "active",
  "event_types": ["user.created", "wallet.transaction.created"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### `GET /api/v1/webhooks/endpoints/{id}/`
Retrieve a specific webhook endpoint.

**Response:**
```json
{
  "id": 1,
  "url": "https://example.com/webhook",
  "status": "active",
  "event_types": ["user.created", "wallet.transaction.created"],
  "http_method": "POST",
  "timeout_seconds": 30,
  "max_retries": 3,
  "ip_whitelist": ["192.168.1.1", "10.0.0.1"],
  "headers": {
    "Content-Type": "application/json",
    "X-Custom-Header": "custom-value"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### `PUT /api/v1/webhooks/endpoints/{id}/`
Update a webhook endpoint.

**Request:**
```json
{
  "status": "paused",
  "timeout_seconds": 60,
  "max_retries": 5
}
```

#### `DELETE /api/v1/webhooks/endpoints/{id}/`
Delete a webhook endpoint.

**Response:**
```json
{
  "message": "Webhook endpoint deleted successfully"
}
```

### Webhook Subscription Endpoints

#### `GET /api/v1/webhooks/subscriptions/`
List all webhook subscriptions.

**Request:**
```json
{
  "endpoint_id": 1,
  "event_type": "user.created",
  "is_active": true
}
```

#### `POST /api/v1/webhooks/subscriptions/`
Create a webhook subscription.

**Request:**
```json
{
  "endpoint_id": 1,
  "event_type": "user.created",
  "filter_config": {
    "user.email": {
      "operator": "contains",
      "value": "@example.com"
    }
  },
  "is_active": true
}
```

### Webhook Delivery Log Endpoints

#### `GET /api/v1/webhooks/delivery-logs/`
List webhook delivery logs.

**Request:**
```json
{
  "endpoint_id": 1,
  "status": "success",
  "date_from": "2024-01-01",
  "date_to": "2024-01-31"
  "page": 1,
  "page_size": 50
}
```

**Response:**
```json
{
  "count": 1000,
  "next": "https://api.example.com/api/v1/webhooks/delivery-logs/?page=2",
  "results": [
    {
      "id": 1,
      "endpoint_id": 1,
      "event_type": "user.created",
      "status": "success",
      "response_code": 200,
      "duration_ms": 150,
      "attempt_number": 1,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Webhook Emission Endpoints

#### `POST /api/v1/webhooks/emit/`
Emit a webhook event.

**Request:**
```json
{
  "event_type": "user.created",
  "payload": {
    "user_id": 12345,
    "email": "user@example.com"
  },
  "endpoint_id": 1,
  "async_emit": false
}
```

**Response:**
```json
{
  "success": true,
  "delivery_log_id": 12345,
  "message": "Webhook emitted successfully"
}
```

## 🔧 Advanced Endpoints

### Webhook Filter Endpoints

#### `GET /api/v1/webhooks/filters/`
List webhook filters for an endpoint.

**Request:**
```json
{
  "endpoint_id": 1
  "is_active": true
}
```

#### `POST /api/v1/webhooks/filters/`
Create a webhook filter.

**Request:**
```json
{
  "endpoint_id": 1,
  "field_path": "user.email",
  "operator": "contains",
  "value": "@example.com",
  "is_active": true
}
```

### Webhook Template Endpoints

#### `GET /api/v1/webhooks/templates/`
List webhook templates.

**Request:**
```json
{
  "event_type": "user.created"
  "is_active": true
}
```

#### `POST /api/v1/webhooks/templates/`
Create a webhook template.

**Request:**
```json
{
  "name": "Welcome Email Template",
  "event_type": "user.created",
  "payload_template": "{\n  \"Welcome {{user_email}}!\"\n  \"Your account has been created successfully.\"\n}",
  "transform_rules": {
    "format_email": {
      "type": "map_value",
      "path": "user_email",
      "mappings": {
        "user@example.com": "USER@EXAMPLE.COM"
      }
    }
  },
  "is_active": true
}
```

#### `POST /api/v1/webhooks/templates/{id}/preview/`
Preview a webhook template.

**Request:**
```json
{
  "payload": {
    "user_id": 12345,
    "email": "user@example.com"
  }
}
```

## 📥 Analytics Endpoints

#### `GET /api/v1/webhooks/analytics/`
Get webhook analytics.

**Request:**
```json
{
  "endpoint_id": 1,
  "date_from": "2024-01-01",
  "date_to": "2024-01-31",
  "period": "daily"
}
```

**Response:**
```json
{
  "total_sent": 10000,
  "success_count": 9500,
  "failed_count": 500,
  "success_rate": 95.0,
  "avg_response_time_ms": 150.5
}
```

#### `GET /api/v1/webhooks/analytics/health/`
Get webhook health status.

**Request:**
```json
{
  "endpoint_id": 1,
  "hours": 24
}
```

**Response:**
```json
{
  "uptime_percentage": 98.5,
  "avg_response_time_ms": 145.0,
  "total_checks": 100,
  "healthy_checks": 98,
  "last_check_at": "2024-01-01T00:00:00Z"
}
```

## 🔄 Replay Endpoints

#### `POST /api/v1/webhooks/replay/create-batch/`
Create a replay batch.

**Request:**
```json
{
  "event_type": "user.created",
  "date_from": "2024-01-01",
  "date_to": "2024-01-31",
  "batch_size": 100,
  "reason": "Monthly data recovery"
}
```

#### `GET /api/v1/webhooks/replay/batch-progress/{batch_id}/`
Get batch progress.

**Response:**
```json
{
  "batch_id": "BATCH-001",
  "total_items": 100,
  "processed_items": 75,
  "completion_percentage": 75.0,
  "status": "processing",
  "started_at": "2024-01-01T00:00:00Z"
}
```

#### `POST /api/v1/webhooks/replay/cancel-batch/`
Cancel a replay batch.

**Request:**
```json
{
  "batch_id": "BATCH-001",
  "reason": "Emergency stop"
}
```

## 🌐 Inbound Endpoints

#### `POST /api/v1/webhooks/inbound/{url_token}/`
Receive inbound webhook from external services.

**Request:**
```json
{
  "event": {
    "type": "payment_intent.succeeded",
    "data": {
      "payment_id": "pay_123456789",
      "amount": 100.00,
      "currency": "USD"
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Webhook received and processed"
}
```

## 🔐 Authentication

### API Key Authentication

All webhook API endpoints require authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.example.com/api/v1/webhooks/endpoints/
```

### JWT Authentication (Alternative)

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  https://api.example.com/api/v1/webhooks/endpoints/
```

## ❌ Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| 200 | Success | 200 |
| 201 | Created | 201 |
| 400 | Bad Request | 400 |
| 401 | Unauthorized | 401 |
| 403 | Forbidden | 403 |
| 404 | Not Found | 404 |
| 409 | Conflict | 409 |
| 429 | Rate Limited | 429 |
| 500 | Internal Server Error | 500 |

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid webhook URL format",
    "details": {
      "field": "url",
      "issue": "URL must include scheme and domain"
    }
  },
  "request_id": "req_123456789"
}
```

## 📊 Rate Limiting

### Headers

Rate limiting is implemented using standard HTTP headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1640995200
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again later.",
    "retry_after": 1640995200
  }
}
```

## 📋 Webhook Format

### Standard Webhook Payload

```json
{
  "event_type": "user.created",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "user_id": 12345,
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "signature": "sha256=abc123..."
}
```

### Signature Verification

Webhook signatures are included in the `X-Webhook-Signature` header:

```http
X-Webhook-Signature: sha256=abc123...
X-Webhook-Timestamp: 2024-01-01T00:00:00Z
```

## 🔧 Examples

### Python/Django

```python
# Create webhook endpoint
import requests

api_key = "your-api-key"
headers = {"Authorization": f"Bearer {api_key}"}

# Create endpoint
response = requests.post(
    "https://api.example.com/api/v1/webhooks/endpoints/",
    json={
        "url": "https://example.com/webhook",
        "event_types": ["user.created"],
        "secret": "your-webhook-secret"
    },
    headers=headers
)

if response.status_code == 201:
    webhook = response.json()
    print(f"Created webhook: {webhook['id']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const apiClient = axios.create({
  baseURL: 'https://api.example.com/api/v1',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY'
  }
});

// Emit webhook event
const emitWebhook = async (eventType, payload) => {
  try {
    const response = await apiClient.post('/webhooks/emit/', {
      event_type: eventType,
      payload: payload
    });
    
    console.log('Webhook emitted:', response.data);
  } catch (error) {
    console.error('Failed to emit webhook:', error.response.data);
  }
};

// Usage
emitWebhook('user.created', {
  user_id: 12345,
  email: 'user@example.com'
});
```

### cURL

```bash
# List endpoints
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.example.com/api/v1/webhooks/endpoints/

# Create endpoint
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/webhook",
    "event_types": ["user.created"],
    "secret": "your-webhook-secret"
  }' \
  https://api.example.com/api/v1/webhooks/endpoints/

# Emit webhook
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.created",
    "payload": {
      "user_id": 12345,
      "email": "user@example.com"
    }
  }' \
  https://api.example.com/api/v1/webhooks/emit/
```

## 📚 Additional Resources

- [Webhooks Management Commands](../management/commands/)
- [Event Types Reference](event_types.md)
- [Signature Verification Guide](signature_guide.md)
- [Inbound Webhook Setup](inbound_setup.md)
- [Webhook Replay Guide](replay_guide.md)

## 🆘 Support

For technical support:
- Check the [API Documentation](../management/commands/)
- Review the [Event Types Reference](event_types.md)
- Contact the development team

---

*Last updated: January 1, 2026*
