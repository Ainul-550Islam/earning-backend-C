# Webhook Replay Guide

This guide provides comprehensive instructions for safely replaying webhook events
for debugging, recovery, and data recovery purposes.

## 🎯 Overview

Webhook replay allows you to resend specific webhook events or event ranges
that may have failed, been lost, or need to be reprocessed for various reasons.
This feature is essential for maintaining data consistency and recovering from
temporary failures.

## 📋 When to Use Webhook Replay

### ✅ Recommended Scenarios

1. **Failed Deliveries**
   - Network timeouts or connection errors
   - Temporary endpoint unavailability
   - Rate limiting issues
   - Server errors (500, 502, etc.)

2. **Data Issues**
   - Corrupted webhook payloads
   - Missing or incorrect data
   - Formatting errors

3. **Testing and Development**
   - Testing new webhook configurations
   - Debugging webhook processing
   - Validating event data

4. **Data Recovery**
   - Lost webhook events
   - Corrupted delivery logs
   - Historical data reconstruction

5. **Compliance Requirements**
   - Audit trail requirements
   - Data retention policies
   - Regulatory compliance needs

### ⚠️ When NOT to Use Webhook Replay

1. **Duplicate Processing**
   - Events that were successfully delivered
   - Idempotent operations
   - Financial transactions

2. **System Events**
   - User actions that are already logged
   - Automated system processes
   - High-volume repetitive events

3. **Security Concerns**
   - Sensitive data (passwords, tokens)
   - Payment processing without proper authorization
   - User privacy violations

## 🔄 Replay Methods

### 1. Single Event Replay
Replay a specific webhook event by its delivery log ID.

```python
# Using management command
python manage.py replay_events \
  --event-type user.created \
  --delivery-log-id 12345 \
  --reason "Testing webhook replay"
```

### 2. Batch Replay
Replay multiple events within a date range or matching specific criteria.

```python
# Using management command
python manage.py replay_events \
  --event-type wallet.transaction.created \
  --date-from 2024-01-01 \
  --date-to 2024-01-31 \
  --batch-size 100 \
  --reason "Monthly wallet transaction replay"
```

### 3. API-Based Replay
Programmatic replay using the REST API.

```python
import requests

# Create replay batch
response = requests.post('https://your-domain.com/api/webhooks/replay/create-batch/', json={
    'event_type': 'user.created',
    'date_from': '2024-01-01',
    'date_to': '2024-01-31',
    'batch_size': 100,
    'reason': 'Data recovery'
})

if response.status_code == 201:
    batch_id = response.json()['batch_id']
    print(f"Replay batch created: {batch_id}")
else:
    print(f"Failed to create replay batch: {response.text}")
```

## 🛡️ Safety Considerations

### 1. Idempotency
- Ensure replayed events are idempotent
- Use idempotency keys to prevent duplicate processing
- Check for existing replays before creating new ones

### 2. Rate Limiting
- Monitor rate limits during replay operations
- Implement backoff strategies for batch replays
- Consider system load and endpoint capacity

### 3. Data Integrity
- Validate event data before replay
- Ensure all required fields are present
- Maintain referential integrity

### 4. Audit Trail
- Log all replay operations with reasons
- Track who initiated replays and when
- Maintain replay history for compliance

### 5. Error Handling
- Handle replay failures gracefully
- Implement retry logic with exponential backoff
- Provide clear error messages and recovery options

## 📊 Monitoring Replay Progress

### 1. Using Management Commands

```bash
# Monitor batch progress
python manage.py replay_events --batch-progress --batch-id BATCH-001

# Check replay status
python manage.py replay_events --batch-status --batch-id BATCH-001

# Cancel running replay
python manage.py replay_events --cancel-batch --batch-id BATCH-001 --reason "Emergency stop"
```

### 2. Using API Endpoints

```python
import requests

# Get batch progress
response = requests.get(
    'https://your-domain.com/api/webhooks/replay/batch-progress/',
    params={'batch_id': 'BATCH-001'}
)

progress_data = response.json()
print(f"Progress: {progress_data['completion_percentage']}%")
```

### 3. Webhook Analytics

```bash
# Check replay statistics
python manage.py check_endpoint_health --analytics

# View replay history
python manage.py replay_events --history --event-type user.created --days 30
```

## 🧪 Testing Replay Functionality

### 1. Unit Testing

```python
# tests/test_replay_service.py
import pytest
from api.webhooks.services.replay import ReplayService

def test_single_event_replay():
    """Test single event replay functionality."""
    service = ReplayService()
    
    # Create test delivery log
    delivery_log = create_test_delivery_log()
    
    # Test replay
    replay = service.create_replay(
        original_log=delivery_log,
        replayed_by=test_user,
        reason="Unit test replay"
    )
    
    assert replay.status == 'pending'
    assert replay.reason == "Unit test replay"

def test_batch_replay():
    """Test batch replay functionality."""
    service = ReplayService()
    
    # Create test batch
    result = service.create_replay_batch(
        event_type='user.created',
        from_date='2024-01-01',
        to_date='2024-01-31',
        batch_size=10,
        user_id=test_user.id
    )
    
    assert 'batch' in result
    assert result['event_count'] == 10
```

### 2. Integration Testing

```python
# tests/test_integration.py
import pytest
from django.test import TestCase
from api.webhooks.models import WebhookDeliveryLog, WebhookReplay

class ReplayIntegrationTest(TestCase):
    """Test replay functionality end-to-end."""
    
    def test_end_to_end_replay(self):
        """Test complete replay workflow."""
        # Create original delivery log
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.test_endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status='failed',
            response_code=500
        )
        
        # Create replay
        replay = WebhookReplay.objects.create(
            original_log=delivery_log,
            replayed_by=self.test_user,
            reason="Integration test replay",
            status='pending'
        )
        
        # Start replay processing
        from api.webhooks.tasks import process_replay_batch
        process_replay_batch.delay(replay.id)
        
        # Verify completion
        self.assertEqual(replay.status, 'completed')
```

### 3. Load Testing

```bash
# Load test replay batch
python manage.py replay_events \
  --create-batch \
  --event-type user.created \
  --date-from 2024-01-01 \
  --date-to 2024-01-31 \
  --batch-size 1000 \
  --dry-run

# Monitor system performance
python manage.py replay_events --monitor-performance --duration 60
```

## 🔧 Configuration Options

### Management Command Options

```bash
# Create replay batch
python manage.py replay_events create-batch \
  --event-type EVENT_TYPE \
  --date-from YYYY-MM-DD \
  --date-to YYYY-MM-DD \
  --batch-size INTEGER \
  --reason TEXT \
  --user-id INTEGER

# Start batch processing
python manage.py replay_events start-batch \
  --batch-id BATCH_ID

# Monitor batch progress
python manage.py replay_events batch-progress \
  --batch-id BATCH_ID \
  --interval SECONDS

# Cancel batch
python manage.py replay_events cancel-batch \
  --batch-id BATCH_ID \
  --reason TEXT
```

### API Configuration

```python
# settings.py
WEBHOOKS_SETTINGS = {
    'REPLAY': {
        'MAX_BATCH_SIZE': 1000,
        'DEFAULT_REASON': 'System recovery',
        'RATE_LIMIT_REPLAYS': 100,  # per hour
        'RETENTION_DAYS': 90,
        'AUTO_RETRY_FAILED': True,
        'IDEMPOTENCY_TIMEOUT': 300,  # 5 minutes
    }
}
```

## 📈 Best Practices

### 1. Planning
- Identify specific events or date ranges
- Assess potential impact on downstream systems
- Plan replay during low-traffic periods
- Communicate with affected stakeholders

### 2. Execution
- Start with small batches to test functionality
- Monitor system performance during replay
- Have rollback plan ready if issues occur
- Document all replay activities

### 3. Validation
- Verify replayed events match original data
- Check for duplicate processing
- Validate webhook endpoint availability
- Monitor error rates and response times

### 4. Communication
- Notify teams about replay activities
- Provide clear status updates and progress reports
- Document any issues discovered during replay
- Share lessons learned and improvements

## 🚨 Common Issues and Solutions

### Issue 1: Rate Limiting
**Problem**: Replays fail due to rate limits
**Solution**: 
- Implement rate limiting bypass for replay operations
- Use smaller batch sizes
- Add delays between batches
- Coordinate with downstream services

### Issue 2: Endpoint Unavailability
**Problem**: Target endpoints are down during replay
**Solution**:
- Check endpoint health before starting replay
- Implement retry logic with exponential backoff
- Have fallback endpoints available
- Schedule replays during maintenance windows

### Issue 3: Data Inconsistency
**Problem**: Replay data doesn't match original events
**Solution**:
- Validate data before replay
- Use original event data from delivery logs
- Implement data transformation if needed
- Maintain audit trail of changes

### Issue 4: Performance Impact
**Problem**: Replays cause system overload
**Solution**:
- Monitor system resources during replay
- Use smaller batch sizes
- Implement throttling for replay operations
- Schedule replays during off-peak hours

## 📚 Additional Resources

- [Webhooks API Reference](api_reference.md)
- [Event Types Reference](event_types.md)
- [Management Commands](../management/commands/)
- [Troubleshooting Guide](../troubleshooting/)

## 🆘 Support

For questions about webhook replay functionality:
- Check the [API Documentation](api_reference.md)
- Review the [Management Commands](../management/commands/)
- Contact the development team

---

*Last updated: January 1, 2026*
