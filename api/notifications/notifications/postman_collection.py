# earning_backend/api/notifications/postman_collection.py
"""
Postman Collection Generator — Auto-generates Postman collection from OpenAPI spec.

Run: python manage.py shell -c "from notifications.postman_collection import generate; generate('/tmp/notifications.postman.json')"
"""
import json, logging
from django.conf import settings
logger = logging.getLogger(__name__)

COLLECTION = {
    "info": {"name": "Notification System API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "variable": [
        {"key": "base_url", "value": "http://localhost:8000/api/notifications"},
        {"key": "token", "value": "your-jwt-token-here"},
    ],
    "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}"}]},
    "item": [
        {"name": "Notifications", "item": [
            {"name": "List Notifications", "request": {"method": "GET", "url": "{{base_url}}/notifications/", "header": []}},
            {"name": "Create Notification", "request": {"method": "POST", "url": "{{base_url}}/notifications/", "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": {"mode": "raw", "raw": json.dumps({"title": "Test Notification", "message": "Test message", "notification_type": "announcement", "channel": "in_app", "priority": "medium"})}}},
            {"name": "Mark All Read", "request": {"method": "POST", "url": "{{base_url}}/notifications/mark-all-read/"}},
            {"name": "Unread Count", "request": {"method": "GET", "url": "{{base_url}}/notifications/unread-count/"}},
        ]},
        {"name": "Push Devices", "item": [
            {"name": "List Devices", "request": {"method": "GET", "url": "{{base_url}}/v2/push-devices/"}},
            {"name": "Register Device", "request": {"method": "POST", "url": "{{base_url}}/v2/push-devices/register/",
                "body": {"mode": "raw", "raw": json.dumps({"device_type": "android", "fcm_token": "your_fcm_token_here"})}}},
        ]},
        {"name": "In-App Messages", "item": [
            {"name": "List In-App Messages", "request": {"method": "GET", "url": "{{base_url}}/v2/in-app-messages/"}},
        ]},
        {"name": "Campaigns", "item": [
            {"name": "List Campaigns", "request": {"method": "GET", "url": "{{base_url}}/v2/campaigns/"}},
            {"name": "Create Campaign", "request": {"method": "POST", "url": "{{base_url}}/v2/campaigns/",
                "body": {"mode": "raw", "raw": json.dumps({"name": "Test Campaign", "template_id": 1, "segment_conditions": {"type": "all"}})}}},
        ]},
        {"name": "Opt-Outs", "item": [
            {"name": "Opt Out of Channel", "request": {"method": "POST", "url": "{{base_url}}/v2/opt-outs/opt_out/",
                "body": {"mode": "raw", "raw": json.dumps({"channel": "email", "reason": "too_many"})}}},
            {"name": "Resubscribe", "request": {"method": "POST", "url": "{{base_url}}/v2/opt-outs/resubscribe/",
                "body": {"mode": "raw", "raw": json.dumps({"channel": "email"})}}},
        ]},
        {"name": "Analytics", "item": [
            {"name": "List Insights", "request": {"method": "GET", "url": "{{base_url}}/v2/insights/"}},
            {"name": "Delivery Rates", "request": {"method": "GET", "url": "{{base_url}}/v2/delivery-rates/"}},
        ]},
        {"name": "Webhooks", "item": [
            {"name": "SendGrid Webhook", "request": {"method": "POST", "url": "{{base_url}}/webhooks/sendgrid/"}},
            {"name": "Twilio SMS Webhook", "request": {"method": "POST", "url": "{{base_url}}/webhooks/twilio/sms/"}},
        ]},
        {"name": "System", "item": [
            {"name": "Health Check", "request": {"method": "GET", "url": "{{base_url}}/health/"}},
            {"name": "VAPID Public Key", "request": {"method": "GET", "url": "{{base_url}}/push/vapid-key/"}},
            {"name": "API Meta", "request": {"method": "GET", "url": "{{base_url}}/meta/"}},
        ]},
    ]
}

def generate(output_path: str = '/tmp/notifications_postman.json'):
    with open(output_path, 'w') as f:
        json.dump(COLLECTION, f, indent=2)
    print(f"Postman collection generated: {output_path}")
    return output_path

def get_collection() -> dict:
    return COLLECTION
