"""
Minimal Django settings for the realtime_dashboard test suite.

pytest.ini sets DJANGO_SETTINGS_MODULE = config.settings. Since this app
ships without a full project, the test runner needs its own standalone
settings module. Two ways to use this:

Option A — Point pytest.ini directly at this file:
    [pytest]
    DJANGO_SETTINGS_MODULE = api.realtime_dashboard.tests.settings
    asyncio_mode = auto

Option B — Import this file from your project's config/settings.py in CI:
    from api.realtime_dashboard.tests.settings import *  # noqa

This file is intentionally minimal — only what the test harness needs.
No SECRET_KEY rotation, no CORS, no HTTPS settings needed for testing.
"""

SECRET_KEY = 'test-secret-key-not-for-production-use-only'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'rest_framework',
    'drf_spectacular',          # OpenAPI 3 schema generation (see urls.py: /api/schema/*)
    'django_filters',          # Required for DjangoFilterBackend on viewsets
    'channels',
    'api.realtime_dashboard',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# ── Authentication ────────────────────────────────────────────────────────────

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']

AUTH_USER_MODEL = 'auth.User'

# ── Middleware ────────────────────────────────────────────────────────────────
# Minimal set required for DRF + session auth + admin to work in tests.

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'api.realtime_dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ── Django Channels ────────────────────────────────────────────────────────────
# InMemoryChannelLayer — no Redis required in the test environment.
# Consumer tests that call channel_layer.group_send will use this layer.

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

ASGI_APPLICATION = 'api.realtime_dashboard.asgi.application'

# ── Django REST Framework ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS':
        'api.realtime_dashboard.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER':
        'api.realtime_dashboard.exceptions.custom_exception_handler',
    # Filter backends must be declared for DjangoFilterBackend viewsets to work.
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # Disable throttling in tests to avoid rate-limit failures.
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'metric_update': '1000/min',
        'dashboard_render': '1000/min',
        'websocket_connect': '1000/min',
        'health_check': '1000/min',
        'burst_user': '10000/hour',
    },
    # ADDED (v1.4.0): drf-spectacular generates the OpenAPI 3 schema from
    # this instead of DRF's legacy CoreAPI schema generator.
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ── drf-spectacular (OpenAPI schema) ────────────────────────────────────────────
# ADDED (v1.4.0). Served at /api/schema/, /api/schema/swagger-ui/,
# /api/schema/redoc/ — see urls.py.
SPECTACULAR_SETTINGS = {
    'TITLE': 'Real-time Dashboard Backend API',
    'DESCRIPTION': (
        'WebSocket-backed real-time dashboards: widgets, metrics, layouts, '
        'per-user dashboards, and connection tracking.'
    ),
    'VERSION': '1.4.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # Actions are already grouped by tag via @extend_schema(tags=[...]) on
    # each viewset — component/operation IDs stay as the DRF-generated
    # defaults (e.g. "dashboardwidget_activate_create") rather than being
    # renamed here, so tests asserting on those names elsewhere keep working.
    'SCHEMA_PATH_PREFIX': r'/api/',
    'SORT_OPERATIONS': True,
    # FOUND DURING SCHEMA VALIDATION (v1.4.0): every model exposes both a
    # full Serializer and a *ListSerializer variant, and every one of them
    # has a `status` field — drf-spectacular names enum components after
    # the field name by default, so all of them collide under "Status" and
    # fall back to unreadable auto-hashed names (Status3a5Enum etc.).
    # DashboardWidget.WidgetStatus and UserDashboard.DashboardStatus are
    # additionally *value-identical* (active/inactive/archived), so they
    # are deliberately mapped to the SAME shared name below rather than
    # two different ones — drf-spectacular hashes by value-set, and two
    # different names for one hash raises a hard "duplication" error at
    # schema-generation time.
    'ENUM_NAME_OVERRIDES': {
        'LifecycleStatusEnum':
            'api.realtime_dashboard.models.dashboard_widget.DashboardWidget.WidgetStatus',
        'MetricStatusEnum':
            'api.realtime_dashboard.models.real_time_metric.RealTimeMetric.MetricStatus',
        'ConnectionStatusEnum':
            'api.realtime_dashboard.models.websocket_connection.WebSocketConnection.ConnectionStatus',
    },
}


# ── Celery (synchronous eager mode for tests) ─────────────────────────────────
# task_always_eager=True makes @shared_task run inline in the calling
# thread — no broker, no worker process, no timing issues.

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ── Cache (in-memory, never persists between tests) ───────────────────────────

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'realtime-dashboard-test',
    }
}

# ── Misc ──────────────────────────────────────────────────────────────────────

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Suppress all logging below CRITICAL during tests so test output is clean.
# Individual tests that want to assert on log output can override this
# by adding the assertLogs / caplog fixture.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
}
