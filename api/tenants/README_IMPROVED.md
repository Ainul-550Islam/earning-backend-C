# Tenant Management System - Improved Version

A comprehensive, secure, and feature-rich tenant management system for Django applications with multi-tenant support, advanced security, and extensive functionality.

## Overview

This improved tenant system provides complete multi-tenant architecture with enhanced security, comprehensive audit logging, flexible billing management, and extensive customization options. It's designed to handle enterprise-level multi-tenant applications with proper isolation, security, and scalability.

## Features

### Core Features
- **Multi-Tenant Architecture**: Complete tenant isolation with hierarchical support
- **Advanced Security**: Role-based access control, audit logging, rate limiting
- **Billing Management**: Subscription plans, invoicing, payment processing
- **Customizable Settings**: Feature flags, configuration management
- **Audit Logging**: Comprehensive activity tracking for compliance
- **API Integration**: RESTful APIs with proper authentication
- **React Native Support**: Mobile app configuration and features

### Security Features
- **Role-Based Permissions**: Granular access control system
- **API Security**: Rate limiting, IP whitelisting, webhook verification
- **Audit Trails**: Complete logging of all tenant activities
- **Data Encryption**: Secure storage of sensitive data
- **Session Management**: Configurable session timeouts and security
- **Multi-Factor Authentication**: Optional 2FA support

### Billing Features
- **Subscription Plans**: Flexible plan configuration (Basic, Pro, Enterprise, Custom)
- **Trial Management**: Automatic trial expiration and notifications
- **Invoicing**: Automated invoice generation and management
- **Payment Processing**: Stripe integration with webhook support
- **Usage Tracking**: Monitor tenant usage and limits
- **Billing Analytics**: Comprehensive billing reports and insights

### Developer Features
- **Comprehensive APIs**: Full REST API with documentation
- **Middleware Stack**: Request processing and security middleware
- **Signal Handlers**: Automated event processing
- **Cache Management**: Optimized caching for performance
- **Admin Interface**: Rich Django admin with advanced features
- **Testing Support**: Comprehensive test coverage

## Installation

### Requirements
- Django 4.2+
- Python 3.8+
- Redis (for caching)
- PostgreSQL (recommended)

### Setup

1. **Install Dependencies**
```bash
pip install django djangorestframework django-filter drf-spectacular
pip install redis psycopg2-binary stripe
```

2. **Add to Django Settings**
```python
INSTALLED_APPS = [
    # ... other apps
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    'tenants',
]

# Add tenant middleware
MIDDLEWARE = [
    # ... other middleware
    'tenants.middleware_improved.TenantMiddleware',
    'tenants.middleware_improved.TenantSecurityMiddleware',
    'tenants.middleware_improved.TenantContextMiddleware',
    'tenants.middleware_improved.TenantAuditMiddleware',
]

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Tenant configuration
TENANT_CACHE_TIMEOUT = 300
TENANT_RATE_LIMIT_REQUESTS = 1000
TENANT_RATE_LIMIT_WINDOW = 60
CREATE_DEFAULT_TENANT = True
DEFAULT_TENANT_SLUG = 'default'
```

3. **Run Migrations**
```bash
python manage.py migrate
```

4. **Create Superuser**
```bash
python manage.py createsuperuser
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis
REDIS_URL=redis://localhost:6379/1

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourapp.com

# Security
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
```

### Tenant Settings

```python
# Tenant limits and features
TENANT_MAX_USERS_PER_PLAN = {
    'basic': 100,
    'pro': 500,
    'enterprise': 10000,
    'custom': 0,  # Unlimited
}

TENANT_FEATURES_PER_PLAN = {
    'basic': ['referral', 'offerwall'],
    'pro': ['referral', 'offerwall', 'kyc', 'leaderboard'],
    'enterprise': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics'],
    'custom': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics', 'api_access'],
}
```

## Usage

### Creating a Tenant

```python
from tenants.services_improved import tenant_service

# Create a new tenant
tenant_data = {
    'name': 'Acme Corporation',
    'slug': 'acme',
    'plan': 'pro',
    'max_users': 500,
    'admin_email': 'admin@acme.com',
    'owner_email': 'owner@acme.com',
}

tenant = tenant_service.create_tenant(tenant_data, created_by=request.user)
```

### Managing Tenant Settings

```python
from tenants.services_improved import tenant_settings_service

# Update tenant settings
settings_data = {
    'enable_referral': True,
    'enable_kyc': True,
    'min_withdrawal': 10.00,
    'max_withdrawal': 5000.00,
}

settings = tenant_settings_service.update_settings(tenant, settings_data, updated_by=request.user)

# Toggle features
tenant_settings_service.toggle_feature(tenant, 'enable_chat', True, updated_by=request.user)
```

### Billing Management

```python
from tenants.services_improved import tenant_billing_service

# Create subscription
plan_data = {
    'plan': 'pro',
    'monthly_price': 99.99,
    'billing_cycle': 'monthly',
}

billing = tenant_billing_service.create_subscription(tenant, plan_data, created_by=request.user)

# Create invoice
invoice_data = {
    'amount': 99.99,
    'description': 'Monthly subscription fee',
    'due_date': timezone.now() + timedelta(days=7),
}

invoice = tenant_billing_service.create_invoice(tenant, invoice_data, created_by=request.user)
```

### API Usage

```python
# Get tenant information
GET /api/v1/tenants/{tenant_id}/

# Update tenant branding
PATCH /api/v1/tenants/{tenant_id}/update_branding/
{
    "primary_color": "#007bff",
    "secondary_color": "#6c757d",
    "logo": <file>
}

# Get tenant dashboard
GET /api/v1/tenants/{tenant_id}/dashboard/

# Toggle features
POST /api/v1/tenants/{tenant_id}/toggle_feature/
{
    "feature": "enable_referral",
    "enabled": true
}

# Public tenant info (for React Native)
GET /api/v1/app/tenant/
```

## Models

### Tenant
Main tenant model with comprehensive fields for tenant management.

```python
class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, unique=True, null=True)
    admin_email = models.EmailField()
    plan = models.CharField(choices=PLAN_CHOICES)
    status = models.CharField(choices=STATUS_CHOICES)
    max_users = models.PositiveIntegerField(default=100)
    # ... many more fields
```

### TenantSettings
Tenant-specific configuration and feature flags.

```python
class TenantSettings(models.Model):
    enable_referral = models.BooleanField(default=True)
    enable_offerwall = models.BooleanField(default=True)
    enable_kyc = models.BooleanField(default=True)
    min_withdrawal = models.DecimalField(default=5.00)
    max_withdrawal = models.DecimalField(default=10000.00)
    # ... many more settings
```

### TenantBilling
Billing and subscription management.

```python
class TenantBilling(models.Model):
    status = models.CharField(choices=BILLING_STATUS_CHOICES)
    billing_cycle = models.CharField(choices=BILLING_CYCLE_CHOICES)
    monthly_price = models.DecimalField(default=0.00)
    stripe_customer_id = models.CharField(max_length=255, null=True)
    # ... billing fields
```

### TenantInvoice
Invoice management and tracking.

```python
class TenantInvoice(models.Model):
    invoice_number = models.CharField(unique=True)
    amount = models.DecimalField()
    status = models.CharField(choices=INVOICE_STATUS_CHOICES)
    due_date = models.DateTimeField()
    # ... invoice fields
```

### TenantAuditLog
Comprehensive audit logging for security and compliance.

```python
class TenantAuditLog(models.Model):
    action = models.CharField(choices=ACTION_CHOICES)
    details = models.JSONField()
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True)
    # ... audit fields
```

## APIs

### Authentication
All API endpoints require proper authentication. Use JWT tokens or session authentication.

### Endpoints

#### Tenant Management
- `GET /api/v1/tenants/` - List tenants (admin only)
- `POST /api/v1/tenants/` - Create tenant (admin only)
- `GET /api/v1/tenants/{id}/` - Get tenant details
- `PATCH /api/v1/tenants/{id}/` - Update tenant
- `DELETE /api/v1/tenants/{id}/` - Delete tenant (soft delete)

#### Tenant Actions
- `PATCH /api/v1/tenants/{id}/update_branding/` - Update branding
- `POST /api/v1/tenants/{id}/regenerate_api_key/` - Regenerate API key
- `POST /api/v1/tenants/{id}/toggle_feature/` - Toggle feature
- `GET /api/v1/tenants/{id}/dashboard/` - Get dashboard stats
- `POST /api/v1/tenants/{id}/toggle_status/` - Suspend/activate

#### Settings
- `GET /api/v1/tenant-settings/` - List settings
- `PATCH /api/v1/tenant-settings/{id}/` - Update settings

#### Billing
- `GET /api/v1/tenant-billing/` - List billing info
- `PATCH /api/v1/tenant-billing/{id}/` - Update billing
- `POST /api/v1/tenant-billing/{id}/create_invoice/` - Create invoice
- `POST /api/v1/tenant-billing/{id}/extend_trial/` - Extend trial

#### Invoices
- `GET /api/v1/tenant-invoices/` - List invoices
- `GET /api/v1/tenant-invoices/{id}/` - Get invoice details
- `POST /api/v1/tenant-invoices/{id}/mark_paid/` - Mark as paid

#### Public APIs
- `GET /api/v1/app/tenant/` - Public tenant info (React Native)
- `GET /public/{slug}/` - Public tenant details
- `POST /webhook/{slug}/` - Webhook handler

### API Documentation
Visit `/api/docs/` for interactive API documentation (Swagger UI).

## Security

### Permission System
The system uses a comprehensive permission system with multiple layers:

1. **Base Permissions**: `IsTenantOwner`, `IsTenantMember`, `IsActiveTenant`
2. **Security Permissions**: `IsNotSuspended`, `HasValidSubscription`
3. **Feature Permissions**: `ReferralFeaturePermission`, `KYCFeaturePermission`
4. **Combined Permissions**: `FullTenantPermission`, `TenantOwnerOrSuperAdmin`

### Rate Limiting
- API requests: 1000 requests per hour per tenant
- Login attempts: 5 attempts per minute per IP
- Custom rate limits per endpoint

### Audit Logging
All important actions are logged with:
- User information
- IP addresses
- Action details
- Timestamps
- Success/failure status

### Data Protection
- Sensitive data encryption
- Secure API key generation
- Webhook signature verification
- IP whitelisting support

## Admin Interface

The Django admin provides comprehensive management capabilities:

### Tenant Management
- Create, update, delete tenants
- View tenant statistics
- Manage tenant status
- Bulk operations

### Settings Management
- Configure tenant settings
- Toggle features
- Update payout rules
- Manage security settings

### Billing Management
- View billing status
- Create invoices
- Manage subscriptions
- Extend trials

### Audit Logs
- View all activity logs
- Filter by user, action, date
- Export logs for compliance

## Middleware Stack

The system includes comprehensive middleware:

1. **TenantMiddleware**: Identifies current tenant
2. **TenantSecurityMiddleware**: Security checks and rate limiting
3. **TenantContextMiddleware**: Adds tenant context to requests
4. **TenantAuditMiddleware**: Logs all requests
5. **TenantMaintenanceMiddleware**: Handles maintenance mode
6. **TenantCorsMiddleware**: CORS handling
7. **TenantCacheMiddleware**: Cache management

## Testing

### Running Tests
```bash
python manage.py test tenants
```

### Test Coverage
The system includes comprehensive tests for:
- Model operations
- API endpoints
- Permission checks
- Security features
- Billing operations
- Signal handlers

### Test Configuration
```python
# settings/test.py
TENANT_CACHE_TIMEOUT = 1
TENANT_RATE_LIMIT_REQUESTS = 1000
CREATE_DEFAULT_TENANT = False
```

## Performance

### Caching Strategy
- Tenant objects: 5 minutes
- Settings: 10 minutes
- Billing info: 5 minutes
- Feature flags: 5 minutes

### Database Optimization
- Proper indexing on all frequently queried fields
- Select_related and prefetch_related optimizations
- Database connection pooling

### Monitoring
- Request logging
- Performance metrics
- Error tracking
- Usage analytics

## Deployment

### Production Settings
```python
# Security
DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Performance
USE_TZ = True
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 300

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'tenants.log',
        },
    },
    'loggers': {
        'tenants': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Docker Configuration
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "myproject.wsgi:application"]
```

### Environment Setup
```bash
# Production environment
export DEBUG=False
export DATABASE_URL=postgresql://user:pass@db:5432/dbname
export REDIS_URL=redis://redis:6379/1
export SECRET_KEY=your-production-secret-key
```

## Troubleshooting

### Common Issues

1. **Tenant Not Found**
   - Check tenant slug/domain configuration
   - Verify middleware is properly configured
   - Check cache settings

2. **Permission Denied**
   - Verify user permissions
   - Check tenant ownership
   - Review permission classes

3. **Billing Issues**
   - Check Stripe configuration
   - Verify webhook endpoints
   - Review billing status

4. **Performance Issues**
   - Check Redis connection
   - Review cache settings
   - Monitor database queries

### Debug Mode
Enable debug logging:
```python
LOGGING = {
    'loggers': {
        'tenants': {
            'level': 'DEBUG',
        },
    },
}
```

## Contributing

### Development Setup
```bash
git clone <repository>
cd tenant-system
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings
- Write tests

### Pull Requests
1. Fork the repository
2. Create feature branch
3. Add tests
4. Submit pull request

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For support and questions:
- Email: support@yourapp.com
- Documentation: https://docs.yourapp.com
- Issues: https://github.com/yourorg/tenant-system/issues

## Changelog

### Version 2.0.0 (Improved)
- Enhanced security features
- Comprehensive audit logging
- Advanced billing system
- React Native support
- Performance optimizations
- Extensive API documentation
- Comprehensive testing suite

### Version 1.0.0 (Original)
- Basic tenant management
- Simple billing system
- Basic API endpoints
- Limited security features
