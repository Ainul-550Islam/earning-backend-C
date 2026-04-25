# Tenant Management API Documentation

This document provides comprehensive API documentation for the Tenant Management System.

## Base URL
```
/api/v1/tenants/
```

## Authentication

All API endpoints require authentication using Django's built-in authentication system. Include the authentication token in the request headers:

```
Authorization: Token your-api-key-here
```

## Response Format

All API responses follow a consistent format:

```json
{
    "success": true,
    "data": {},
    "message": "Operation successful",
    "errors": []
}
```

## Error Handling

Errors are returned with appropriate HTTP status codes and detailed error messages:

```json
{
    "success": false,
    "error": "Validation error",
    "errors": {
        "field_name": ["Error message"]
    }
}
```

## Endpoints

### Tenant Management

#### List Tenants
```http
GET /api/v1/tenants/
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20)
- `status` (str): Filter by status (active, inactive, suspended, trial)
- `tier` (str): Filter by tier (basic, professional, enterprise)
- `search` (str): Search by name or email

**Response:**
```json
{
    "success": true,
    "data": {
        "results": [
            {
                "id": 1,
                "name": "Example Company",
                "slug": "example-company",
                "admin_email": "admin@example.com",
                "status": "active",
                "tier": "professional",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_items": 100,
            "total_pages": 5
        }
    }
}
```

#### Create Tenant
```http
POST /api/v1/tenants/
```

**Request Body:**
```json
{
    "name": "New Company",
    "slug": "new-company",
    "admin_email": "admin@newcompany.com",
    "plan_id": 1,
    "domain": "newcompany.com",
    "settings": {
        "enable_analytics": true,
        "default_language": "en"
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 2,
        "name": "New Company",
        "slug": "new-company",
        "admin_email": "admin@newcompany.com",
        "status": "trial",
        "tier": "basic",
        "created_at": "2023-01-01T00:00:00Z"
    }
}
```

#### Get Tenant Details
```http
GET /api/v1/tenants/{id}/
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "Example Company",
        "slug": "example-company",
        "admin_email": "admin@example.com",
        "status": "active",
        "tier": "professional",
        "domain": "example.com",
        "settings": {
            "enable_analytics": true,
            "enable_api_access": true,
            "default_language": "en"
        },
        "billing": {
            "status": "active",
            "billing_cycle": "monthly",
            "next_payment_at": "2023-02-01T00:00:00Z"
        },
        "created_at": "2023-01-01T00:00:00Z"
    }
}
```

#### Update Tenant
```http
PUT /api/v1/tenants/{id}/
```

**Request Body:**
```json
{
    "name": "Updated Company Name",
    "admin_email": "updated@example.com",
    "domain": "updated-domain.com"
}
```

#### Delete Tenant
```http
DELETE /api/v1/tenants/{id}/
```

**Response:**
```json
{
    "success": true,
    "message": "Tenant deleted successfully"
}
```

### Plan Management

#### List Plans
```http
GET /api/v1/plans/
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Basic",
            "plan_type": "basic",
            "price_monthly": 29.99,
            "price_yearly": 299.99,
            "features": [
                {
                    "feature_key": "api_calls",
                    "feature_name": "API Calls",
                    "value": 10000,
                    "unit": "per_month"
                }
            ]
        }
    ]
}
```

#### Get Plan Details
```http
GET /api/v1/plans/{id}/
```

#### Create Plan
```http
POST /api/v1/plans/
```

**Request Body:**
```json
{
    "name": "Premium Plan",
    "plan_type": "premium",
    "price_monthly": 99.99,
    "price_yearly": 999.99,
    "max_users": 100,
    "features": [
        {
            "feature_key": "api_calls",
            "feature_name": "API Calls",
            "value": 100000,
            "unit": "per_month"
        }
    ]
}
```

### Billing Management

#### List Billing Records
```http
GET /api/v1/billing/
```

#### Create Billing Record
```http
POST /api/v1/billing/
```

#### List Invoices
```http
GET /api/v1/invoices/
```

**Query Parameters:**
- `status` (str): Filter by status (draft, pending, paid, overdue, cancelled)
- `tenant_id` (int): Filter by tenant
- `date_from` (date): Filter by date range start
- `date_to` (date): Filter by date range end

#### Create Invoice
```http
POST /api/v1/invoices/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "type": "subscription",
    "subtotal": 99.99,
    "tax_amount": 8.00,
    "discount_amount": 0.00,
    "total_amount": 107.99,
    "due_date": "2023-02-01",
    "line_items": [
        {
            "description": "Monthly subscription",
            "quantity": 1,
            "unit_price": 99.99,
            "total": 99.99
        }
    ]
}
```

#### Mark Invoice as Paid
```http
POST /api/v1/invoices/{id}/pay/
```

**Request Body:**
```json
{
    "payment_amount": 107.99,
    "payment_method": "credit_card",
    "transaction_id": "txn_123456789"
}
```

### Security Management

#### List API Keys
```http
GET /api/v1/api-keys/
```

#### Create API Key
```http
POST /api/v1/api-keys/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "name": "Production API Key",
    "permissions": ["read", "write"],
    "rate_limit_per_minute": 1000,
    "allowed_ips": ["192.168.1.1", "10.0.0.1"]
}
```

#### Rotate API Key
```http
POST /api/v1/api-keys/{id}/rotate/
```

#### Revoke API Key
```http
POST /api/v1/api-keys/{id}/revoke/
```

#### List Audit Logs
```http
GET /api/v1/audit-logs/
```

**Query Parameters:**
- `tenant_id` (int): Filter by tenant
- `action` (str): Filter by action type
- `severity` (str): Filter by severity level
- `date_from` (date): Filter by date range start
- `date_to` (date): Filter by date range end

### Analytics Management

#### List Metrics
```http
GET /api/v1/metrics/
```

**Query Parameters:**
- `tenant_id` (int): Filter by tenant
- `metric_type` (str): Filter by metric type
- `date_from` (date): Filter by date range start
- `date_to` (date): Filter by date range end

#### Record Metric
```http
POST /api/v1/metrics/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "metric_type": "api_calls",
    "value": 150,
    "metadata": {
        "endpoint": "/api/v1/data",
        "method": "GET"
    }
}
```

#### Get Health Scores
```http
GET /api/v1/health-scores/
```

#### Calculate Health Score
```http
POST /api/v1/health-scores/calculate/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "period": "monthly"
}
```

#### List Feature Flags
```http
GET /api/v1/feature-flags/
```

#### Toggle Feature Flag
```http
POST /api/v1/feature-flags/{id}/toggle/
```

### Onboarding Management

#### List Onboarding Records
```http
GET /api/v1/onboarding/
```

#### Start Onboarding
```http
POST /api/v1/onboarding/start/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "plan_id": 1,
    "trial_days": 14
}
```

#### Complete Onboarding Step
```http
POST /api/v1/onboarding/{id}/complete-step/
```

**Request Body:**
```json
{
    "step_name": "configure_branding",
    "metadata": {
        "completed_at": "2023-01-01T12:00:00Z"
    }
}
```

### Reseller Management

#### List Resellers
```http
GET /api/v1/resellers/
```

#### Create Reseller
```http
POST /api/v1/resellers/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "company_name": "Reseller Company",
    "contact_person": "John Doe",
    "contact_email": "john@reseller.com",
    "commission_type": "percentage",
    "commission_pct": 10.0,
    "max_tenants": 100
}
```

#### Calculate Commission
```http
POST /api/v1/resellers/{id}/calculate-commission/
```

**Request Body:**
```json
{
    "period": "monthly",
    "create_invoice": false
}
```

## Custom Actions

### Tenant Actions

#### Suspend Tenant
```http
POST /api/v1/tenants/{id}/suspend/
```

**Request Body:**
```json
{
    "reason": "Payment overdue"
}
```

#### Unsuspend Tenant
```http
POST /api/v1/tenants/{id}/unsuspend/
```

#### Get Tenant Statistics
```http
GET /api/v1/tenants/{id}/statistics/
```

#### Export Tenant Data
```http
POST /api/v1/tenants/{id}/export/
```

**Request Body:**
```json
{
    "data_types": ["metrics", "billing", "settings"],
    "format": "json"
}
```

### Billing Actions

#### Generate Invoices
```http
POST /api/v1/billing/generate-invoices/
```

**Request Body:**
```json
{
    "tenant_ids": [1, 2, 3],
    "period": "monthly"
}
```

#### Send Payment Reminders
```http
POST /api/v1/billing/send-reminders/
```

### Analytics Actions

#### Generate Analytics Report
```http
POST /api/v1/analytics/generate-report/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "report_type": "comprehensive",
    "days": 30
}
```

#### Export Analytics Data
```http
POST /api/v1/analytics/export/
```

## Rate Limiting

API endpoints are rate-limited based on tenant plan:

- **Basic Plan**: 100 requests/minute
- **Professional Plan**: 1000 requests/minute
- **Enterprise Plan**: 10000 requests/minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Webhooks

### Webhook Events

The system sends webhook notifications for various events:

- `tenant.created`: New tenant created
- `tenant.updated`: Tenant updated
- `tenant.suspended`: Tenant suspended
- `invoice.created`: New invoice created
- `invoice.paid`: Invoice paid
- `metric.recorded`: Metric recorded
- `health_score.updated`: Health score updated

### Webhook Configuration

Configure webhooks via the API:

```http
POST /api/v1/webhooks/
```

**Request Body:**
```json
{
    "tenant_id": 1,
    "url": "https://example.com/webhook",
    "secret": "webhook-secret",
    "event_types": ["tenant.created", "invoice.paid"],
    "is_active": true
}
```

### Webhook Payload Format

```json
{
    "event_type": "tenant.created",
    "tenant_id": 1,
    "timestamp": "2023-01-01T12:00:00Z",
    "data": {
        "tenant": {
            "id": 1,
            "name": "Example Company",
            "email": "admin@example.com"
        }
    },
    "signature": "sha256=hash"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Validation error |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 422 | Unprocessable Entity - Business logic error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |

## SDK Examples

### Python SDK

```python
from tenants_client import TenantsClient

client = TenantsClient(api_key='your-api-key')

# Create tenant
tenant = client.tenants.create(
    name="My Company",
    admin_email="admin@mycompany.com",
    plan_id=1
)

# Get tenant
tenant = client.tenants.get(tenant.id)

# Update tenant
client.tenants.update(tenant.id, name="Updated Name")

# List tenants
tenants = client.tenants.list(status='active')
```

### JavaScript SDK

```javascript
import { TenantsClient } from '@tenants/client';

const client = new TenantsClient({ apiKey: 'your-api-key' });

// Create tenant
const tenant = await client.tenants.create({
    name: 'My Company',
    adminEmail: 'admin@mycompany.com',
    planId: 1
});

// Get tenant
const tenant = await client.tenants.get(tenant.id);

// List tenants
const tenants = await client.tenants.list({ status: 'active' });
```

## Testing

### API Testing

Use the provided test suite to verify API functionality:

```bash
# Run API tests
python manage.py test api.tenants.tests.test_viewsets

# Run specific endpoint tests
python manage.py test api.tenants.tests.test_viewsets.TenantViewSetTest
```

### Postman Collection

A Postman collection is available in `docs/postman-collection.json` for testing all endpoints.

## Support

For API support:
- Check the documentation
- Review the test cases
- Create an issue in the repository
- Contact the development team
