"""
tasks/ip_management_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IP Management & Geo-Routing Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ sync_ip_blacklist          — sync IP blacklist to cache
  ✅ update_geo_routing_table   — update country→offer routing
  ✅ block_ip_range             — block a CIDR range
  ✅ unblock_ip                 — remove IP from blacklist
  ✅ refresh_ip_intelligence    — update IP reputation data
  ✅ generate_geo_report        — geo-based traffic report
"""
import logging
import hashlib
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ip_management_tasks.sync_ip_blacklist')
def sync_ip_blacklist(self) -> dict:
    """Load all blocked IPs from DB into cache for fast lookup."""
    try:
        logger.info("🚫 Syncing IP blacklist to cache...")
        synced = 0

        try:
            from ad_networks.models import BlacklistedIP
            blocked = list(
                BlacklistedIP.objects.filter(is_active=True)
                .values_list('ip_address', flat=True)
            )
            for ip in blocked:
                key = f'ip_blocked_{hashlib.md5(ip.encode()).hexdigest()}'
                cache.set(key, 'blacklisted', timeout=None)
                synced += 1

            # Also store as a set for bulk lookups
            cache.set('ip_blacklist_set', set(blocked), timeout=3600)

        except ImportError as e:
            logger.warning(f"[WARN] BlacklistedIP not available: {e}")

        return {'status': 'success', 'synced': synced, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ip_management_tasks.update_geo_routing_table')
def update_geo_routing_table(self) -> dict:
    """
    Build a geo-routing table: country_code → best_offers.
    Used by RTB system to instantly serve country-targeted offers.
    """
    try:
        logger.info("🌍 Updating geo routing table...")
        synced = 0

        try:
            from ad_networks.models import SmartlinkOffer
            from django.db.models import Avg

            # Group offers by country
            geo_routing = {}
            for offer in SmartlinkOffer.objects.filter(is_active=True).values(
                'id', 'external_id', 'countries', 'payout', 'epc', 'quality_score'
            ):
                countries = offer.get('countries') or ['ALL']
                for country in countries:
                    geo_routing.setdefault(country, []).append({
                        'offer_id': offer['external_id'],
                        'payout':   float(offer['payout'] or 0),
                        'epc':      float(offer['epc'] or 0),
                        'score':    float(offer['quality_score'] or 50),
                    })
                    synced += 1

            # Sort each country's offers by score
            for country in geo_routing:
                geo_routing[country].sort(key=lambda x: x['score'], reverse=True)
                geo_routing[country] = geo_routing[country][:20]  # Top 20 per country

            cache.set('geo_routing_table', geo_routing, timeout=1800)

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'countries_mapped': len(cache.get('geo_routing_table', {})),
                'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.ip_management_tasks.block_ip_range')
def block_ip_range(self, cidr: str, reason: str = '', duration_hours: int = 24) -> dict:
    """Block all IPs in a CIDR range."""
    try:
        import ipaddress
        network = ipaddress.ip_network(cidr, strict=False)
        blocked = 0

        # For small networks, block each IP individually
        if network.num_addresses <= 256:
            for ip in network.hosts():
                ip_str = str(ip)
                key    = f'ip_blocked_{hashlib.md5(ip_str.encode()).hexdigest()}'
                cache.set(key, reason or 'cidr_block', timeout=duration_hours * 3600)
                blocked += 1
        else:
            # For large ranges, cache the CIDR itself
            cache.set(f'cidr_blocked_{cidr}', reason, timeout=duration_hours * 3600)
            blocked = network.num_addresses

        logger.warning(f"[IP_MGMT] Blocked CIDR {cidr}: {blocked} IPs for {duration_hours}h")
        return {'status': 'success', 'cidr': cidr, 'blocked': blocked, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.ip_management_tasks.unblock_ip')
def unblock_ip(self, ip_address: str) -> dict:
    """Remove an IP from the blacklist."""
    try:
        key = f'ip_blocked_{hashlib.md5(ip_address.encode()).hexdigest()}'
        cache.delete(key)

        try:
            from ad_networks.models import BlacklistedIP
            BlacklistedIP.objects.filter(ip_address=ip_address).update(is_active=False)
        except ImportError:
            pass

        logger.info(f"[IP_MGMT] Unblocked IP: {ip_address}")
        return {'status': 'success', 'ip': ip_address, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.ip_management_tasks.refresh_ip_intelligence')
def refresh_ip_intelligence(self) -> dict:
    """
    Refresh IP reputation data from external threat feeds.
    Downloads known VPN/proxy/bot IP lists.
    """
    try:
        import requests
        from django.conf import settings
        logger.info("🔄 Refreshing IP intelligence feeds...")

        feeds_loaded = 0
        THREAT_FEEDS = getattr(settings, 'IP_THREAT_FEEDS', [])

        for feed_url in THREAT_FEEDS:
            try:
                resp = requests.get(feed_url, timeout=30)
                if resp.status_code == 200:
                    ips = [line.strip() for line in resp.text.splitlines()
                           if line.strip() and not line.startswith('#')]
                    for ip in ips[:10000]:  # Cap at 10K per feed
                        key = f'ip_blocked_{hashlib.md5(ip.encode()).hexdigest()}'
                        cache.set(key, 'threat_feed', timeout=86400 * 7)
                    feeds_loaded += len(ips)
            except Exception as e:
                logger.warning(f"[WARN] Threat feed {feed_url}: {e}")

        return {
            'status': 'success',
            'ips_loaded': feeds_loaded,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.ip_management_tasks.generate_geo_report')
def generate_geo_report(self, date_str: str = None) -> dict:
    """Generate a geographic traffic distribution report."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum
        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        report = {'date': str(target), 'type': 'geo_daily', 'by_country': []}

        try:
            from ad_networks.models import OfferClick
            day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
            day_end   = day_start + timedelta(days=1)
            by_country = list(
                OfferClick.objects.filter(created_at__gte=day_start, created_at__lt=day_end)
                .values('country')
                .annotate(clicks=Count('id'), unique_users=Count('user_id', distinct=True))
                .order_by('-clicks')[:30]
            )
            report['by_country'] = by_country
        except ImportError:
            pass

        cache.set(f'geo_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/proxy_intelligence/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
@shared_task(name='proxy_intelligence.sync_tor_exit_nodes', bind=True, max_retries=3)
def sync_tor_exit_nodes(self):
    """Sync Tor exit node list from the Tor Project (runs every 6 hours)."""
    try:
        from .detection_engines.tor_detector import TorDetector
        count = TorDetector.sync_exit_nodes()
        logger.info(f"[Task] Tor exit nodes synced: {count} nodes.")
        return {'status': 'success', 'count': count}
    except Exception as exc:
        logger.error(f"[Task] Tor sync failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='proxy_intelligence.send_daily_summary')
def send_daily_risk_summary():
    """Send daily risk summary email to admins."""
    try:
        from .analytics_reporting.daily_risk_summary import DailyRiskSummary
        from django.conf import settings
        recipients = getattr(settings, 'PROXY_INTELLIGENCE_ADMIN_EMAILS', [])
        if not recipients:
            logger.warning("[Task] No admin emails configured for daily summary.")
            return {'status': 'skipped', 'reason': 'no_recipients'}
        DailyRiskSummary().send_email(recipients)
        return {'status': 'sent', 'recipients': len(recipients)}
    except Exception as e:
        logger.error(f"[Task] Daily summary failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.cleanup_old_logs')
def cleanup_old_logs():
    """Remove API request logs older than retention period."""
    try:
        from .models import APIRequestLog, PerformanceMetric
        from .constants import API_LOG_RETENTION_DAYS, PERFORMANCE_METRIC_RETENTION_DAYS
        from datetime import timedelta

        cutoff_api = timezone.now() - timedelta(days=API_LOG_RETENTION_DAYS)
        cutoff_perf = timezone.now() - timedelta(days=PERFORMANCE_METRIC_RETENTION_DAYS)

        deleted_api, _ = APIRequestLog.objects.filter(created_at__lt=cutoff_api).delete()
        deleted_perf, _ = PerformanceMetric.objects.filter(recorded_at__lt=cutoff_perf).delete()

        logger.info(f"[Task] Cleanup: {deleted_api} API logs, {deleted_perf} metrics deleted.")
        return {'api_logs_deleted': deleted_api, 'metrics_deleted': deleted_perf}
    except Exception as e:
        logger.error(f"[Task] Cleanup failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.sync_threat_feeds')
def sync_threat_feeds():
    """Sync all active threat feeds."""
    try:
        from .threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
        results = ThreatFeedIntegrator().sync_all_feeds()
        logger.info(f"[Task] Threat feeds synced: {results}")
        return {'status': 'success', 'results': results}
    except Exception as e:
        logger.error(f"[Task] Threat feed sync failed: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name='proxy_intelligence.expire_blacklist_entries')
def expire_blacklist_entries():
    """Deactivate expired blacklist entries."""
    try:
        from .models import IPBlacklist
        from .cache import PICache

        now = timezone.now()
        expired = IPBlacklist.objects.filter(
            is_active=True,
            is_permanent=False,
            expires_at__lt=now
        )
        count = expired.count()
        ips = list(expired.values_list('ip_address', flat=True))
        expired.update(is_active=False)

        # Invalidate cache for expired IPs
        for ip in ips:
            PICache.invalidate_blacklist(ip)

        logger.info(f"[Task] Expired {count} blacklist entries.")
        return {'expired': count}
    except Exception as e:
        logger.error(f"[Task] Blacklist expiry failed: {e}")
        return {'status': 'error', 'error': str(e)}

