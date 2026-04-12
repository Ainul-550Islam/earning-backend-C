# Alerts API Development Guide

## Overview

This guide provides comprehensive information for developers working with the Alerts API, including setup, development workflows, testing, and deployment.

## Development Environment Setup

### Prerequisites

- Python 3.8+
- Django 4.0+
- PostgreSQL 12+
- Redis 6+
- Celery
- Docker (optional but recommended)

### Local Development Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd alerts-api
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database Setup**
```bash
python manage.py migrate
python manage.py createsuperuser
```

6. **Load Initial Data**
```bash
python manage.py loaddata alerts/fixtures/core_alerts.json
python manage.py loaddata alerts/fixtures/channel_alerts.json
```

7. **Start Development Server**
```bash
python manage.py runserver
```

8. **Start Celery Worker** (optional)
```bash
celery -A alerts worker --loglevel=info
```

### Docker Development Setup

1. **Build Docker Image**
```bash
docker build -t alerts-api .
```

2. **Run with Docker Compose**
```bash
docker-compose up -d
```

3. **Run Migrations**
```bash
docker-compose exec web python manage.py migrate
```

## Project Structure

```
api/alerts/
|-- __init__.py
|-- admin/                  # Admin interface
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- models/                  # Database models
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- viewsets/               # API viewsets
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- services/                # Business logic
|   |-- __init__.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- alert_processing.py
|   |   |-- escalation.py
|   |   |-- analytics.py
|   |-- channel/
|   |   |-- __init__.py
|   |   |-- notification.py
|   |   |-- routing.py
|   |   |-- health.py
|   |-- intelligence/
|       |-- __init__.py
|       |-- correlation.py
|       |-- prediction.py
|       |-- anomaly_detection.py
|-- serializers/             # API serializers
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- tasks/                  # Celery tasks
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- signals/                # Django signals
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- templates/alerts/       # Email templates
|   |-- alert_notification.html
|   |-- incident_notification.html
|   |-- escalation_notification.html
|   |-- sla_breach_notification.html
|   |-- report_notification.html
|   |-- oncall_notification.html
|   |-- test_notification.html
|   |-- maintenance_notification.html
|   |-- group_alert_notification.html
|   |-- digest_notification.html
|-- management/              # Django management commands
|   |-- commands/
|   |   |-- __init__.py
|   |   |-- process_alerts.py
|   |   |-- generate_reports.py
|   |   |-- cleanup_alerts.py
|   |   |-- test_alerts.py
|   |   |-- check_health.py
|   |   |-- export_data.py
|   |   |-- import_data.py
|   |   |-- backup_data.py
|   |   |-- restore_data.py
|   |   |-- update_statistics.py
|-- tests/                  # Test suite
|   |-- __init__.py
|   |-- test_models_core.py
|   |-- test_models_threshold.py
|   |-- test_models_channel.py
|   |-- test_models_incident.py
|   |-- test_models_intelligence.py
|   |-- test_models_reporting.py
|   |-- test_viewsets_core.py
|   |-- test_viewsets_threshold.py
|   |-- test_viewsets_channel.py
|   |-- test_viewsets_incident.py
|   |-- test_viewsets_intelligence.py
|   |-- test_viewsets_reporting.py
|   |-- test_services_core.py
|   |-- test_services_channel.py
|   |-- test_services_intelligence.py
|   |-- test_tasks_core.py
|   |-- test_serializers_core.py
|   |-- test_urls.py
|   |-- test_signals_core.py
|   |-- test_management_commands.py
|   |-- test_utilities.py
|   |-- test_integration.py
|   |-- test_performance.py
|   |-- test_fixtures.py
|   |-- test_edge_cases.py
|   |-- test_error_handling.py
|   |-- test_security.py
|   |-- test_comprehensive.py
|-- urls/                  # URL configuration
|   |-- __init__.py
|   |-- core.py
|   |-- threshold.py
|   |-- channel.py
|   |-- incident.py
|   |-- intelligence.py
|   |-- reporting.py
|-- utils/                  # Utility functions
|   |-- __init__.py
|   |-- core.py
|   |-- notification.py
|   |-- metrics.py
|   |-- validation.py
|   |-- datetime.py
|   |-- format.py
|   |-- security.py
|-- docs/                   # Documentation
|   |-- README.md
|   |-- API_REFERENCE.md
|   |-- DEVELOPMENT_GUIDE.md
|   |-- DEPLOYMENT.md
|   |-- TROUBLESHOOTING.md
|   |-- CHANGELOG.md
|-- fixtures/               # Test fixtures
|   |-- core_alerts.json
|   |-- threshold_alerts.json
|   |-- channel_alerts.json
|   |-- incident_alerts.json
|   |-- intelligence_alerts.json
|   |-- reporting_alerts.json
|   |-- system_metrics.json
|-- static/                 # Static files
|-- media/                  # User uploaded files
|-- urls.py                 # Main URL configuration
|-- settings.py             # Django settings
|-- wsgi.py                 # WSGI configuration
|-- asgi.py                 # ASGI configuration
|-- manage.py               # Django management script
|-- requirements.txt         # Production dependencies
|-- requirements-dev.txt     # Development dependencies
|-- Dockerfile              # Docker configuration
|-- docker-compose.yml      # Docker Compose configuration
|-- .env.example           # Environment variables example
|-- .gitignore              # Git ignore file
|-- README.md               # Project README
```

## Development Workflow

### Code Style and Standards

We follow these coding standards:

1. **Python Code Style**
   - Follow PEP 8
   - Use Black for code formatting
   - Use flake8 for linting
   - Use isort for import sorting

2. **Naming Conventions**
   - Classes: `PascalCase`
   - Functions/Variables: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`
   - Private methods: `_leading_underscore`

3. **Documentation**
   - All public methods must have docstrings
   - Use Google-style docstrings
   - Include type hints where appropriate

4. **Testing Standards**
   - Write tests for all new features
   - Maintain >90% code coverage
   - Use descriptive test names

### Git Workflow

1. **Branch Naming**
   - `feature/feature-name`
   - `bugfix/bug-description`
   - `hotfix/critical-fix`
   - `release/version-number`

2. **Commit Messages**
   ```
   type(scope): description
   
   feat(alerts): add new alert correlation feature
   fix(core): resolve memory leak in alert processing
   docs(readme): update installation instructions
   ```

3. **Pull Request Process**
   - Create PR from feature branch
   - Ensure all tests pass
   - Request code review
   - Merge after approval

### Testing Strategy

#### Unit Tests
```bash
# Run all tests
python manage.py test

# Run specific test file
python manage.py test alerts.tests.test_models_core

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

#### Integration Tests
```bash
# Run integration tests
python manage.py test alerts.tests.test_integration

# Run API tests
python manage.py test alerts.tests.test_urls
```

#### Performance Tests
```bash
# Run performance tests
python manage.py test alerts.tests.test_performance
```

### Database Migrations

1. **Create Migration**
```bash
python manage.py makemigrations alerts
```

2. **Apply Migration**
```bash
python manage.py migrate
```

3. **Review Migration**
- Check for data integrity
- Test rollback procedure
- Verify performance impact

### API Development

#### Adding New Endpoints

1. **Create Model** (if needed)
```python
# alerts/models/core.py
class NewModel(models.Model):
    name = models.CharField(max_length=100)
    # ... other fields
```

2. **Create Serializer**
```python
# alerts/serializers/core.py
class NewModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewModel
        fields = '__all__'
```

3. **Create ViewSet**
```python
# alerts/viewsets/core.py
class NewModelViewSet(viewsets.ModelViewSet):
    queryset = NewModel.objects.all()
    serializer_class = NewModelSerializer
```

4. **Add URLs**
```python
# alerts/urls/core.py
path('newmodels/', viewsets.NewModelViewSet.as_view({'get': 'list', 'post': 'create'}), name='newmodel-list'),
```

5. **Write Tests**
```python
# alerts/tests/test_models_core.py
class NewModelTest(TestCase):
    def test_create_newmodel(self):
        # Test implementation
```

#### Custom Actions

Add custom actions to ViewSets:
```python
class AlertRuleViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        # Implementation
```

### Celery Tasks

#### Creating New Tasks

1. **Create Task File**
```python
# alerts/tasks/core.py
from celery import shared_task

@shared_task
def new_task(param1, param2):
    # Implementation
    return result
```

2. **Register Task**
```python
# alerts/__init__.py
default_app_config = 'alerts.celery'
```

3. **Test Task**
```python
# alerts/tests/test_tasks_core.py
class NewTaskTest(TestCase):
    def test_new_task(self):
        # Test implementation
```

### Frontend Integration

#### API Client Examples

**Python:**
```python
import requests

client = requests.Session()
client.auth = ('username', 'token')

response = client.get('http://localhost:8000/api/alerts/rules/')
```

**JavaScript:**
```javascript
fetch('/api/alerts/rules/', {
    headers: {
        'Authorization': 'Token your-token'
    }
})
.then(response => response.json())
```

### Performance Optimization

#### Database Optimization

1. **Use select_related/prefetch_related**
```python
alerts = AlertLog.objects.select_related('rule').prefetch_related('notifications')
```

2. **Add Database Indexes**
```python
class AlertLog(models.Model):
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE)
    
    class Meta:
        indexes = [
            models.Index(fields=['rule', 'created_at']),
        ]
```

3. **Use Caching**
```python
from django.core.cache import cache

def get_alert_rule(rule_id):
    cache_key = f'alert_rule_{rule_id}'
    rule = cache.get(cache_key)
    if rule is None:
        rule = AlertRule.objects.get(id=rule_id)
        cache.set(cache_key, rule, timeout=300)
    return rule
```

#### API Optimization

1. **Pagination**
```python
class AlertRuleViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    pagination_class.page_size = 20
```

2. **Filtering and Searching**
```python
class AlertRuleFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    severity = django_filters.ChoiceFilter(choices=AlertRule.SEVERITY_CHOICES)
```

### Security Best Practices

#### Input Validation
```python
from django.core.validators import MinValueValidator, MaxValueValidator

class AlertRule(models.Model):
    threshold_value = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
```

#### Authentication and Authorization
```python
from rest_framework.permissions import IsAuthenticated

class AlertRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
```

#### Data Protection
```python
from alerts.utils.security import mask_sensitive_data

def log_alert(alert):
    masked_data = mask_sensitive_data(alert.__dict__)
    logger.info(f"Alert created: {masked_data}")
```

### Debugging

#### Logging Configuration
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'alerts.log',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'alerts': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

#### Debug Tools

1. **Django Debug Toolbar**
2. **Query Logging**
```python
from django.db import connection

def log_queries():
    for query in connection.queries:
        print(query['sql'])
```

3. **Performance Profiling**
```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    # Function to profile
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats()
```

## Deployment

### Environment Configuration

#### Development
```bash
DEBUG=True
ALLOWED_HOSTS=['localhost', '127.0.0.1']
DATABASE_URL='postgresql://user:pass@localhost/alerts_dev'
```

#### Staging
```bash
DEBUG=False
ALLOWED_HOSTS=['staging.example.com']
DATABASE_URL='postgresql://user:pass@staging-db/alerts_staging'
```

#### Production
```bash
DEBUG=False
ALLOWED_HOSTS=['api.example.com']
DATABASE_URL='postgresql://user:pass@prod-db/alerts_prod'
```

### Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "alerts.wsgi:application"]
```

#### Docker Compose
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/alerts
    depends_on:
      - db
      - redis
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: alerts
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
  redis:
    image: redis:6-alpine
  worker:
    build: .
    command: celery -A alerts worker --loglevel=info
    depends_on:
      - db
      - redis
```

### Monitoring and Logging

#### Application Monitoring
- Use Sentry for error tracking
- Implement health checks
- Monitor key metrics

#### Log Management
- Centralized logging with ELK stack
- Log rotation policies
- Security event logging

## Contributing

### Getting Started

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

### Code Review Guidelines

1. **Code Quality**
   - Follow style guidelines
   - Ensure tests pass
   - Update documentation

2. **Security Review**
   - Check for vulnerabilities
   - Validate input handling
   - Review permissions

3. **Performance Review**
   - Check database queries
   - Verify caching strategy
   - Test with large datasets

### Release Process

1. **Version Bump**
   - Update version in settings.py
   - Update CHANGELOG.md
   - Create git tag

2. **Testing**
   - Run full test suite
   - Perform integration tests
   - Security scan

3. **Deployment**
   - Deploy to staging
   - Run smoke tests
   - Deploy to production

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check DATABASE_URL
   - Verify database server status
   - Check network connectivity

2. **Celery Task Issues**
   - Check Redis connection
   - Verify worker status
   - Review task logs

3. **Performance Issues**
   - Check database indexes
   - Monitor query performance
   - Review caching strategy

### Debug Checklist

1. **Check Logs**
   - Application logs
   - Database logs
   - System logs

2. **Verify Configuration**
   - Environment variables
   - Database settings
   - Cache configuration

3. **Test Components**
   - Database connectivity
   - External services
   - API endpoints

## Resources

### Documentation
- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Tools and Libraries
- Black: Code formatting
- Flake8: Linting
- Coverage: Code coverage
- Sentry: Error tracking
- New Relic: Performance monitoring

### Community
- Django Forum
- Stack Overflow
- GitHub Discussions
- Slack Channel

## Support

For development support:
- Check this guide first
- Review existing documentation
- Search issue tracker
- Contact development team
