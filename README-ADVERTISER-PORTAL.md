# Advertiser Portal

A comprehensive Django REST API for managing advertising campaigns, creatives, targeting, analytics, and billing for advertisers.

## Overview

The Advertiser Portal is a robust, scalable, and feature-rich advertising management system built with Django and Django REST Framework. It provides complete functionality for advertisers to manage their campaigns, track performance, handle billing, and optimize their advertising efforts.

## Features

### 🎯 Core Features
- **Campaign Management**: Create, manage, and optimize advertising campaigns
- **Creative Management**: Upload, approve, and manage ad creatives
- **Targeting Management**: Advanced targeting options including geographic, demographic, and behavioral targeting
- **Analytics & Reporting**: Comprehensive analytics with real-time metrics and custom reports
- **Billing Management**: Complete billing system with invoices, payments, and credit management
- **User Management**: Role-based access control for advertiser users
- **Fraud Detection**: Advanced fraud detection and prevention mechanisms

### 🚀 Advanced Features
- **Real-time Analytics**: Live performance metrics and dashboards
- **A/B Testing**: Built-in A/B testing framework for campaign optimization
- **Multi-currency Support**: Support for multiple currencies and automatic conversion
- **API Webhooks**: Extensive webhook system for integrations
- **Auto-optimization**: AI-powered campaign optimization
- **Custom Reports**: Flexible reporting system with scheduled reports
- **Audit Logging**: Comprehensive audit trail for compliance

## Architecture

### 📁 Project Structure
```
api/advertiser_portal/
├── __init__.py                 # App initialization
├── apps.py                    # Django app configuration
├── admin.py                   # Django admin configuration
├── urls.py                    # Main URL configuration
├── models.py                  # Abstract base models
├── schemas.py                 # Pydantic schemas
├── routes.py                  # DRF ViewSets
├── services.py                # Business logic services
├── repository.py              # Data access layer
├── validators.py              # Custom validators
├── utils.py                   # Utility functions
├── dependencies.py            # Dependency injection
├── constants.py              # Application constants
├── enums.py                   # Enum definitions
├── exceptions.py              # Custom exceptions
├── middleware.py              # Custom middleware
├── cache.py                   # Cache management
├── config.py                  # Configuration management
├── tasks.py                   # Background tasks
├── signals.py                 # Django signals
├── events.py                  # Event system
├── hooks.py                   # Plugin hooks
├── plugins.py                 # Plugin system
├── database_models/           # Database models
│   ├── __init__.py
│   ├── advertiser_model.py
│   ├── campaign_model.py
│   ├── creative_model.py
│   ├── targeting_model.py
│   ├── impression_model.py
│   ├── click_model.py
│   ├── conversion_model.py
│   ├── billing_model.py
│   ├── analytics_model.py
│   ├── fraud_detection_model.py
│   ├── ab_testing_model.py
│   ├── integration_model.py
│   ├── reporting_model.py
│   ├── notification_model.py
│   ├── user_model.py
│   ├── audit_model.py
│   └── configuration_model.py
├── advertiser_management/      # Advertiser management module
│   ├── __init__.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── campaign_management/        # Campaign management module
│   ├── __init__.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── creative_management/        # Creative management module
│   ├── __init__.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── targeting_management/       # Targeting management module
│   ├── __init__.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── analytics_management/       # Analytics management module
│   ├── __init__.py
│   ├── services.py
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
└── billing_management/         # Billing management module
    ├── __init__.py
    ├── services.py
    ├── views.py
    ├── serializers.py
    └── urls.py
```

## 🏗️ Architecture Patterns

### Service Layer Architecture
- **Services**: Business logic encapsulated in service classes
- **Repository Pattern**: Data access layer for clean separation of concerns
- **Dependency Injection**: Flexible dependency management
- **Event-Driven Architecture**: Loose coupling through events and hooks

### Database Design
- **UUID Primary Keys**: Globally unique identifiers
- **Soft Deletes**: Data retention with soft deletion
- **Audit Logging**: Comprehensive audit trails
- **Timestamps**: Created/updated timestamps for all entities
- **Status Management**: Consistent status fields across models

### API Design
- **RESTful Design**: Standard REST API patterns
- **Versioning**: API versioning support
- **Pagination**: Consistent pagination across all endpoints
- **Filtering**: Advanced filtering capabilities
- **Search**: Full-text search where applicable
- **Rate Limiting**: API rate limiting and throttling

## 🛠️ Technology Stack

### Backend
- **Django 4.2+**: Web framework
- **Django REST Framework 3.14+**: API framework
- **PostgreSQL**: Primary database
- **Redis**: Caching and session storage
- **Celery**: Background task processing

### Additional Libraries
- **Stripe**: Payment processing
- **Pillow**: Image processing
- **Pandas**: Data analysis
- **Plotly**: Data visualization
- **Sentry**: Error monitoring
- **Celery**: Background tasks

## 📊 Database Models

### Core Entities
- **Advertiser**: Main advertiser account
- **Campaign**: Advertising campaigns
- **Creative**: Ad creatives and assets
- **Targeting**: Campaign targeting configuration
- **Impression**: Ad impression tracking
- **Click**: Click tracking
- **Conversion**: Conversion tracking
- **BillingProfile**: Billing information
- **Invoice**: Invoicing system
- **PaymentTransaction**: Payment processing

### Supporting Models
- **User**: User management
- **Notification**: Notification system
- **AuditLog**: Audit trail
- **AnalyticsReport**: Analytics and reporting
- **FraudDetection**: Fraud detection rules and alerts

## 🔧 Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Node.js 16+ (for frontend development)

### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd earning_backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements-advertiser-portal.txt
```

4. **Environment configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database setup**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create superuser**
```bash
python manage.py createsuperuser
```

7. **Run the development server**
```bash
python manage.py runserver
```

## 🔐 Authentication & Security

### Authentication Methods
- JWT Token Authentication
- OAuth 2.0 Support
- Session-based Authentication

### Security Features
- Rate Limiting
- CORS Configuration
- SQL Injection Prevention
- XSS Protection
- CSRF Protection
- Input Validation
- Data Encryption

## 📚 API Documentation

### Base URL
```
http://localhost:8000/api/v1/
```

### Main Endpoints

#### Advertiser Management
- `GET /advertiser/` - List advertisers
- `POST /advertiser/` - Create advertiser
- `GET /advertiser/{id}/` - Get advertiser details
- `PUT /advertiser/{id}/` - Update advertiser
- `DELETE /advertiser/{id}/` - Delete advertiser

#### Campaign Management
- `GET /campaign/` - List campaigns
- `POST /campaign/` - Create campaign
- `GET /campaign/{id}/` - Get campaign details
- `PUT /campaign/{id}/` - Update campaign
- `DELETE /campaign/{id}/` - Delete campaign
- `POST /campaign/{id}/activate/` - Activate campaign
- `POST /campaign/{id}/pause/` - Pause campaign

#### Creative Management
- `GET /creative/` - List creatives
- `POST /creative/` - Create creative
- `GET /creative/{id}/` - Get creative details
- `PUT /creative/{id}/` - Update creative
- `DELETE /creative/{id}/` - Delete creative

#### Analytics
- `GET /analytics/campaign/` - Campaign analytics
- `GET /analytics/creative/` - Creative analytics
- `GET /analytics/advertiser/` - Advertiser analytics
- `POST /analytics/attribution/` - Calculate attribution

#### Billing
- `GET /billing/profiles/` - List billing profiles
- `POST /billing/profiles/` - Create billing profile
- `GET /billing/invoices/` - List invoices
- `POST /billing/invoices/` - Create invoice
- `POST /billing/payments/` - Process payment

### API Documentation
- Swagger UI: `http://localhost:8000/api/v1/docs/`
- ReDoc: `http://localhost:8000/api/v1/redoc/`

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python manage.py test

# Run with coverage
pytest --cov=api/advertiser_portal

# Run specific test file
pytest api/advertiser_portal/tests/test_campaigns.py
```

### Test Structure
```
api/advertiser_portal/tests/
├── __init__.py
├── test_models.py
├── test_services.py
├── test_views.py
├── test_serializers.py
├── test_utils.py
└── fixtures/
```

## 📈 Performance

### Optimization Features
- Database Indexing
- Query Optimization
- Caching Strategy
- Background Tasks
- Connection Pooling

### Monitoring
- Performance Metrics
- Database Query Analysis
- API Response Times
- Error Tracking

## 🚀 Deployment

### Production Setup
1. **Environment Configuration**
2. **Database Migration**
3. **Static Files Collection**
4. **Cache Configuration**
5. **Background Workers Setup**
6. **Load Balancer Configuration**

### Docker Deployment
```bash
# Build Docker image
docker build -t advertiser-portal .

# Run with Docker Compose
docker-compose up -d
```

## 🤝 Contributing

### Development Guidelines
1. Follow PEP 8 coding standards
2. Write comprehensive tests
3. Update documentation
4. Use type hints
5. Follow Git workflow

### Code Review Process
1. Create feature branch
2. Write tests
3. Submit pull request
4. Code review
5. Merge to main

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Email: support@advertiser-portal.com
- Documentation: https://docs.advertiser-portal.com

## 🔮 Roadmap

### Upcoming Features
- Machine Learning Optimization
- Advanced Fraud Detection
- Multi-tenant Support
- GraphQL API
- Mobile SDK
- Advanced Analytics Dashboard
- Real-time Bidding Integration

### Version History
- **v1.0.0**: Initial release with core features
- **v1.1.0**: Added A/B testing and advanced analytics
- **v1.2.0**: Enhanced billing and payment features
- **v1.3.0**: Improved fraud detection and security
- **v2.0.0**: Major architecture overhaul and performance improvements

---

**Advertiser Portal** - Empowering advertisers with powerful, scalable, and intuitive campaign management tools.
