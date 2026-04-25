# Tenant Management System

A comprehensive Django application for managing multi-tenant SaaS operations including tenant provisioning, billing, analytics, security, and reseller management.

## Features

### Core Tenant Management
- **Tenant Creation & Management**: Complete lifecycle management of tenants
- **Tenant Settings**: Configurable settings and preferences
- **Tenant Billing**: Automated billing and invoice generation
- **Tenant Suspension**: Temporary suspension capabilities

### Plan Management
- **Plan Configuration**: Flexible plan definitions
- **Plan Features**: Granular feature management
- **Plan Upgrades**: Seamless upgrade/downgrade workflows
- **Plan Usage Tracking**: Real-time usage monitoring
- **Plan Quotas**: Resource quota enforcement

### Branding & Customization
- **Tenant Branding**: Custom branding options
- **Domain Management**: Custom domain support
- **Email Configuration**: Custom email settings
- **Social Links**: Social media integration

### Security & Access Control
- **API Key Management**: Secure API key generation and rotation
- **Webhook Configuration**: Event-driven integrations
- **IP Whitelisting**: Network access control
- **Audit Logging**: Comprehensive security audit trails

### Analytics & Monitoring
- **Metrics Collection**: Real-time metrics tracking
- **Health Scoring**: Tenant health assessment
- **Feature Flags**: Feature toggle management
- **Notifications**: In-app and email notifications

### Onboarding & Trials
- **Onboarding Workflows**: Guided tenant setup
- **Trial Management**: Automated trial periods
- **Trial Extensions**: Flexible trial extensions
- **Progress Tracking**: Onboarding progress monitoring

### Reseller Management
- **Reseller Configuration**: Multi-level reseller hierarchies
- **Commission Tracking**: Automated commission calculations
- **Reseller Analytics**: Reseller performance metrics
- **Reseller Invoicing**: Commission invoice generation

## Architecture

### Models
- **Core Models**: `Tenant`, `TenantSettings`, `TenantBilling`, `TenantInvoice`
- **Plan Models**: `Plan`, `PlanFeature`, `PlanUpgrade`, `PlanUsage`, `PlanQuota`
- **Branding Models**: `TenantBranding`, `TenantDomain`, `TenantEmail`, `TenantSocialLink`
- **Security Models**: `TenantAPIKey`, `TenantWebhookConfig`, `TenantIPWhitelist`, `TenantAuditLog`
- **Onboarding Models**: `TenantOnboarding`, `TenantOnboardingStep`, `TenantTrialExtension`
- **Analytics Models**: `TenantMetric`, `TenantHealthScore`, `TenantFeatureFlag`, `TenantNotification`
- **Reseller Models**: `ResellerConfig`, `ResellerInvoice`

### Services
- **Business Logic**: Service layer encapsulating business rules
- **Tenant Services**: `TenantService`, `TenantProvisioningService`, `TenantSuspensionService`
- **Plan Services**: `PlanService`, `PlanUsageService`, `PlanFeatureService`
- **Security Services**: `TenantAuditService`, `TenantEmailService`
- **Analytics Services**: `TenantMetricService`, `TenantHealthScoreService`
- **Reseller Services**: `ResellerService`

### ViewSets
- **REST API**: Django REST Framework viewsets
- **Tenant Endpoints**: Complete CRUD operations
- **Plan Endpoints**: Plan management APIs
- **Security Endpoints**: API key and security management
- **Analytics Endpoints**: Metrics and health score APIs

### Serializers
- **Data Serialization**: DRF serializers for API responses
- **Validation**: Input validation and sanitization
- **Nested Serialization**: Complex object serialization

### Tasks
- **Background Jobs**: Celery tasks for async operations
- **Billing Tasks**: Invoice generation and processing
- **Analytics Tasks**: Metric collection and reporting
- **Maintenance Tasks**: System maintenance and cleanup

### Signals
- **Event Handling**: Django signals for event-driven architecture
- **Tenant Signals**: Lifecycle event handlers
- **Security Signals**: Security event notifications
- **Analytics Signals**: Metric collection triggers

### Management Commands
- **CLI Tools**: Django management commands
- **Tenant Commands**: Tenant management utilities
- **Billing Commands**: Billing and invoice management
- **Analytics Commands**: Reporting and analytics tools

## Installation

1. Add to `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...
    'api.tenants',
]
```

2. Run migrations:
```bash
python manage.py migrate tenants
```

3. Create a superuser:
```bash
python manage.py createsuperuser
```

## Configuration

### Settings
Add the following to your `settings.py`:

```python
# Tenant Settings
TENANTS_DEFAULT_PLAN = 'basic'
TENANTS_TRIAL_DAYS = 14
TENANTS_MAX_TENANTS_PER_USER = 10

# Billing Settings
TENANTS_BILLING_ENABLED = True
TENANTS_DEFAULT_CURRENCY = 'USD'
TENANTS_INVOICE_PREFIX = 'INV'

# Security Settings
TENANTS_API_KEY_LENGTH = 32
TENANTS_WEBHOOK_TIMEOUT = 30
TENANTS_AUDIT_LOG_RETENTION_DAYS = 90

# Analytics Settings
TENANTS_METRICS_RETENTION_DAYS = 365
TENANTS_HEALTH_SCORE_CALCULATION_INTERVAL = 24  # hours
```

### Celery Configuration
Configure Celery for background tasks:

```python
# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
```

## Usage

### Creating a Tenant

```python
from api.tenants.services import TenantService

# Create a new tenant
tenant = TenantService.create_tenant(
    name="My Company",
    slug="my-company",
    admin_email="admin@mycompany.com",
    plan_id=1,
    owner=request.user
)
```

### Managing API Keys

```python
from api.tenants.services import TenantAPIKeyService

# Generate API key
api_key = TenantAPIKeyService.generate_api_key(
    tenant=tenant,
    name="Production API Key",
    permissions=['read', 'write']
)
```

### Collecting Metrics

```python
from api.tenants.services import TenantMetricService

# Record a metric
TenantMetricService.record_metric(
    tenant=tenant,
    metric_type='api_calls',
    value=100,
    metadata={'endpoint': '/api/v1/data'}
)
```

### Calculating Health Scores

```python
from api.tenants.services import TenantHealthScoreService

# Calculate health score
health_score = TenantHealthScoreService.calculate_health_score(
    tenant=tenant,
    period='monthly'
)
```

## API Endpoints

### Tenant Management
- `GET /api/v1/tenants/` - List tenants
- `POST /api/v1/tenants/` - Create tenant
- `GET /api/v1/tenants/{id}/` - Get tenant details
- `PUT /api/v1/tenants/{id}/` - Update tenant
- `DELETE /api/v1/tenants/{id}/` - Delete tenant

### Billing
- `GET /api/v1/billing/` - List billing records
- `GET /api/v1/invoices/` - List invoices
- `POST /api/v1/invoices/` - Create invoice
- `POST /api/v1/invoices/{id}/pay/` - Mark invoice as paid

### Security
- `GET /api/v1/api-keys/` - List API keys
- `POST /api/v1/api-keys/` - Create API key
- `POST /api/v1/api-keys/{id}/rotate/` - Rotate API key
- `GET /api/v1/audit-logs/` - List audit logs

### Analytics
- `GET /api/v1/metrics/` - List metrics
- `POST /api/v1/metrics/` - Record metric
- `GET /api/v1/health-scores/` - Get health scores
- `GET /api/v1/feature-flags/` - List feature flags

## Management Commands

### Tenant Management
```bash
# Create a tenant
python manage.py tenants create --name "My Company" --email "admin@company.com"

# List tenants
python manage.py tenants list --status active

# Suspend tenant
python manage.py tenants suspend --tenant-id 1 --reason "Payment overdue"
```

### Billing Management
```bash
# Generate invoices
python manage.py billing generate-invoices --period monthly

# Send payment reminders
python manage.py billing send-reminders --days-overdue 7
```

### Analytics
```bash
# Collect metrics
python manage.py metrics collect --period daily

# Generate health scores
python manage.py metrics calculate-health-scores
```

### Security
```bash
# Rotate API keys
python manage.py security rotate-api-keys --days-old 90

# Security scan
python manage.py security scan --tenant-id 1
```

## Testing

Run the test suite:

```bash
# Run all tests
python manage.py test api.tenants

# Run specific test module
python manage.py test api.tenants.tests.test_models

# Run with coverage
coverage run --source='.' manage.py test api.tenants
coverage report
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the test cases for usage examples

## Changelog

### Version 1.0.0
- Initial release
- Complete tenant management system
- REST API endpoints
- Background task processing
- Comprehensive test suite
- Documentation and management commands
