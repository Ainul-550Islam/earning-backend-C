# Webhook Signature Verification Guide

This guide provides comprehensive instructions for implementing webhook signature verification
to ensure the authenticity and integrity of webhook payloads.

## 🔐 Overview

Webhook signatures use HMAC (Hash-based Message Authentication Code) to verify that
webhook payloads are authentic and haven't been tampered with during transmission.

## 🛠️ Supported Algorithms

- **SHA-256** (Recommended): Strong cryptographic hash
- **SHA-1**: Legacy support (not recommended for new implementations)
- **MD5**: Legacy only (not recommended for security)

## 📋 Implementation Steps

### 1. Receive Webhook Headers

When a webhook is received, extract the following HTTP headers:

```http
X-Webhook-Signature: <signature>
X-Webhook-Timestamp: <timestamp>
X-Webhook-Nonce: <nonce> (optional)
Content-Type: application/json
```

### 2. Extract Request Body

Read the raw request body as a string, not parsed JSON:

```python
import json

def get_webhook_payload(request):
    """Extract raw webhook payload from Django request."""
    return request.body.decode('utf-8')
```

### 3. Verify Signature

Compare the received signature with your computed signature:

```python
import hmac
import hashlib
from django.utils import timezone

def verify_webhook_signature(request, secret):
    """Verify webhook signature."""
    # Get headers
    signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
    timestamp = request.META.get('HTTP_X_WEBHOOK_TIMESTAMP')
    
    # Get raw payload
    payload = get_webhook_payload(request)
    
    # Compute expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures securely
    return hmac.compare_digest(
        expected_signature.encode('utf-8'),
        signature.encode('utf-8')
    )
```

### 4. Timestamp Validation (Optional but Recommended)

Verify that the webhook was sent within a reasonable time window:

```python
from datetime import datetime, timedelta
import time

def verify_timestamp(timestamp, max_age_seconds=300):
    """Verify webhook timestamp is within acceptable window."""
    if not timestamp:
        return False
    
    try:
        webhook_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        current_time = datetime.utcnow()
        age = current_time - webhook_time
        
        return age.total_seconds() <= max_age_seconds
    except ValueError:
        return False
```

## 🐍 Language-Specific Examples

### Python (Django)

```python
# views.py
from django.http import JsonResponse, HttpResponse
from django.views.decorators import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def webhook_receiver(request):
    """Handle incoming webhook with signature verification."""
    
    # Get webhook secret for this endpoint
    secret = get_webhook_secret_for_endpoint(request.path)
    
    # Verify signature
    if not verify_webhook_signature(request, secret):
        return JsonResponse({
            'error': 'Invalid signature'
        }, status=401)
    
    # Verify timestamp (optional but recommended)
    timestamp = request.META.get('HTTP_X_WEBHOOK_TIMESTAMP')
    if timestamp and not verify_timestamp(timestamp):
        return JsonResponse({
            'error': 'Timestamp too old'
        }, status=401)
    
    try:
        # Parse and process payload
        payload = json.loads(request.body.decode('utf-8'))
        
        # Process webhook event
        process_webhook_event(payload)
        
        return JsonResponse({
            'status': 'success'
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON payload'
        }, status=400)
```

### Node.js (Express)

```javascript
const crypto = require('crypto');
const express = require('express');
const bodyParser = require('body-parser');

const app = express();

// Middleware to parse JSON body
app.use(bodyParser.json({
    verify: (req, res, buf) => {
        req.rawBody = buf;
    }
}));

// Webhook endpoint
app.post('/webhook', (req, res) => {
    const secret = 'your-webhook-secret';
    const signature = req.headers['x-webhook-signature'];
    const timestamp = req.headers['x-webhook-timestamp'];
    
    // Verify signature
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(req.rawBody)
        .digest('hex');
    
    if (!crypto.timingSafeEqual(signature, expectedSignature)) {
        return res.status(401).json({
            error: 'Invalid signature'
        });
    }
    
    // Verify timestamp (optional)
    if (timestamp && !verifyTimestamp(timestamp)) {
        return res.status(401).json({
            error: 'Timestamp too old'
        });
    }
    
    try {
        // Process webhook
        const payload = req.body;
        processWebhookEvent(payload);
        
        res.status(200).json({
            status: 'success'
        });
    } catch (error) {
        res.status(400).json({
            error: 'Invalid JSON payload'
        });
    }
});

function verifyTimestamp(timestamp, maxAge = 300000) {
    const now = Date.now();
    const webhookTime = new Date(timestamp);
    return (now - webhookTime) < maxAge;
}
```

### PHP

```php
<?php
// webhook_receiver.php
header('Content-Type: application/json');

$secret = 'your-webhook-secret';
$signature = $_SERVER['HTTP_X_WEBHOOK_SIGNATURE'] ?? '';
$timestamp = $_SERVER['HTTP_X_WEBHOOK_TIMESTAMP'] ?? '';

// Get raw payload
$payload = file_get_contents('php://input');

// Verify signature
$expectedSignature = hash_hmac('sha256', $payload, $secret);

if (!hash_equals($signature, $expectedSignature)) {
    http_response_code(401);
    echo json_encode(['error' => 'Invalid signature']);
    exit;
}

// Verify timestamp (optional)
if ($timestamp && !verifyTimestamp($timestamp)) {
    http_response_code(401);
    echo json_encode(['error' => 'Timestamp too old']);
    exit;
}

// Process webhook
try {
    $data = json_decode($payload, true);
    processWebhookEvent($data);
    
    http_response_code(200);
    echo json_encode(['status' => 'success']);
} catch (Exception $e) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON payload']);
}

function verifyTimestamp($timestamp, $maxAge = 300) {
    $webhookTime = strtotime($timestamp);
    $now = time();
    return ($now - $webhookTime) < $maxAge;
}
?>
```

## 🔒 Security Best Practices

### 1. Secret Management

- **Store secrets securely**: Use environment variables or secure key management
- **Rotate secrets regularly**: Change webhook secrets periodically
- **Use strong secrets**: Minimum 32 characters with mixed case, numbers, and symbols
- **Never log secrets**: Avoid logging webhook secrets in plain text

### 2. Signature Verification

- **Always verify signatures**: Never skip signature verification
- **Use constant-time comparison**: Prevent timing attacks
- **Validate timestamps**: Prevent replay attacks
- **Handle multiple algorithms**: Support different hash algorithms if needed

### 3. Error Handling

- **Return specific error codes**: 401 for auth, 400 for bad data
- **Don't expose internal errors**: Return generic error messages
- **Log verification failures**: Monitor for suspicious activity
- **Rate limit verification failures**: Prevent brute force attacks

### 4. Network Security

- **Use HTTPS**: Always use HTTPS for webhook URLs
- **Validate certificates**: Ensure SSL certificates are valid
- **Monitor IP addresses**: Track which IPs are sending webhooks
- **Implement rate limiting**: Prevent abuse and DoS attacks

## 🧪 Testing Your Implementation

### Test Cases

1. **Valid Signature Test**
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: $(echo -n '{"test": "data"}' | openssl dgst -sha256 -hmac 'your-secret-key')" \
     -d '{"test": "data"}' \
     https://your-domain.com/webhook
   ```

2. **Invalid Signature Test**
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: invalid-signature" \
     -d '{"test": "data"}' \
     https://your-domain.com/webhook
   ```

3. **Replay Attack Test**
   ```bash
   # Send old webhook with valid signature
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: $(echo -n '{"test": "data"}' | openssl dgst -sha256 -hmac 'your-secret-key')" \
     -H "X-Webhook-Timestamp: 2024-01-01T00:00:00Z" \
     -d '{"test": "data"}' \
     https://your-domain.com/webhook
   ```

## 🔧 Debugging Tips

### Common Issues

1. **Encoding Problems**
   - Ensure UTF-8 encoding for both payload and secret
   - Check for extra whitespace or newlines
   - Verify timezone handling

2. **Header Case Sensitivity**
   - Headers are case-insensitive in HTTP/1.1
   - Check both `X-Webhook-Signature` and `x-webhook-signature`

3. **Timing Issues**
   - Check system clock synchronization
   - Verify timestamp format (ISO 8601)
   - Consider network latency in timestamp validation

4. **Secret Mismatch**
   - Verify secret is exactly the same
   - Check for trailing/leading whitespace
   - Ensure no URL encoding issues

## 📚 Additional Resources

- [RFC 2104 HMAC](https://tools.ietf.org/html/rfc2104)
- [OWASP Webhook Security](https://owasp.org/www-project-webhook-security)
- [Django Security Best Practices](https://docs.djangoproject.com/en/stable/topics/security/)

## 🆘 Support

For questions about webhook signature verification:
- Check the [API Documentation](api_reference.md)
- Review the [Event Types Reference](event_types.md)
- Contact the development team

---

*Last updated: January 1, 2026*
