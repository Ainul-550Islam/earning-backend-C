# api/admin_panel/settings_check.py
"""Pre-flight settings validator. Call from apps.py ready() or manage.py."""
from django.conf import settings
import os


REQUIRED_SETTINGS = {
    'SECRET_KEY':          'Django secret key',
    'DATABASES':           'Database configuration',
    'INSTALLED_APPS':      'Installed apps list',
    'CELERY_BROKER_URL':   'Celery broker (Redis) URL',
}

OPTIONAL_SETTINGS = {
    'OPENAI_API_KEY':      'OpenAI API key (for AI features)',
    'FCM_SERVER_KEY':      'Firebase Cloud Messaging (for push)',
    'BKASH_APP_KEY':       'bKash payment gateway',
    'NAGAD_MERCHANT_ID':   'Nagad payment gateway',
    'TWILIO_ACCOUNT_SID':  'Twilio SMS (for OTP)',
    'CHANNEL_LAYERS':      'Django Channels (for WebSocket)',
    'SSL_WIRELESS_API_KEY':'SSL Wireless SMS (BD)',
}

REQUIRED_APPS = [
    'api.admin_panel',
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
]


def check_settings(verbose: bool = True) -> dict:
    """Run pre-flight settings check. Returns {ok, warnings, errors}."""
    errors = []
    warnings = []
    ok_list = []

    for key, desc in REQUIRED_SETTINGS.items():
        if not getattr(settings, key, None):
            errors.append(f"MISSING REQUIRED: {key} — {desc}")
        else:
            ok_list.append(key)

    for key, desc in OPTIONAL_SETTINGS.items():
        if not getattr(settings, key, None):
            warnings.append(f"Not configured: {key} — {desc}")
        else:
            ok_list.append(key)

    installed = getattr(settings, 'INSTALLED_APPS', [])
    for app in REQUIRED_APPS:
        if app not in installed:
            errors.append(f"Missing from INSTALLED_APPS: {app}")

    result = {
        'ok': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'configured': ok_list,
        'error_count': len(errors),
        'warning_count': len(warnings),
    }
    if verbose:
        if errors:
            import logging
            logger = logging.getLogger(__name__)
            for e in errors:
                logger.error(f"[SettingsCheck] {e}")
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for w in warnings:
                logger.warning(f"[SettingsCheck] {w}")
    return result


def assert_required_settings():
    """Raise ImproperlyConfigured if required settings are missing."""
    result = check_settings(verbose=False)
    if not result['ok']:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "Admin Panel: Missing required settings:\n" +
            "\n".join(result['errors'])
        )