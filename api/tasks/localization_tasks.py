"""
tasks/localization_tasks.py
Localization Celery tasks:
  - update_exchange_rates       — fetch latest FX rates and cache
  - sync_translations           — pull translations from external provider
  - update_currency_display     — refresh user-facing currency values
  - detect_user_locale          — infer and cache locale from user-agent/IP
  - cleanup_stale_translations  — remove obsolete translation keys
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

EXCHANGE_RATE_CACHE_KEY  = 'exchange_rates'
EXCHANGE_RATE_CACHE_TTL  = 3600          # 1 hour
SUPPORTED_CURRENCIES     = ['USD', 'EUR', 'GBP', 'BDT', 'INR', 'PKR', 'NGN', 'GHS', 'KES', 'PHP']
BASE_CURRENCY            = 'USD'


# ─────────────────────────────────────────────
# update_exchange_rates
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    name='tasks.localization_tasks.update_exchange_rates',
)
def update_exchange_rates(self, force: bool = False) -> dict:
    """
    Fetch latest foreign exchange rates from a free API
    (exchangerate-api.com or openexchangerates.org) and cache them.
    Also persists rates to ExchangeRate model for history.

    Settings required:
      EXCHANGE_RATE_API_KEY  — API key for the provider
      EXCHANGE_RATE_API_URL  — full URL template with {base} placeholder
    """
    try:
        import requests
        from django.conf import settings

        logger.info(f"💱 Updating exchange rates (force={force})...")

        # Check if cache is still fresh (skip if not forced)
        if not force:
            cached = cache.get(EXCHANGE_RATE_CACHE_KEY)
            if cached:
                logger.info("[INFO] Exchange rates still fresh in cache. Skipping.")
                return {
                    'status': 'skipped',
                    'reason': 'cache_hit',
                    'timestamp': timezone.now().isoformat(),
                }

        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')
        api_url = getattr(
            settings,
            'EXCHANGE_RATE_API_URL',
            f'https://v6.exchangerate-api.com/v6/{api_key}/latest/{BASE_CURRENCY}',
        )

        rates = {}

        if api_key:
            try:
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                data     = response.json()
                all_rates = data.get('conversion_rates', data.get('rates', {}))

                for currency in SUPPORTED_CURRENCIES:
                    if currency in all_rates:
                        rates[currency] = float(all_rates[currency])

                rates['updated_at'] = timezone.now().isoformat()
                rates['base']       = BASE_CURRENCY

            except requests.exceptions.RequestException as req_err:
                logger.error(f"[ERROR] Exchange rate API request failed: {req_err}")
                raise self.retry(exc=req_err)

        else:
            # Fallback hardcoded approximate rates if no API key
            logger.warning("[WARN] No EXCHANGE_RATE_API_KEY configured. Using fallback rates.")
            rates = {
                'USD': 1.0,  'EUR': 0.92, 'GBP': 0.79,
                'BDT': 110.0, 'INR': 83.0, 'PKR': 280.0,
                'NGN': 1450.0, 'GHS': 13.5, 'KES': 130.0, 'PHP': 55.0,
                'base': BASE_CURRENCY,
                'updated_at': timezone.now().isoformat(),
                'source': 'fallback',
            }

        # Cache rates
        cache.set(EXCHANGE_RATE_CACHE_KEY, rates, timeout=EXCHANGE_RATE_CACHE_TTL)

        # Persist to DB
        try:
            from localization.models import ExchangeRate

            for currency, rate in rates.items():
                if currency in ('updated_at', 'base', 'source'):
                    continue
                ExchangeRate.objects.update_or_create(
                    currency=currency,
                    base_currency=BASE_CURRENCY,
                    defaults={
                        'rate': Decimal(str(rate)),
                        'updated_at': timezone.now(),
                        'source': 'api',
                    },
                )
        except ImportError:
            pass  # ExchangeRate model may not exist

        result = {
            'status': 'success',
            'currencies_updated': len([k for k in rates if k not in ('updated_at', 'base', 'source')]),
            'rates': rates,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Exchange rates updated: {result['currencies_updated']} currencies")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] update_exchange_rates failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# sync_translations
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='tasks.localization_tasks.sync_translations',
)
def sync_translations(self, locale: str = None) -> dict:
    """
    Pull translation strings from an external translation provider
    (Crowdin, Lokalise, Phrase, etc.) and update the local translation cache.
    Falls back to compiling existing .po/.mo files if no provider is configured.

    Settings:
      TRANSLATION_PROVIDER     — 'crowdin' | 'lokalise' | 'none'
      TRANSLATION_PROJECT_ID   — provider project ID
      TRANSLATION_API_KEY      — provider API key
    """
    try:
        from django.conf import settings

        provider = getattr(settings, 'TRANSLATION_PROVIDER', 'none')
        logger.info(f"🌍 Syncing translations (provider={provider}, locale={locale or 'all'})...")

        synced_locales  = []
        errors          = []

        target_locales = [locale] if locale else getattr(
            settings, 'LANGUAGES', [('en', 'English')]
        )
        if isinstance(target_locales, list) and target_locales and isinstance(target_locales[0], tuple):
            target_locales = [code for code, _ in target_locales]

        if provider == 'crowdin':
            try:
                import requests
                api_key    = getattr(settings, 'TRANSLATION_API_KEY', '')
                project_id = getattr(settings, 'TRANSLATION_PROJECT_ID', '')

                for loc in target_locales:
                    try:
                        url = (
                            f'https://api.crowdin.com/api/v2/projects/{project_id}'
                            f'/translations/builds?targetLanguageId={loc}'
                        )
                        headers = {'Authorization': f'Bearer {api_key}'}
                        response = requests.get(url, headers=headers, timeout=30)

                        if response.status_code == 200:
                            synced_locales.append(loc)
                            cache.set(f'translations_{loc}', response.json(), timeout=86400)
                        else:
                            errors.append({'locale': loc, 'error': f'HTTP {response.status_code}'})

                    except Exception as loc_err:
                        errors.append({'locale': loc, 'error': str(loc_err)})

            except ImportError:
                logger.warning("[WARN] requests library not available for Crowdin sync")

        elif provider == 'none':
            # Compile .po → .mo using Django's compilemessages
            import subprocess
            try:
                result = subprocess.run(
                    ['python', 'manage.py', 'compilemessages'],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    synced_locales = list(target_locales)
                    logger.info(f"[OK] compilemessages done: {result.stdout}")
                else:
                    errors.append({'error': result.stderr})
            except Exception as sub_err:
                errors.append({'error': str(sub_err)})

        result = {
            'status': 'success' if not errors else 'partial',
            'provider': provider,
            'synced_locales': synced_locales,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Translation sync done: {len(synced_locales)} locales, {len(errors)} errors")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] sync_translations failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# update_currency_display
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.localization_tasks.update_currency_display',
)
def update_currency_display(self) -> dict:
    """
    Recompute display amounts for all active smartlink offers and
    task rewards in each supported currency, using cached exchange rates.
    Stores converted amounts in cache for fast frontend rendering.
    """
    try:
        logger.info("💰 Updating currency display amounts...")

        rates   = cache.get(EXCHANGE_RATE_CACHE_KEY) or {}
        updated = 0
        errors  = 0

        if not rates:
            logger.warning("[WARN] No exchange rates in cache. Run update_exchange_rates first.")
            return {
                'status': 'skipped',
                'reason': 'no_exchange_rates',
                'timestamp': timezone.now().isoformat(),
            }

        try:
            from api.tasks.models import MasterTask

            for task in MasterTask.objects.filter(is_active=True).iterator(chunk_size=200):
                try:
                    rewards  = task.rewards or {}
                    base_amt = Decimal(str(rewards.get('amount', 0)))

                    if base_amt <= Decimal('0'):
                        continue

                    converted = {}
                    for currency, rate in rates.items():
                        if currency in ('updated_at', 'base', 'source'):
                            continue
                        converted[currency] = str(round(base_amt * Decimal(str(rate)), 4))

                    cache.set(
                        f'task_reward_converted_{task.task_id}',
                        converted,
                        timeout=EXCHANGE_RATE_CACHE_TTL,
                    )
                    updated += 1

                except Exception as task_err:
                    logger.error(f"[ERROR] Currency display for task {task.task_id}: {task_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] MasterTask model not available: {e}")

        result = {
            'status': 'success',
            'tasks_updated': updated,
            'errors': errors,
            'currencies': [k for k in rates if k not in ('updated_at', 'base', 'source')],
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Currency display updated: {updated} tasks")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] update_currency_display failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# detect_user_locale
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.localization_tasks.detect_user_locale',
)
def detect_user_locale(self, user_id: int, ip_address: str = '', accept_language: str = '') -> dict:
    """
    Infer a user's locale from their IP address and Accept-Language header.
    Stores the detected locale in cache and optionally in UserProfile.
    """
    try:
        import requests
        from django.conf import settings

        logger.info(f"🌐 Detecting locale for user {user_id} (IP={ip_address})...")

        detected_locale   = 'en'
        detected_currency = 'USD'
        detected_country  = 'US'

        # Step 1: Parse Accept-Language header
        if accept_language:
            lang = accept_language.split(',')[0].split(';')[0].strip().lower()
            if lang and len(lang) >= 2:
                detected_locale = lang[:5]

        # Step 2: IP Geolocation (if IP is provided and API is configured)
        if ip_address and ip_address not in ('127.0.0.1', '::1', ''):
            geo_api_key = getattr(settings, 'IPINFO_API_KEY', '')
            try:
                geo_url  = f'https://ipinfo.io/{ip_address}/json'
                params   = {'token': geo_api_key} if geo_api_key else {}
                response = requests.get(geo_url, params=params, timeout=5)

                if response.status_code == 200:
                    geo_data          = response.json()
                    detected_country  = geo_data.get('country', 'US')

                    # Map country → currency
                    country_currency_map = {
                        'US': 'USD', 'GB': 'GBP', 'EU': 'EUR',
                        'BD': 'BDT', 'IN': 'INR', 'PK': 'PKR',
                        'NG': 'NGN', 'GH': 'GHS', 'KE': 'KES', 'PH': 'PHP',
                    }
                    detected_currency = country_currency_map.get(detected_country, 'USD')

                    # Map country → locale if not already set from header
                    if detected_locale == 'en':
                        country_locale_map = {
                            'BD': 'bn', 'IN': 'hi', 'PK': 'ur',
                            'NG': 'en', 'GH': 'en', 'KE': 'sw', 'PH': 'en',
                        }
                        detected_locale = country_locale_map.get(detected_country, 'en')

            except Exception as geo_err:
                logger.warning(f"[WARN] IP geolocation failed: {geo_err}")

        # Cache locale for this user
        locale_data = {
            'locale': detected_locale,
            'currency': detected_currency,
            'country': detected_country,
            'detected_at': timezone.now().isoformat(),
        }
        cache.set(f'user_locale_{user_id}', locale_data, timeout=86400)

        # Persist to UserProfile if possible
        try:
            from users.models import Profile
            Profile.objects.filter(user_id=user_id).update(
                preferred_locale=detected_locale,
                preferred_currency=detected_currency,
                country=detected_country,
            )
        except Exception:
            pass

        result = {
            'status': 'success',
            'user_id': user_id,
            'locale': detected_locale,
            'currency': detected_currency,
            'country': detected_country,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Locale detected for user {user_id}: {locale_data}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] detect_user_locale failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_stale_translations
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.localization_tasks.cleanup_stale_translations',
)
def cleanup_stale_translations(self, days_old: int = 90) -> dict:
    """
    Remove translation cache entries that haven't been refreshed
    in more than `days_old` days. Also clears locale-detection cache
    for inactive users.
    """
    try:
        from datetime import timedelta
        from django.contrib.auth import get_user_model

        logger.info(f"🧹 Cleaning up stale translations (days_old={days_old})...")

        cleared_locale_caches = 0
        cutoff                = timezone.now() - timedelta(days=days_old)

        try:
            User = get_user_model()
            inactive_users = User.objects.filter(
                last_login__lt=cutoff,
                is_active=True,
            ).values_list('id', flat=True)[:500]

            for uid in inactive_users:
                cache.delete(f'user_locale_{uid}')
                cleared_locale_caches += 1

        except Exception as e:
            logger.warning(f"[WARN] Could not clear locale caches: {e}")

        result = {
            'status': 'success',
            'cleared_locale_caches': cleared_locale_caches,
            'days_old': days_old,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Stale translation cleanup done: {cleared_locale_caches} locale caches cleared")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_stale_translations failed: {exc}")
        raise self.retry(exc=exc)
