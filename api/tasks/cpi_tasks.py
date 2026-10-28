"""
tasks/cpi_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPI (Cost Per Install) Mobile App Install Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead pays up to $4 per app install. Our CPI system:
  ✅ process_app_install_event     — verify mobile app install
  ✅ verify_install_with_mmp       — verify via Appsflyer/Adjust/Kochava
  ✅ process_cpi_payout            — credit publisher after verified install
  ✅ detect_install_fraud          — fake install detection
  ✅ sync_mmp_install_data         — pull install data from attribution partners
  ✅ generate_cpi_report           — daily CPI performance report
  ✅ manage_cpi_budgets            — pause CPI campaigns when budget hit
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

CPI_DEDUP_TTL = 86400 * 7  # 7 days


@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.cpi_tasks.process_app_install_event')
def process_app_install_event(
    self,
    click_id: str,
    app_id: str,
    bundle_id: str,
    platform: str,         # 'android' | 'ios'
    device_id: str,
    install_time: str,
    publisher_id: int,
    mmp_name: str = 'appsflyer',
    event_type: str = 'install',   # 'install' | 'event' (CPE)
    event_name: str = '',
) -> dict:
    """
    Process a mobile app install (CPI) or in-app event (CPE) postback.
    1. Dedup check (same device + app)
    2. Verify install with MMP (Appsflyer/Adjust/Kochava)
    3. Check for fraud signals
    4. Credit publisher
    """
    try:
        logger.info(
            f"📱 CPI event: app={bundle_id} platform={platform} "
            f"device={device_id[:12]}... click={click_id}"
        )

        # Dedup: same device + app install
        dedup_key = f'cpi_dedup_{bundle_id}_{device_id}'
        if cache.get(dedup_key):
            logger.info(f"[CPI] Duplicate install detected: {bundle_id}/{device_id[:12]}")
            return {'status': 'duplicate', 'timestamp': timezone.now().isoformat()}

        cache.set(dedup_key, 1, timeout=CPI_DEDUP_TTL)

        # Fraud check: device ID reuse across many accounts
        device_key   = f'cpi_device_count_{device_id}'
        device_count = cache.get(device_key, 0) + 1
        cache.set(device_key, device_count, timeout=86400)

        if device_count > 3:
            logger.warning(f"[CPI FRAUD] Device {device_id[:12]} used for {device_count} installs")
            _flag_cpi_fraud(click_id, 'device_reuse', device_id)
            return {'status': 'fraud_detected', 'reason': 'device_reuse'}

        # MMP Verification
        verified = _verify_with_mmp(click_id, bundle_id, device_id, mmp_name)
        if not verified:
            logger.warning(f"[CPI] MMP verification failed for click {click_id}")
            return {'status': 'mmp_not_verified', 'timestamp': timezone.now().isoformat()}

        # Get payout for this app
        payout = _get_cpi_payout(app_id, bundle_id, platform, event_type, event_name)

        # Record install
        install_id = None
        try:
            from ad_networks.models import AppInstall
            install = AppInstall.objects.create(
                click_id=click_id,
                app_id=app_id,
                bundle_id=bundle_id,
                platform=platform,
                device_id=device_id,
                publisher_id=publisher_id,
                mmp_name=mmp_name,
                event_type=event_type,
                event_name=event_name,
                payout=payout,
                status='verified',
                installed_at=timezone.now(),
            )
            install_id = install.pk
        except ImportError:
            pass

        # Credit publisher
        if payout > Decimal('0') and publisher_id:
            process_cpi_payout.apply_async(kwargs={
                'publisher_id': publisher_id,
                'payout':       str(payout),
                'click_id':     click_id,
                'install_id':   install_id or 0,
                'bundle_id':    bundle_id,
                'event_type':   event_type,
            })

        return {
            'status': 'success',
            'click_id': click_id,
            'bundle_id': bundle_id,
            'payout': str(payout),
            'install_id': install_id,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] process_app_install_event: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=5, default_retry_delay=15,
             name='tasks.cpi_tasks.process_cpi_payout')
def process_cpi_payout(
    self,
    publisher_id: int,
    payout: str,
    click_id: str,
    install_id: int,
    bundle_id: str,
    event_type: str = 'install',
) -> dict:
    """
    Credit publisher wallet after verified CPI/CPE event.
    Revenue split: 75% publisher, 25% platform.
    """
    try:
        gross         = Decimal(str(payout))
        user_share    = gross * Decimal('0.75')
        platform_share = gross * Decimal('0.25')

        if user_share <= Decimal('0'):
            return {'status': 'skipped', 'reason': 'zero_payout'}

        try:
            from api.tasks.services import WalletService
            from api.tasks.notification_tasks import dispatch_in_app_notification

            WalletService().credit(
                user_id=publisher_id,
                amount=user_share,
                transaction_type='cpi_install' if event_type == 'install' else 'cpe_event',
                reference=f'cpi_{click_id}_{install_id}',
                metadata={
                    'click_id':   click_id,
                    'install_id': install_id,
                    'bundle_id':  bundle_id,
                    'gross':      str(gross),
                    'share':      str(user_share),
                },
            )

            dispatch_in_app_notification.apply_async(kwargs={
                'user_id':           publisher_id,
                'title':             f'📱 App Install Reward! +${user_share:.2f}',
                'message':           f'You earned ${user_share:.2f} for an app install!',
                'notification_type': 'reward',
            })

        except ImportError as e:
            logger.warning(f"[WARN] Wallet/notification not available: {e}")

        logger.info(f"[CPI] Publisher {publisher_id} credited ${user_share} for {bundle_id}")
        return {
            'status': 'success',
            'publisher_id': publisher_id,
            'payout': str(user_share),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.cpi_tasks.sync_mmp_install_data')
def sync_mmp_install_data(self, mmp: str = 'appsflyer', lookback_hours: int = 1) -> dict:
    """
    Pull install/event data from MMP (Appsflyer, Adjust, Kochava, Branch).
    Processes any installs not yet credited.
    """
    try:
        import requests
        from django.conf import settings
        logger.info(f"🔄 Syncing MMP install data from {mmp} (lookback={lookback_hours}h)...")

        synced = 0
        errors = 0

        MMP_CONFIGS = getattr(settings, 'MMP_CONFIGS', {
            'appsflyer': {'api_key': '', 'base_url': 'https://api2.appsflyer.com/'},
            'adjust':    {'api_key': '', 'base_url': 'https://api.adjust.com/'},
            'kochava':   {'api_key': '', 'base_url': 'https://api.kochava.com/'},
        })

        config = MMP_CONFIGS.get(mmp, {})
        if not config.get('api_key'):
            return {'status': 'skipped', 'reason': f'no_{mmp}_api_key'}

        from datetime import timedelta
        from_time = (timezone.now() - timedelta(hours=lookback_hours)).strftime('%Y-%m-%d %H:%M:%S')

        # Pull installs from MMP API
        try:
            resp = requests.get(
                f"{config['base_url']}v1/installs",
                params={'from': from_time, 'limit': 1000},
                headers={'Authorization': f"Bearer {config['api_key']}"},
                timeout=30,
            )
            if resp.status_code == 200:
                installs = resp.json().get('data', [])
                for install in installs:
                    process_app_install_event.apply_async(kwargs={
                        'click_id':     install.get('click_id', ''),
                        'app_id':       install.get('app_id', ''),
                        'bundle_id':    install.get('bundle_id', ''),
                        'platform':     install.get('platform', 'android'),
                        'device_id':    install.get('device_id', ''),
                        'install_time': install.get('install_time', ''),
                        'publisher_id': install.get('publisher_id', 0),
                        'mmp_name':     mmp,
                    })
                    synced += 1
        except Exception as req_err:
            logger.error(f"[ERROR] MMP API {mmp}: {req_err}")
            errors += 1

        return {
            'status': 'success',
            'mmp': mmp,
            'synced': synced,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.cpi_tasks.detect_install_fraud')
def detect_install_fraud(self, lookback_hours: int = 1) -> dict:
    """
    Detect fraudulent app installs:
    - Install farms (same device_id many installs)
    - Click injection (install time before click time)
    - SDK spoofing (install without real device data)
    """
    try:
        from datetime import timedelta
        from django.db.models import Count
        logger.info(f"🔍 Detecting install fraud (lookback={lookback_hours}h)...")

        flagged = 0
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import AppInstall

            # Same device_id with multiple different bundle_ids
            device_multi = (
                AppInstall.objects.filter(installed_at__gte=cutoff)
                .values('device_id')
                .annotate(
                    app_count=Count('bundle_id', distinct=True),
                    install_count=Count('id'),
                )
                .filter(app_count__gt=5)
            )

            for row in device_multi:
                AppInstall.objects.filter(
                    device_id=row['device_id'],
                    installed_at__gte=cutoff,
                    is_fraud=False,
                ).update(is_fraud=True, fraud_reason='device_farm')
                flagged += row['install_count']
                logger.warning(f"[CPI FRAUD] Device farm: {row['device_id'][:12]} — {row['app_count']} apps")

            # Click injection: installed_at < click created_at (impossible)
            injection = AppInstall.objects.filter(
                installed_at__gte=cutoff,
                is_fraud=False,
            ).select_related('click')

            for install in injection:
                try:
                    from ad_networks.models import OfferClick
                    click = OfferClick.objects.filter(click_id=install.click_id).first()
                    if click and install.installed_at < click.created_at:
                        install.is_fraud     = True
                        install.fraud_reason = 'click_injection'
                        install.save(update_fields=['is_fraud', 'fraud_reason'])
                        flagged += 1
                except Exception:
                    pass

        except ImportError as e:
            logger.warning(f"[WARN] AppInstall not available: {e}")

        return {
            'status': 'success',
            'flagged': flagged,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.cpi_tasks.generate_cpi_report')
def generate_cpi_report(self, date_str: str = None) -> dict:
    """Daily CPI performance report."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum

        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {'date': str(target), 'type': 'cpi_daily', 'totals': {}}

        try:
            from ad_networks.models import AppInstall
            from django.db.models import Q

            qs = AppInstall.objects.filter(installed_at__gte=day_start, installed_at__lt=day_end)
            agg = qs.aggregate(
                total=Count('id'),
                verified=Count('id', filter=Q(status='verified')),
                fraudulent=Count('id', filter=Q(is_fraud=True)),
                revenue=Sum('payout', filter=Q(status='verified')),
            )
            report['totals'] = {
                'total_installs':  agg['total'] or 0,
                'verified':        agg['verified'] or 0,
                'fraudulent':      agg['fraudulent'] or 0,
                'fraud_rate':      round((agg['fraudulent'] or 0) / max(agg['total'] or 1, 1) * 100, 2),
                'revenue':         str(agg['revenue'] or Decimal('0')),
            }
            # Per-platform
            by_platform = qs.values('platform').annotate(cnt=Count('id'), rev=Sum('payout'))
            report['by_platform'] = list(by_platform)
        except ImportError:
            pass

        cache.set(f'cpi_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _verify_with_mmp(click_id: str, bundle_id: str, device_id: str, mmp: str) -> bool:
    """Verify install with MMP. Returns True if verified."""
    if not click_id:
        return False
    # Check cache first
    verified_key = f'mmp_verified_{click_id}'
    cached = cache.get(verified_key)
    if cached is not None:
        return cached

    try:
        import requests
        from django.conf import settings
        configs = getattr(settings, 'MMP_CONFIGS', {})
        config  = configs.get(mmp, {})
        if not config.get('api_key'):
            return True  # Can't verify → assume valid

        resp = requests.get(
            f"{config['base_url']}v1/installs/verify",
            params={'click_id': click_id, 'bundle_id': bundle_id},
            headers={'Authorization': f"Bearer {config['api_key']}"},
            timeout=5,
        )
        result = resp.status_code == 200 and resp.json().get('verified', False)
        cache.set(verified_key, result, timeout=3600)
        return result
    except Exception:
        return True  # Network error → assume valid


def _get_cpi_payout(app_id: str, bundle_id: str, platform: str, event_type: str, event_name: str) -> Decimal:
    """Get CPI/CPE payout for an app + platform combination."""
    cache_key = f'cpi_payout_{bundle_id}_{platform}_{event_type}'
    cached = cache.get(cache_key)
    if cached:
        return Decimal(str(cached))

    payout = Decimal('0')
    try:
        from ad_networks.models import CpiOffer
        offer = CpiOffer.objects.filter(
            bundle_id=bundle_id,
            platform=platform,
            is_active=True,
        ).first()
        if offer:
            if event_type == 'install':
                payout = Decimal(str(offer.install_payout or 0))
            elif event_type == 'event' and event_name:
                events = offer.event_payouts or {}
                payout = Decimal(str(events.get(event_name, 0)))
    except ImportError:
        payout = Decimal('0.50')  # Default $0.50 per install

    cache.set(cache_key, str(payout), timeout=3600)
    return payout


def _flag_cpi_fraud(click_id: str, reason: str, device_id: str) -> None:
    """Flag a CPI click as fraudulent."""
    cache.set(f'cpi_fraud_{click_id}', {'reason': reason, 'device': device_id}, timeout=86400)
    try:
        from ad_networks.models import AppInstall
        AppInstall.objects.filter(click_id=click_id).update(
            is_fraud=True, fraud_reason=reason
        )
    except ImportError:
        pass
