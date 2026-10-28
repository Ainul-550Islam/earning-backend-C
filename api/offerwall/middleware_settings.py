"""
api/offerwall/middleware_settings.py

Settings snippets to make B2BQuotaMiddleware and
PublisherAPIKeyAuthentication actually work.

FIX 1: B2BQuotaMiddleware defined but never in MIDDLEWARE → quota system dead
FIX 2: PublisherAPIKeyAuthentication defined but never in
        REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] → X-Publisher-Key auth dead

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO USE: Copy these blocks into config/settings.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. MIDDLEWARE — add B2BQuotaMiddleware AFTER SecurityMiddleware:

    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        # ↓ ADD THIS — B2B quota check for X-Publisher-Key requests
        'api.offerwall.b2b.middleware.B2BQuotaMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'corsheaders.middleware.CorsMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

2. REST_FRAMEWORK — add PublisherAPIKeyAuthentication:

    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.SessionAuthentication',
            'rest_framework.authentication.TokenAuthentication',
            # ↓ ADD THIS — allows X-Publisher-Key header auth
            'api.offerwall.publisher.PublisherAPIKeyAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        ...
    }

3. CELERY_BEAT_SCHEDULE — merge offerwall tasks:

    from api.offerwall.celery_schedule import OFFERWALL_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {
        **globals().get('CELERY_BEAT_SCHEDULE', {}),
        **OFFERWALL_BEAT_SCHEDULE,
    }

4. INSTALLED_APPS — ensure offerwall is registered:

    INSTALLED_APPS = [
        ...
        'api.offerwall.apps.OfferwallConfig',  # NOT just 'api.offerwall'
        'api.offerwall.b2b',                   # B2B sub-app
        ...
    ]

5. OFFERWALL-SPECIFIC SETTINGS (add to settings.py):

    # Offerwall feature flags
    OFFERWALL_LARGE_PAYOUT_THRESHOLD = 500   # payouts above this go to payout queue
    OFFERWALL_AUTO_APPROVE_HOURS     = 24    # auto-approve after N hours
    OFFERWALL_CONVERSION_TIMEOUT_HOURS = 72  # auto-reject after N hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RUNTIME VALIDATION — run this in Django shell to verify:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    from django.conf import settings

    # Check middleware
    mw = settings.MIDDLEWARE
    assert 'api.offerwall.b2b.middleware.B2BQuotaMiddleware' in mw, \\
        'B2BQuotaMiddleware not in MIDDLEWARE!'
    print('✓ B2BQuotaMiddleware registered')

    # Check DRF auth
    auth_classes = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', [])
    assert 'api.offerwall.publisher.PublisherAPIKeyAuthentication' in auth_classes, \\
        'PublisherAPIKeyAuthentication not in DRF auth classes!'
    print('✓ PublisherAPIKeyAuthentication registered')

    # Check Celery tasks
    from api.offerwall.tasks import expire_offers
    print(f'✓ Tasks registered: {expire_offers.name}')

    # Check adapter registry
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
    print(f'✓ Adapters: {list(OfferwallAdapterFactory._registry.keys())}')

    # Check processor registry
    from api.offerwall.services.OfferFactory import OfferFactory
    print(f'✓ Processors: {list(OfferFactory._processors.keys())}')
"""

# This file is documentation — not imported at runtime.
# All actual classes are in their respective modules.

OFFERWALL_MIDDLEWARE = [
    'api.offerwall.b2b.middleware.B2BQuotaMiddleware',
]

OFFERWALL_DRF_AUTH_CLASSES = [
    'api.offerwall.publisher.PublisherAPIKeyAuthentication',
]

OFFERWALL_INSTALLED_APPS = [
    'api.offerwall.apps.OfferwallConfig',
    'api.offerwall.b2b',
]
