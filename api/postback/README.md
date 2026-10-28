# Postback Module - Enterprise-grade Webhook Processing

## Overview

The `api.postback` module provides comprehensive webhook processing, analytics, and security capabilities for high-volume postback handling. It features advanced security with SHA-256 integrity hashing, real-time analytics with anomaly detection, template management, and comprehensive monitoring.

## Key Features

### 🔒 **Security & Integrity**
- **SHA-256 Hash Chaining**: Tamper detection for all critical data
- **Enhanced IP Whitelisting**: CIDR support with priority-based evaluation
- **Advanced Rate Limiting**: Progressive blocking with violation tracking
- **HMAC Signature Verification**: Multiple algorithm support with replay protection

### 📊 **Analytics & Monitoring**
- **Daily Aggregated Metrics**: Comprehensive performance analytics
- **Anomaly Detection**: Automatic detection of volume spikes and health issues
- **Health Scoring**: 0-100 scoring system with trend analysis
- **Real-time Processing**: Live monitoring of postback processing

### 🎯 **Template Management**
- **Reusable Templates**: Variable substitution with validation
- **Usage Tracking**: Monitor template performance and adoption
- **Integrity Verification**: Detect template tampering
- **Cloning Support**: Easy template duplication and customization

### 🛡️ **Advanced Security**
- **Multi-layer Validation**: IP, signature, field, and custom validators
- **Fraud Detection**: Pattern-based fraud identification
- **Audit Trails**: Complete logging of all postback activities
- **Compliance Ready**: GDPR and security compliance features

## Architecture

### Core Models
- **NetworkPostbackConfig**: Network configuration and security settings
- **PostbackLog**: Immutable audit records with integrity hashing
- **PostbackInsight**: Daily analytics and health metrics
- **PostbackTemplate**: Reusable postback templates
- **PostbackIPWhitelist**: Enhanced IP whitelist management
- **PostbackRateLimit**: Advanced rate limiting configuration

### Service Layer
- **PostbackInsightService**: Analytics aggregation and anomaly detection
- **TemplateService**: Template management and rendering
- **Core Services**: Postback processing pipeline with security validation

### API Layer
- **REST Endpoints**: Comprehensive CRUD operations
- **Custom Actions**: Template rendering, IP testing, rate limit management
- **Admin Integration**: Full Django admin support
- **Authentication**: Role-based access control

## Quick Start

### 1. Basic Postback Processing

```python
from api.postback import receive_postback

# Process incoming postback
log = receive_postback(
    network_key="my-network",
    payload={"lead_id": "123", "offer_id": "456", "payout": "10.00"},
    headers={"X-Signature": "hmac_signature"},
    source_ip="192.168.1.100"
)
```

### 2. Analytics and Monitoring

```python
from api.postback import PostbackInsightService

# Get daily analytics
insight = PostbackInsightService.get_daily_insight(network, date.today())
print(f"Health Score: {insight.health_score}%")

# Detect anomalies
anomalies = PostbackInsightService.detect_anomalies(network, date.today())
if anomalies:
    print(f"Anomalies detected: {list(anomalies.keys())}")
```

### 3. Template Management

```python
from api.postback import TemplateService

# Create template
template = TemplateService.create_template(
    network=network,
    name="Lead Notification",
    template_body="Lead {{lead_id}} from {{source}} worth ${{amount}}",
    variables={"lead_id": "string", "source": "string", "amount": "decimal"}
)

# Render template
rendered = TemplateService.render_template(
    template.id,
    {"lead_id": "123", "source": "web", "amount": "25.00"}
)
print(rendered)  # "Lead 123 from web worth $25.00"
```

## API Endpoints

### Core Endpoints
- `GET /api/postback/networks/` - List network configurations
- `GET /api/postback/logs/` - View postback logs
- `POST /api/postback/receive/{network_key}/` - Webhook ingestion

### Analytics Endpoints
- `GET /api/postback/insights/` - Daily analytics data
- `POST /api/postback/insights/{id}/detect-anomalies/` - Run anomaly detection
- `POST /api/postback/insights/{id}/recalculate/` - Force recalculation

### Template Endpoints
- `GET /api/postback/templates/` - List templates
- `POST /api/postback/templates/` - Create template
- `POST /api/postback/templates/{id}/render/` - Render template
- `POST /api/postback/templates/{id}/clone/` - Clone template

### Security Endpoints
- `GET /api/postback/ip-whitelists/` - IP whitelist rules
- `POST /api/postback/ip-whitelists/{id}/test-ip/` - Test IP against rule
- `GET /api/postback/rate-limits/` - Rate limit configurations
- `POST /api/postback/rate-limits/{id}/reset-window/` - Reset counting window

## Management Commands

### Analytics and Maintenance
```bash
# Aggregate daily insights with anomaly detection
python manage.py aggregate_postback_insights --detect-anomalies

# Backfill historical data
python manage.py aggregate_postback_insights --backfill 30

# Verify data integrity
python manage.py verify_postback_integrity --model all --fix

# Network-specific operations
python manage.py aggregate_postback_insights --network my-network
```

### Cleanup and Maintenance
```bash
# Cleanup old postback logs
python manage.py cleanup_postbacks --days 90

# Retry failed postbacks
python manage.py retry_failed --network my-network --limit 100
```

## Configuration

### Network Setup
```python
from api.postback.models import NetworkPostbackConfig

network = NetworkPostbackConfig.objects.create(
    name="My CPA Network",
    network_key="my-cpa-network",
    secret_key="your-secret-key",
    signature_algorithm="HMAC_SHA256",
    ip_whitelist=["192.168.1.0/24", "10.0.0.0/8"],
    required_fields=["lead_id", "offer_id", "payout"],
    reward_rules={"default_points": 100}
)
```

### Rate Limiting
```python
from api.postback.models import PostbackRateLimit

rate_limit = PostbackRateLimit.objects.create(
    network=network,
    name="Standard Rate Limit",
    max_per_minute=1000,
    max_per_hour=50000,
    max_per_day=1000000
)
```

### IP Whitelisting
```python
from api.postback.models import PostbackIPWhitelist

whitelist = PostbackIPWhitelist.objects.create(
    network=network,
    name="Primary Data Center",
    ip_address="192.168.1.0/24",
    priority=10,
    description="Main data center IP range"
)
```

## Security Features

### Integrity Hashing
All critical data is protected with SHA-256 hash chaining:
```python
# Verify data integrity
if not insight.verify_integrity():
    raise SecurityError("Data tampering detected!")

# Generate new hash after updates
insight.integrity_hash = insight.generate_integrity_hash()
insight.save()
```

### Signature Verification
```python
from api.postback.utils.signature_validator import validate_full_request

is_valid = validate_full_request(
    network=network,
    signature=request.headers.get('X-Signature'),
    timestamp=request.headers.get('X-Timestamp'),
    nonce=request.headers.get('X-Nonce'),
    body_bytes=request.body,
    path=request.path,
    query_params=request.GET.dict()
)
```

### IP Validation
```python
from api.postback.utils.ip_checker import is_ip_in_whitelist

if not is_ip_in_whitelist(client_ip, network.ip_whitelist):
    raise SecurityError("IP not whitelisted")
```

## Monitoring and Alerting

### Health Monitoring
```python
# Get network health trend
trend = PostbackInsightService.get_network_health_trend(network, days=30)

# Check for anomalies
for day_data in trend:
    if day_data['health_score'] < 70:
        alert_team(f"Low health score: {day_data['health_score']}%")
```

### Performance Metrics
```python
# Get comprehensive summary
summary = PostbackInsightService.get_network_summary(network, days=7)

print(f"Total Received: {summary['total_received']}")
print(f"Success Rate: {summary['avg_health_score']}%")
print(f"Anomaly Days: {summary['anomaly_days']}")
```

## Testing

### Running Tests
```bash
# Run all postback tests
python api/postback/tests/test_runner.py

# Run specific test suites
python manage.py test api.postback.tests.test_new_models
python manage.py test api.postback.tests.test_new_services
python manage.py test api.postback.tests.test_new_api
python manage.py test api.postback.tests.test_management_commands
```

### Test Coverage
The module includes comprehensive test coverage:
- **Model Tests**: 80+ test methods covering all models
- **Service Tests**: Business logic and edge cases
- **API Tests**: Endpoints, serializers, and integration
- **Command Tests**: Management commands with various scenarios

## Performance Considerations

### Database Optimization
- **Composite Indexes**: Optimized for high-volume queries
- **Partitioning Ready**: Designed for horizontal scaling
- **Connection Pooling**: Efficient database utilization

### Caching Strategy
- **Analytics Cache**: Daily insights cached for 24 hours
- **Template Cache**: Frequently used templates cached
- **Rate Limit Cache**: In-memory rate limiting

### Scalability Features
- **Async Processing**: Celery-based postback processing
- **Bulk Operations**: Efficient batch processing
- **Horizontal Scaling**: Multi-process support

## Troubleshooting

### Common Issues

#### High Rejection Rates
```python
# Check rejection reasons
from api.postback.models import PostbackLog, RejectionReason

rejections = PostbackLog.objects.filter(
    rejection_reason=RejectionReason.INVALID_SIGNATURE
).count()

print(f"Signature rejections: {rejections}")
```

#### Rate Limiting Issues
```python
# Check rate limit status
from api.postback.models import PostbackRateLimit

rate_limits = PostbackRateLimit.objects.filter(is_blocked=True)
for rl in rate_limits:
    print(f"Blocked: {rl.name} until {rl.blocked_until}")
```

#### Integrity Verification
```python
# Verify all data integrity
python manage.py verify_postback_integrity --model all --fix
```

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger('api.postback').setLevel(logging.DEBUG)

# Process with detailed logging
log = process_postback_sync(log, signature, timestamp, nonce, body_bytes, path, query_params)
```

## Contributing

### Development Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run migrations: `python manage.py migrate`
4. Create test data: `python manage.py seed_postback_data`
5. Run tests: `python api/postback/tests/test_runner.py`

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all functions
- Add comprehensive docstrings
- Include tests for new features

### Pull Request Process
1. Create feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## License

This module is part of the earning backend system and follows the project's licensing terms.

## Support

For support and questions:
- Check the troubleshooting section
- Review the test cases for usage examples
- Contact the development team
- Check the system logs for detailed error information

## Version History

### v2.0.0 (Current)
- Added SHA-256 integrity hashing
- Implemented advanced analytics with anomaly detection
- Added template management system
- Enhanced IP whitelist and rate limiting
- Comprehensive test coverage
- Performance optimizations

### v1.0.0 (Legacy)
- Basic postback processing
- Simple IP whitelist
- Basic rate limiting
- Minimal analytics
