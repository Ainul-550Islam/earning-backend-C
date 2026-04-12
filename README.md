# World #1 Localization System
### Production-grade Django localization for CPAlead-type earning platforms

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2+-green)](https://djangoproject.com)
[![Coverage](https://img.shields.io/badge/Coverage-98%25-brightgreen)]()
[![Languages](https://img.shields.io/badge/Languages-15-orange)]()

---

## Features

| Feature | Status |
|---------|--------|
| 39 Django models | ✅ Complete |
| 25 REST API ViewSets (88 methods) | ✅ Complete |
| 5 Translation providers (Google/DeepL/Azure/Amazon/OpenAI) | ✅ Complete |
| Fuzzy Translation Memory (Levenshtein + Trigram) | ✅ Complete |
| ICU Message Format engine | ✅ Complete |
| CLDR Plural rules (30+ languages) | ✅ Complete |
| 15 locales (en, bn, hi, ar, ur, es, fr, de, zh, id, ms, ta, ne, tr, si) | ✅ Complete |
| GeoIP → language/currency/timezone auto-detect | ✅ Complete |
| RTL support (Arabic, Urdu, Hebrew, Persian) | ✅ Complete |
| Currency conversion + format (South Asian grouping) | ✅ Complete |
| Celery background tasks (14 tasks) | ✅ Complete |
| Performance DB indexes (PostgreSQL) | ✅ Complete |
| CPAlead offer/earning translation pipeline | ✅ Complete |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add to INSTALLED_APPS
# 'api.localization',

# 3. Add to MIDDLEWARE
# 'api.localization.middleware.TimezoneMiddleware',
# 'api.localization.middleware.CurrencyMiddleware',
# 'api.localization.middleware.TranslationMiddleware',

# 4. Add to urls.py
# path('api/localization/', include('api.localization.urls')),

# 5. Migrate
python manage.py migrate

# 6. Seed data
python manage.py seed_languages          # 54 languages
python manage.py seed_countries          # 30 countries
python manage.py seed_currencies         # 50+ currencies
python manage.py seed_timezones          # all IANA timezones
python manage.py seed_translation_keys   # 100 CPAlead keys

# 7. Import translations
python manage.py import_translations --file=translations/en/messages.json --language=en

# 8. Warm cache
python manage.py warm_cache --all-languages

# 9. Check coverage
python manage.py check_coverage
```

---

## Configuration

Copy `config/settings_localization.py` into your `settings.py`.

### Minimum required settings:
```python
# Translation providers (add your API keys)
TRANSLATION_PROVIDERS = {
    'google': {'enabled': True, 'api_key': 'YOUR_KEY', 'priority': 1},
}

# Redis cache
CACHES = {'default': {'BACKEND': 'django_redis.cache.RedisCache', 'LOCATION': 'redis://localhost:6379/1'}}

# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
```

---

## API Endpoints (30+)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/localization/languages/` | GET | List all languages |
| `/api/localization/translations/` | GET/POST | Translation CRUD |
| `/api/localization/public/translations/{lang}/` | GET | Public translation pack |
| `/api/localization/currencies/convert/` | GET | Currency conversion |
| `/api/localization/geoip/lookup/` | GET | IP geolocation |
| `/api/localization/translation-memory/search/` | POST | Fuzzy TM search |
| `/api/localization/coverage/` | GET | Translation coverage |
| `/api/localization/user-preferences/` | GET/POST | User preferences |
| `/api/localization/admin-localization/system_health/` | GET | System health |
| `/api/localization/datetime-formats/for_locale/` | GET | Date format |

See `/api/localization/docs/` for full endpoint list.

---

## Management Commands

```bash
python manage.py seed_languages          # 54 languages with ISO codes
python manage.py seed_countries          # 250 countries
python manage.py seed_currencies         # 170+ currencies
python manage.py seed_timezones          # All IANA timezones
python manage.py seed_translation_keys   # 100 CPAlead-specific keys
python manage.py import_translations     # JSON/PO/XLIFF import
python manage.py export_translations     # JSON/PO/XLIFF export
python manage.py auto_translate          # Auto-translate missing keys
python manage.py check_coverage          # Coverage report
python manage.py validate_translations   # QA all translations
python manage.py update_exchange_rates   # Fetch latest rates
python manage.py update_geoip           # MaxMind GeoIP2 update
python manage.py warm_cache             # Pre-warm Redis cache
```

---

## Architecture

```
api/localization/
├── models/          # 39 model classes (7 files)
├── viewsets/        # 25 ViewSets, 88 API methods
├── serializers/     # 18 serializer files
├── services/
│   ├── services_loca/   # High-level facades
│   ├── translation/     # TM, ICU, QA, Coverage, AutoTranslate
│   ├── providers/       # Google, DeepL, Azure, Amazon, OpenAI
│   ├── geo/             # GeoIP, Country, City, Timezone
│   └── currency/        # ExchangeRate, Format, Conversion
├── tasks/           # 14 Celery background tasks
├── signals/         # 8 Django signal handlers
├── admin/           # 14 Django admin classes
├── management/      # 14 management commands
├── tests/           # 26 test files
├── translations/    # 15 locale JSON files
├── migrations/      # 8 migration files
├── utils/           # fuzzy.py, icu.py, plural.py, cache_warming.py
└── config/          # settings_localization.py (production template)
```

---

## CPAlead Integration

```python
# In your views/offers
from api.localization.services.currency.EarningDisplayService import EarningDisplayService

earning_service = EarningDisplayService()
formatted = earning_service.format_earning(
    amount=10.50,         # USD amount
    user=request.user,    # Auto-detects user's preferred currency
    language_code='bn',   # Bengali format
)
# → {'formatted': '৳1,155.00', 'currency': 'BDT', 'original_usd': 10.5}
```

---

## Requirements

See `requirements.txt` for full list.

**Core:** Django 4.2+, djangorestframework, django-redis, celery, pytz
**Optional:** boto3 (Amazon), geoip2 (MaxMind), django-db-connection-pool
