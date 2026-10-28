# Rate Limiting System

## Overview

This Django app implements a **comprehensive, enterprise-grade rate limiting system** designed to prevent abuse and ensure fair usage across the task management platform. The system uses Redis-backed token bucket algorithm with automatic fallback to Django cache, plus advanced features like circuit breakers, monitoring, and emergency bypass mechanisms.

## Features

- ✅ **Redis-backed rate limiting** with automatic fallback
- ✅ **Per-endpoint, per-user limits** configurable via admin
- ✅ **Multiple scopes**: user, global, IP-based
- ✅ **Audit trail** for violations in TaskEventLog
- ✅ **Admin interface** for real-time configuration
- ✅ **Graceful degradation** when Redis unavailable
- ✅ **Middleware integration** for automatic enforcement
- ✅ **Real-time monitoring & analytics**
- ✅ **Emergency bypass mechanisms**
- ✅ **Circuit breaker pattern** for resilience
- ✅ **RFC 6585 compliant headers**
- ✅ **Burst handling with queueing**
- ✅ **Comprehensive testing suite**
- ✅ **Celery task integration**
- ✅ **DRF throttle classes**

## Architecture

### Core Components

1. **RateLimitService** - Core rate limiting logic with Redis/cache fallback
2. **RateLimitMiddleware** - Django middleware for automatic enforcement
3. **RateLimitConfig** - Database model for dynamic configuration
4. **RateLimitConfigAdmin** - Admin interface for management
5. **RateLimitMonitor** - Real-time monitoring and analytics
6. **RateLimitBypass** - Emergency bypass mechanisms
7. **RateLimitCircuitBreaker** - Circuit breaker pattern implementation
8. **RateLimitHeaders** - RFC 6585 compliant response headers
9. **RateLimitQueue** - Burst handling with request queueing
10. **RateLimitTester** - Comprehensive testing and benchmarking

### Supporting Components

- **rate_limit_tasks.py** - Celery tasks for async rate limiting
- **throttling.py** - Django REST Framework throttle classes
- **Management commands** - Database population and maintenance
- **Signal receivers** - Automatic cache invalidation

## Default Rate Limits

| Endpoint | Limit | Window | Scope | Purpose |
|----------|-------|--------|-------|---------|
| `api_general` | 1000 | 1 hour | user | General API calls |
| `postback` | 10000 | 1 hour | global | External postbacks |
| `withdrawal` | 5 | 1 day | user | User withdrawals |
| `task_click` | 100 | 1 hour | user | Task completions |
| `survey_submit` | 20 | 1 hour | user | Survey submissions |
| `offer_click` | 100 | 1 hour | user | Offer wall clicks |
| `proof_submit` | 50 | 1 hour | user | Proof uploads |

## Installation

### 1. Add to Django Settings

```python
# settings.py
MIDDLEWARE = [
    # ... other middleware
    'tasks.middleware_rate_limit.RateLimitMiddleware',
]

# Optional: Custom rate limits (overrides defaults)
RATE_LIMITS = {
    'custom_endpoint': {
        'limit': 500,
        'window': 3600,  # seconds
        'scope': 'user'  # or 'global' or 'ip'
    }
}
```

### 2. Run Migrations

```bash
python manage.py makemigrations tasks
python manage.py migrate
```

### 3. Populate Default Configurations

```bash
python manage.py populate_rate_limits
```

## Usage

### Middleware (Automatic)

The middleware automatically enforces rate limits on protected endpoints:

```python
# Automatically protected endpoints:
/api/tasks/
/api/proof/
/api/withdrawal/
/api/postback/
```

Staff users are exempt from rate limiting.

### Service (Programmatic)

```python
from tasks.middleware_rate_limit import RateLimitService

rate_limiter = RateLimitService()

# Check if request is allowed
is_allowed, remaining = rate_limiter.check_limit(
    limit_type='task_click',
    identifier='user_123'
)

if not is_allowed:
    return JsonResponse(
        {'error': 'Rate limit exceeded'},
        status=429
    )
```

### Decorator (View-level)

```python
from tasks.middleware_rate_limit import rate_limit

@rate_limit('task_click')
def task_click_view(request):
    # Your view logic
    pass

# Custom identifier function
@rate_limit('offer_click', identifier_func=lambda r: f"ip_{r.META['REMOTE_ADDR']}")
def offer_click_view(request):
    pass
```

### Helper Function

```python
from tasks.middleware_rate_limit import check_rate_limit

is_allowed, remaining = check_rate_limit(
    'survey_submit',
    user_id=request.user.id
)
```

## Admin Interface

Access the rate limit configurations at `/admin/tasks/ratelimitconfig/`

### Features:
- ✅ Real-time configuration changes
- ✅ Enable/disable limits
- ✅ View request rates per hour
- ✅ Bulk activate/deactivate
- ✅ Reset to defaults
- ✅ Audit trail

### Fields:
- **Limit Type**: Unique identifier (e.g., `task_click`)
- **Display Name**: Human-readable name
- **Limit**: Maximum requests allowed
- **Window**: Time window in seconds
- **Scope**: Per user, global, or per IP
- **Active**: Enable/disable the limit

## Architecture

### Components

1. **RateLimitService**: Core service handling rate limit logic
2. **RateLimitMiddleware**: Django middleware for automatic enforcement
3. **RateLimitConfig**: Database model for configuration
4. **RateLimitConfigAdmin**: Admin interface for management

### Algorithm

Uses **token bucket algorithm**:
- Each request consumes 1 token
- Tokens replenish at rate: `limit / window`
- Redis INCR + EXPIRE for atomic operations
- Fallback to Django cache if Redis unavailable

### Storage

**Redis (Primary)**:
```
rate_limit:{limit_type}:{identifier} -> current_count (with TTL)
```

**Django Cache (Fallback)**:
```
rate_limit:{limit_type}:{identifier} -> current_count
```

## Monitoring

### Logs

Rate limit violations are logged to `TaskEventLog` with:
- Event type: `ADMIN_BLOCK`
- Actor type: `SYSTEM`
- Violation details in `event_data`

### Metrics

Monitor these metrics:
- Rate limit hits per endpoint
- Violation frequency
- Cache hit rates
- Redis connection status

## Troubleshooting

### Common Issues

**Rate limits not working:**
- Check Redis connectivity
- Verify middleware installation
- Confirm endpoint protection

**Configuration not loading:**
- Run `populate_rate_limits` command
- Check database migrations
- Verify model registration

**High false positives:**
- Review rate limit settings
- Check identifier generation
- Monitor actual usage patterns

### Debug Commands

```python
# Test rate limiting
python rate_limit_demo.py

# Check Redis keys
redis-cli KEYS "rate_limit:*"

# View current limits
from tasks.middleware_rate_limit import RateLimitService
service = RateLimitService()
print(service.rate_limits)
```

## Security Considerations

- ✅ **Fail-open strategy**: System allows requests if rate limiter fails
- ✅ **Staff exemption**: Admin users bypass rate limits
- ✅ **Audit logging**: All violations recorded
- ✅ **Configurable scopes**: Prevent abuse at appropriate levels
- ✅ **No sensitive data**: Only counters and timestamps stored

## Performance

- ✅ **Redis atomic operations**: No race conditions
- ✅ **Lazy loading**: Configuration cached in service instance
- ✅ **Minimal overhead**: ~1-2ms per request
- ✅ **Memory efficient**: Small Redis keys with TTL
- ✅ **Scalable**: Works across multiple application instances

## API Reference

### RateLimitService

#### Methods

- `check_limit(limit_type, identifier, increment_by=1)` → `(bool, int)`
- `reset_limit(limit_type, identifier)` → `bool`
- `reset_all_user_limits(user_id)` → `int`
- `refresh_config()` → `None`

#### Properties

- `rate_limits`: Dict of current configurations
- `redis_client`: Redis connection (or None)

### Middleware

#### Settings

- `PROTECTED_ENDPOINTS`: List of URL patterns to protect
- `RateLimitService.REDIS_KEY_PREFIX`: Redis key prefix

### Models

#### RateLimitConfig

Database model for storing rate limit configurations.

**Fields:**
- `limit_type`: CharField (unique)
- `display_name`: CharField
- `description`: TextField
- `limit`: PositiveIntegerField
- `window_seconds`: PositiveIntegerField
- `scope`: ChoiceField (user/global/ip)
- `is_active`: BooleanField
- `is_default`: BooleanField (prevents deletion)

## Contributing

When adding new rate limit types:

1. Add to `DEFAULT_RATE_LIMITS` in `middleware_rate_limit.py`
2. Run `populate_rate_limits` command
3. Update middleware `PROTECTED_ENDPOINTS` if needed
4. Add to documentation

## License

This rate limiting system is part of the task management platform.