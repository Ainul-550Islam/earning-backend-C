"""
Pytest bootstrap for running the `messaging` test suite in isolation,
outside its real host project (earning_backend).

_tenant_stub/apps.py's docstring documents a stub `tenants` app "never
installed when a real tenants app is already on the INSTALLED_APPS
list (see conftest.py)" — this is that file. It was missing from the
delivered package, which meant `pytest` could not run at all outside
the host project: nothing ever called `settings.configure()` /
`django.setup()`, so importing any test module (most import
`messaging.models` directly) raised
`django.core.exceptions.ImproperlyConfigured` before a single test
could even be collected.

Two cases:

  1. Running inside the real host project — its own conftest.py /
     pytest.ini already configured Django (with the *real* `tenants`
     app) before pytest collection reaches this directory. In that
     case `settings.configured` is already True and this file does
     nothing, deferring entirely to the host project's settings.

  2. Running standalone — just this `messaging` package on disk, e.g.
     `pytest` from an unzipped audit deliverable with no host project
     present. `settings.configured` is False, so this file configures
     a minimal Django settings module itself: the same INSTALLED_APPS
     / MIDDLEWARE / REST_FRAMEWORK / CHANNEL_LAYERS wiring that
     settings_messaging.py's own docstring tells a real host project
     to add, plus `_tenant_stub` (registered under the `tenants`
     app_label) so every model's `ForeignKey('tenants.Tenant', ...)`
     resolves, and `_root_urls` (mounting `messaging.urls` at
     `messaging/`, exactly like the real host project does) as
     ROOT_URLCONF so `self.client.post("/messaging/...")` calls in
     the test suite resolve real URLs.
"""
from __future__ import annotations

import django
from django.conf import settings


def pytest_configure(config):
    if settings.configured:
        # Real host project already set things up (real `tenants` app
        # included) — don't touch anything.
        return

    from api.messaging.settings_messaging import (
        MESSAGING_REST_FRAMEWORK,
        MESSAGING_CHANNEL_LAYERS,
        MESSAGING_CACHES,
    )
    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE

    settings.configure(
        DEBUG=True,
        SECRET_KEY="messaging-standalone-test-secret",
        ALLOWED_HOSTS=["*"],
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "rest_framework",
            "rest_framework.authtoken",
            "django_filters",
            "drf_spectacular",
            "channels",
            # Stub so ForeignKey('tenants.Tenant', ...) resolves without
            # the host project's real `tenants` app — see its own
            # docstring for why it is safe to always include here (this
            # branch only runs when nothing configured settings yet, so
            # a real `tenants` app can't already be registered).
            "messaging.tests._tenant_stub",
            "messaging",
        ],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "messaging.middleware.InboxUnreadCountMiddleware",
            "messaging.middleware.MessagingRequestTimingMiddleware",
            "messaging.middleware.WebSocketRateLimitMiddleware",
        ],
        ROOT_URLCONF="messaging.tests._root_urls",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        AUTH_PASSWORD_VALIDATORS=[],
        LANGUAGE_CODE="en-us",
        TIME_ZONE="UTC",
        USE_I18N=True,
        USE_TZ=True,
        STATIC_URL="static/",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        REST_FRAMEWORK={**MESSAGING_REST_FRAMEWORK},
        CHANNEL_LAYERS=MESSAGING_CHANNEL_LAYERS,
        CACHES=MESSAGING_CACHES,
        CELERY_BEAT_SCHEDULE=dict(MESSAGING_BEAT_SCHEDULE),
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        CELERY_BROKER_URL="memory://",
        DEFAULT_FROM_EMAIL="test@example.com",
        CORS_ALLOWED_ORIGINS=[],
    )
    django.setup()

    # ── Celery app, linked to the settings above ────────────────────────
    # tasks.py uses @shared_task throughout (Celery's app-agnostic
    # decorator), which resolves against whichever Celery app is
    # "current" at call time. In the real host project that's whatever
    # Celery() app earning_backend's own celery.py creates and configures
    # from Django settings (standard `app.config_from_object("django.conf
    # :settings", namespace="CELERY")` pattern) — nothing here duplicates
    # that. But *standalone*, nothing ever created a Celery app at all,
    # so @shared_task fell back to Celery's bare default app: default
    # (non-eager) config, default broker, and Celery's own
    # connect-retries-with-backoff behaviour on every .delay()/
    # .apply_async() call. That's harmless for calls the source code
    # itself wraps in try/except (services.py's bot-trigger/index/webhook
    # dispatches fail fast with a caught ConnectionError and a logged
    # warning), but any call site that doesn't have that guard hangs
    # retrying against a broker that was never going to answer - up to
    # whatever timeout the test run enforces. Creating and activating a
    # real Celery app here, with CELERY_TASK_ALWAYS_EAGER actually wired
    # in, makes every task body run synchronously in-process instead.
    from celery import Celery

    celery_app = Celery("messaging_standalone_tests")
    celery_app.config_from_object("django.conf:settings", namespace="CELERY")
    celery_app.set_default()
