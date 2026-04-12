# Alerts API Reference

## Overview

This document provides a comprehensive reference for all Alerts API endpoints, including request/response formats, parameters, and examples.

## Base URL

```
https://your-domain.com/api/alerts/
```

## Authentication

All API requests must include authentication credentials:

### Token Authentication
```http
Authorization: Token your-api-token-here
```

### Session Authentication
```http
Cookie: sessionid=your-session-id-here
```

## Core Endpoints

### Alert Rules

#### List Alert Rules
```http
GET /api/alerts/rules/
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20, max: 100)
- `severity` (str): Filter by severity (low, medium, high, critical)
- `is_active` (bool): Filter by active status
- `search` (str): Search in name and description
- `ordering` (str): Sort order (e.g., `-created_at`, `name`)

**Response:**
```json
{
    "count": 25,
    "next": "http://api.example.com/api/alerts/rules/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "CPU Usage Alert",
            "alert_type": "cpu_usage",
            "severity": "high",
            "threshold_value": 80.0,
            "time_window_minutes": 15,
            "cooldown_minutes": 30,
            "description": "Alert when CPU usage exceeds 80%",
            "is_active": true,
            "send_email": true,
            "send_telegram": false,
            "send_sms": false,
            "escalation_enabled": false,
            "escalation_delay_minutes": 30,
            "max_escalation_level": 3,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "last_triggered": "2024-01-20T14:25:00Z",
            "severity_display": "High",
            "alert_type_display": "CPU Usage",
            "recent_alerts_count": 5,
            "success_rate": 95.5
        }
    ]
}
```

#### Create Alert Rule
```http
POST /api/alerts/rules/
```

**Request Body:**
```json
{
    "name": "Memory Usage Alert",
    "alert_type": "memory_usage",
    "severity": "medium",
    "threshold_value": 85.0,
    "time_window_minutes": 10,
    "cooldown_minutes": 20,
    "description": "Alert when memory usage exceeds 85%",
    "is_active": true,
    "send_email": true,
    "send_telegram": false,
    "send_sms": false,
    "escalation_enabled": false,
    "escalation_delay_minutes": 15,
    "max_escalation_level": 2
}
```

**Response:**
```json
{
    "id": 2,
    "name": "Memory Usage Alert",
    "alert_type": "memory_usage",
    "severity": "medium",
    "threshold_value": 85.0,
    "time_window_minutes": 10,
    "cooldown_minutes": 20,
    "description": "Alert when memory usage exceeds 85%",
    "is_active": true,
    "send_email": true,
    "send_telegram": false,
    "send_sms": false,
    "escalation_enabled": false,
    "escalation_delay_minutes": 15,
    "max_escalation_level": 2,
    "created_at": "2024-01-20T15:00:00Z",
    "updated_at": "2024-01-20T15:00:00Z",
    "last_triggered": null,
    "severity_display": "Medium",
    "alert_type_display": "Memory Usage",
    "recent_alerts_count": 0,
    "success_rate": 0.0
}
```

#### Get Alert Rule
```http
GET /api/alerts/rules/{id}/
```

**Response:** Same as create response

#### Update Alert Rule
```http
PUT /api/alerts/rules/{id}/
```

**Request Body:** Same as create request

#### Partial Update Alert Rule
```http
PATCH /api/alerts/rules/{id}/
```

**Request Body:**
```json
{
    "severity": "high",
    "threshold_value": 90.0,
    "is_active": false
}
```

#### Delete Alert Rule
```http
DELETE /api/alerts/rules/{id}/
```

**Response:** 204 No Content

#### Activate Alert Rule
```http
POST /api/alerts/rules/{id}/activate/
```

**Request Body:**
```json
{
    "reason": "Re-enabling for testing"
}
```

**Response:**
```json
{
    "success": true,
    "activated_at": "2024-01-20T15:30:00Z",
    "message": "Alert rule activated successfully"
}
```

#### Deactivate Alert Rule
```http
POST /api/alerts/rules/{id}/deactivate/
```

**Request Body:**
```json
{
    "reason": "Maintenance in progress"
}
```

#### Test Alert Rule
```http
POST /api/alerts/rules/{id}/test/
```

**Request Body:**
```json
{
    "trigger_value": 95.0,
    "message": "Test alert message"
}
```

**Response:**
```json
{
    "success": true,
    "test_alert_id": 123,
    "notifications_sent": 1,
    "test_result": {
        "rule_matched": true,
        "threshold_exceeded": true,
        "cooldown_active": false
    }
}
```

#### Get Alert Rule Statistics
```http
GET /api/alerts/rules/{id}/statistics/
```

**Response:**
```json
{
    "rule_id": 1,
    "total_alerts": 150,
    "alerts_last_30_days": 25,
    "alerts_last_7_days": 8,
    "avg_severity": "high",
    "most_common_hour": 14,
    "success_rate": 95.5,
    "avg_resolution_time_minutes": 45.2,
    "escalation_rate": 5.0
}
```

### Alert Logs

#### List Alert Logs
```http
GET /api/alerts/logs/
```

**Query Parameters:**
- `page` (int): Page number
- `page_size` (int): Items per page
- `rule_id` (int): Filter by alert rule ID
- `severity` (str): Filter by severity
- `is_resolved` (bool): Filter by resolution status
- `created_at__gte` (datetime): Filter by creation date (>=)
- `created_at__lte` (datetime): Filter by creation date (<=)
- `search` (str): Search in message
- `ordering` (str): Sort order

**Response:**
```json
{
    "count": 100,
    "next": "http://api.example.com/api/alerts/logs/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "rule": {
                "id": 1,
                "name": "CPU Usage Alert",
                "alert_type": "cpu_usage",
                "severity": "high"
            },
            "trigger_value": 85.5,
            "threshold_value": 80.0,
            "message": "CPU usage is high",
            "details": {
                "current_usage": 85.5,
                "server": "web-01"
            },
            "is_resolved": false,
            "resolved_by": null,
            "resolved_at": null,
            "resolution_note": null,
            "triggered_at": "2024-01-20T14:25:00Z",
            "acknowledged_at": null,
            "acknowledged_by": null,
            "acknowledgment_note": null,
            "severity_display": "High",
            "status_display": "Pending",
            "exceed_percentage": 6.875,
            "age_minutes": 45
        }
    ]
}
```

#### Create Alert Log
```http
POST /api/alerts/logs/
```

**Request Body:**
```json
{
    "rule": 1,
    "trigger_value": 92.0,
    "threshold_value": 80.0,
    "message": "CPU usage critical",
    "details": {
        "current_usage": 92.0,
        "server": "web-01",
        "processes": ["apache", "mysql"]
    }
}
```

#### Get Alert Log
```http
GET /api/alerts/logs/{id}/
```

#### Update Alert Log
```http
PUT /api/alerts/logs/{id}/
```

#### Partial Update Alert Log
```http
PATCH /api/alerts/logs/{id}/
```

#### Resolve Alert Log
```http
POST /api/alerts/logs/{id}/resolve/
```

**Request Body:**
```json
{
    "resolution_note": "Fixed CPU spike by restarting process",
    "resolution_actions": "Restarted Apache service"
}
```

**Response:**
```json
{
    "success": true,
    "resolved_at": "2024-01-20T15:10:00Z",
    "resolution_time_minutes": 45,
    "message": "Alert resolved successfully"
}
```

#### Acknowledge Alert Log
```http
POST /api/alerts/logs/{id}/acknowledge/
```

**Request Body:**
```json
{
    "acknowledgment_note": "Investigating CPU spike"
}
```

#### Get Alerts by Rule
```http
GET /api/alerts/logs/by_rule/{rule_id}/
```

#### Get Pending Alerts
```http
GET /api/alerts/logs/pending/
```

#### Get Resolved Alerts
```http
GET /api/alerts/logs/resolved/
```

#### Get Alerts by Severity
```http
GET /api/alerts/logs/by_severity/{severity}/
```

### Notifications

#### List Notifications
```http
GET /api/alerts/notifications/
```

**Query Parameters:**
- `page` (int): Page number
- `page_size` (int): Items per page
- `alert_log_id` (int): Filter by alert log ID
- `notification_type` (str): Filter by type (email, sms, telegram, webhook)
- `status` (str): Filter by status (pending, sent, failed, retry)
- `recipient` (str): Filter by recipient
- `created_at__gte` (datetime): Filter by creation date (>=)
- `created_at__lte` (datetime): Filter by creation date (<=)

**Response:**
```json
{
    "count": 50,
    "next": "http://api.example.com/api/alerts/notifications/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "alert_log": {
                "id": 1,
                "message": "CPU usage is high",
                "severity": "high"
            },
            "notification_type": "email",
            "recipient": "admin@example.com",
            "status": "sent",
            "sent_at": "2024-01-20T14:26:00Z",
            "failed_at": null,
            "error_message": null,
            "retry_count": 0,
            "created_at": "2024-01-20T14:25:30Z",
            "updated_at": "2024-01-20T14:26:00Z",
            "status_display": "Sent",
            "type_display": "Email",
            "delivery_time_minutes": 0.5
        }
    ]
}
```

#### Create Notification
```http
POST /api/alerts/notifications/
```

**Request Body:**
```json
{
    "alert_log": 1,
    "notification_type": "email",
    "recipient": "admin@example.com",
    "status": "pending"
}
```

#### Get Notification
```http
GET /api/alerts/notifications/{id}/
```

#### Update Notification
```http
PUT /api/alerts/notifications/{id}/
```

#### Mark Notification as Sent
```http
POST /api/alerts/notifications/{id}/mark_sent/
```

**Request Body:**
```json
{
    "delivery_details": {
        "message_id": "msg_123456",
        "provider": "sendgrid"
    }
}
```

#### Mark Notification as Failed
```http
POST /api/alerts/notifications/{id}/mark_failed/
```

**Request Body:**
```json
{
    "error_message": "SMTP server unavailable",
    "error_details": {
        "smtp_code": 550,
        "smtp_response": "User not found"
    }
}
```

#### Retry Notification
```http
POST /api/alerts/notifications/{id}/retry/
```

#### Get Notifications by Status
```http
GET /api/alerts/notifications/by_status/{status}/
```

#### Get Notifications by Type
```http
GET /api/alerts/notifications/by_type/{type}/
```

#### Get Failed Notifications
```http
GET /api/alerts/notifications/failed/
```

### System Health

#### Get System Health
```http
GET /api/alerts/health/
```

**Response:**
```json
{
    "overall_health": "healthy",
    "alerts_health": {
        "status": "healthy",
        "total_rules": 25,
        "active_rules": 20,
        "pending_alerts": 5,
        "error_rate": 2.5,
        "last_check": "2024-01-20T15:00:00Z"
    },
    "channels_health": {
        "status": "warning",
        "total_channels": 5,
        "healthy_channels": 4,
        "unhealthy_channels": 1,
        "last_check": "2024-01-20T15:00:00Z"
    },
    "incidents_health": {
        "status": "healthy",
        "total_incidents": 3,
        "open_incidents": 1,
        "resolved_incidents": 2,
        "avg_resolution_time": 45.5,
        "last_check": "2024-01-20T15:00:00Z"
    },
    "timestamp": "2024-01-20T15:00:00Z"
}
```

#### Get Health Metrics
```http
GET /api/alerts/health/metrics/
```

**Response:**
```json
{
    "alert_metrics": {
        "total_alerts_24h": 150,
        "resolved_alerts_24h": 125,
        "resolution_rate": 83.3,
        "avg_resolution_time": 42.5,
        "alerts_by_severity": {
            "critical": 5,
            "high": 25,
            "medium": 60,
            "low": 60
        }
    },
    "channel_metrics": {
        "total_notifications_24h": 300,
        "successful_notifications_24h": 285,
        "success_rate": 95.0,
        "channel_performance": {
            "email": 98.0,
            "sms": 92.0,
            "webhook": 95.0
        }
    },
    "system_metrics": {
        "avg_response_time_ms": 250.5,
        "error_rate": 1.5,
        "uptime_percentage": 99.9
    }
}
```

#### Get Health History
```http
GET /api/alerts/health/history/
```

#### Run Health Check
```http
POST /api/alerts/health/check/
```

**Request Body:**
```json
{
    "components": ["alerts", "channels", "incidents"],
    "detailed": true
}
```

### Alert Overview

#### Get Alert Overview
```http
GET /api/alerts/overview/
```

**Response:**
```json
{
    "summary": {
        "total_alerts": 150,
        "pending_alerts": 15,
        "resolved_alerts": 135,
        "critical_alerts": 5,
        "active_rules": 20,
        "active_channels": 5
    },
    "recent_alerts": [
        {
            "id": 1,
            "message": "CPU usage is high",
            "severity": "high",
            "triggered_at": "2024-01-20T14:25:00Z",
            "status": "pending"
        }
    ],
    "trends": {
        "alerts_last_7_days": [10, 15, 12, 20, 18, 25, 15],
        "resolution_rate_trend": [85, 87, 83, 90, 88, 92, 89]
    },
    "top_rules": [
        {
            "rule_name": "CPU Usage Alert",
            "alert_count": 25,
            "severity": "high"
        }
    ]
}
```

#### Get Overview Summary
```http
GET /api/alerts/overview/summary/
```

#### Get Recent Alerts
```http
GET /api/alerts/overview/recent_alerts/
```

#### Get Alert Trends
```http
GET /api/alerts/overview/trends/
```

#### Get Top Alert Rules
```http
GET /api/alerts/overview/top_rules/
```

## Error Responses

All endpoints return consistent error responses:

```json
{
    "error": "Validation error",
    "error_code": "validation_failed",
    "details": {
        "field_name": ["This field is required."]
    },
    "timestamp": "2024-01-20T15:00:00Z"
}
```

### Common Error Codes

- `validation_failed` - Request validation failed
- `authentication_required` - Authentication required
- `permission_denied` - Insufficient permissions
- `not_found` - Resource not found
- `rate_limit_exceeded` - Rate limit exceeded
- `server_error` - Internal server error

## Rate Limiting

- **Standard endpoints**: 100 requests/minute
- **Write endpoints**: 50 requests/minute
- **Bulk operations**: 25 requests/minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642694400
```

## Webhooks

### Webhook Events

- `alert.created` - New alert created
- `alert.resolved` - Alert resolved
- `incident.created` - New incident created
- `incident.resolved` - Incident resolved
- `system.health_changed` - System health status changed

### Webhook Configuration

Webhooks are configured through the admin interface or API. Each webhook includes:

```json
{
    "event": "alert.created",
    "timestamp": "2024-01-20T15:00:00Z",
    "data": {
        "alert_id": 1,
        "message": "CPU usage is high",
        "severity": "high"
    }
}
```

## SDKs and Libraries

### Python SDK Example

```python
from alerts_client import AlertsClient

client = AlertsClient(
    base_url="https://api.example.com",
    token="your-api-token"
)

# List alert rules
rules = client.alerts.rules.list(severity="high")

# Create alert rule
rule = client.alerts.rules.create({
    "name": "CPU Usage Alert",
    "alert_type": "cpu_usage",
    "severity": "high",
    "threshold_value": 80.0
})

# Get alert logs
logs = client.alerts.logs.list(is_resolved=False)
```

### JavaScript SDK Example

```javascript
import { AlertsClient } from 'alerts-client-js';

const client = new AlertsClient({
    baseURL: 'https://api.example.com',
    token: 'your-api-token'
});

// List alert rules
const rules = await client.alerts.rules.list({ severity: 'high' });

// Create alert rule
const rule = await client.alerts.rules.create({
    name: 'CPU Usage Alert',
    alertType: 'cpu_usage',
    severity: 'high',
    thresholdValue: 80.0
});
```

## Support

For API support:
- Check the health endpoint: `GET /api/alerts/health/`
- Review error messages in responses
- Contact the development team
- Check system status page
