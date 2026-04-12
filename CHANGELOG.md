# CHANGELOG — World #1 Localization System

## v3.0.0 — 2026-04-09 (Current — Final World #1 Build)

### Added — New Files (Part 1-9)
- `utils/fuzzy.py` — Pure Python Levenshtein + Trigram similarity (no deps)
- `utils/icu.py` — ICU MessageFormat parser (plural, select, number, date)
- `utils/plural.py` — CLDR plural rules for 30+ languages (zero/one/two/few/many/other)
- `utils/cache_warming.py` — Pre-warm strategy for Redis caches
- `utils_module.py` — Standalone helpers (RTL check, Accept-Language parser, IP utils)
- `constants.py` — All magic numbers/strings in one place
- `choices.py` — All Django model choices (TextDirection, CalendarSystem, etc.)
- `enums.py` — Python Enums for type-safe usage
- `exceptions.py` — 20 custom API exceptions
- `permissions.py` — IsTranslator, IsReviewer, HasAPIKey, IsOwnerOrAdmin
- `validators.py` — language_code, currency_code, placeholder_match, ICU, postal_code
- `filters.py` — Custom DjangoFilterBackend FilterSets for all models
- `pagination.py` — LocalizationPagePagination, TranslationCursorPagination, etc.
- `config/settings_localization.py` — Complete production settings template
- `services/services_loca/CurrencyService.py` — High-level currency facade
- `services/services_loca/GeoService.py` — High-level geo facade
- `services/translation/ICUMessageEngine.py` — ICU format/validate/translate
- `services/translation/PluralEngine.py` — CLDR plural form management
- `services/translation/LanguagePackBuilder.py` — Language pack compile + CDN
- `services/currency/EarningDisplayService.py` — CPAlead earning display
- `signals/offer_signals.py` — CPAlead offer auto-translation
- `tasks/language_pack_tasks.py` — Build + publish language packs
- `tasks/seed_data_tasks.py` — Celery seed tasks
- `admin/user_preference_admin.py` — UserLanguagePreference admin
- `management/commands/seed_translation_keys.py` — 100 CPAlead keys
- `management/commands/warm_cache.py` — Cache pre-warming
- `migrations/0008_performance_indexes.py` — 10+ PostgreSQL indexes
- `tests/test_permissions_viewset.py` — ViewSet permission tests

### Fixed — Broken/Stub Files
- `services.py` — TODOs 0: real provider call + Haversine nearby cities
- `signals.py` — TODO 0: real mail_admins alert for missing translation spikes
- `services/providers/ProviderRouter.py` — broken import fixed, health caching added
- `services/translation/TranslationEngine.py` — real glossary regex, DNT protection, TM save
- `middleware.py` — BaseMiddleware real attrs, TranslationMiddleware 6-step language detection

### Upgraded
- `services/translation/TranslationMemoryService.py` — full fuzzy (421L): exact + Levenshtein + Trigram
- `services/providers/GoogleTranslateProvider.py` — v2 batch, detect_language, 80+ langs
- `services/providers/DeepLProvider.py` — formality, glossary push, get_usage, bulk
- `services/providers/OpenAIProvider.py` — context batch, domain prompts, rare lang priority
- `viewsets/__init__.py` — TM search: fuzzy scores, TMX import/export, stats (88 methods)
- 15 translation locale JSON files — en/bn: 67 keys, others: 38-40 keys (CPAlead set)

---

## v2.0.0 — 2026-04-09

### Added
- `MicrosoftAzureProvider.py` — Azure Cognitive Services bulk translate
- `AmazonTranslateProvider.py` — Amazon Translate with boto3
- 7 new ViewSets: LocalizedContent, SEO, DateTimeFormat, NumberFormat, TranslationRequest, Config, UserPreference
- 14 missing serializers
- 26 test files (complete test coverage)
- `services/services_loca/UserPreferenceService.py` — expanded 66L → 379L

---

## v1.0.0 — 2026-04-08 (Initial Build)

### Added
- 39 model classes (7 model files)
- 18 original ViewSets
- LocalizationService (952L), LanguageDetector (602L)
- 15 locale JSON files
- Migrations 0001-0007
- 13 admin files, 12 management commands
