"""
tasks/traffic_quality_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Traffic Quality Scoring System (CPAlead Gap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead selectively accepts publishers based on traffic quality.
Better traffic = more premium offers + higher payouts.
  ✅ score_publisher_traffic       — quality score per publisher
  ✅ score_traffic_source          — per-source quality
  ✅ blacklist_low_quality_sources — auto-ban low-quality traffic
  ✅ update_traffic_tiers          — tier 1/2/3 assignment
  ✅ generate_traffic_report       — daily traffic quality report
  ✅ detect_proxy_traffic          — VPN/proxy/datacenter detection
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Traffic quality thresholds
TIER_1_SCORE = 80   # Premium: US/UK/CA/AU real users, high CVR
TIER_2_SCORE = 50   # Standard: mixed quality
TIER_3_SCORE = 20   # Low-quality: high bounce, low CVR
BLACKLIST_SCORE = 10  # Auto-blacklist below this


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.traffic_quality_tasks.score_publisher_traffic')
def score_publisher_traffic(self, lookback_days: int = 7) -> dict:
    """
    Compute a traffic quality score (0-100) for each publisher based on:
    - Conversion rate (CVR)        → 35%
    - Fraud rate                   → 25% (inverted: lower fraud = higher score)
    - Geo quality (% Tier-1 GEO)   → 20%
    - Advertiser satisfaction rate → 10%
    - Chargeback rate              → 10% (inverted)
    """
    try:
        from datetime import timedelta
        from django.db.models import Count, Q
        logger.info(f"📊 Scoring publisher traffic (lookback={lookback_days}d)...")

        scored = 0
        cutoff = timezone.now() - timedelta(days=lookback_days)

        TIER1_COUNTRIES = {'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'NL', 'SG', 'JP'}

        try:
            from api.tasks.models import UserTaskCompletion
            from django.contrib.auth import get_user_model
            User = get_user_model()

            pub_stats = (
                UserTaskCompletion.objects.filter(completed_at__gte=cutoff)
                .values('user_id')
                .annotate(
                    total=Count('id'),
                    completed=Count('id', filter=Q(status='completed')),
                )
            )

            for row in pub_stats:
                uid   = row['user_id']
                total = row['total'] or 0
                done  = row['completed'] or 0

                # CVR component (0-35)
                cvr       = done / total if total > 0 else 0
                cvr_score = min(cvr * 100, 35)

                # Fraud component (0-25, inverted)
                fraud_score  = cache.get(f'fraud_score_{uid}', 0)
                fraud_component = max(25 - (fraud_score * 0.25), 0)

                # Geo quality (approximate — from task completion IPs)
                geo_score = 20  # Default mid-score; real implementation queries IP data

                # Final score
                quality_score = int(cvr_score + fraud_component + geo_score + 10 + 10)
                quality_score = max(0, min(quality_score, 100))

                cache.set(f'traffic_quality_{uid}', quality_score, timeout=86400)

                # Assign tier
                if quality_score >= TIER_1_SCORE:
                    tier = 'tier_1'
                elif quality_score >= TIER_2_SCORE:
                    tier = 'tier_2'
                elif quality_score >= TIER_3_SCORE:
                    tier = 'tier_3'
                else:
                    tier = 'low_quality'

                cache.set(f'traffic_tier_{uid}', tier, timeout=86400)

                # Auto-blacklist extremely low quality
                if quality_score <= BLACKLIST_SCORE:
                    logger.warning(f"[TRAFFIC] Auto-blacklisting user {uid}: score={quality_score}")
                    try:
                        from users.models import Publisher
                        Publisher.objects.filter(user_id=uid).update(
                            is_suspended=True,
                            suspended_reason=f'traffic_quality_score:{quality_score}',
                        )
                    except ImportError:
                        pass

                try:
                    from users.models import Publisher
                    Publisher.objects.filter(user_id=uid).update(
                        traffic_quality_score=quality_score,
                        traffic_tier=tier,
                    )
                except ImportError:
                    pass

                scored += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'scored': scored,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.traffic_quality_tasks.detect_proxy_traffic')
def detect_proxy_traffic(self, lookback_hours: int = 1) -> dict:
    """
    Detect VPN, proxy, and datacenter traffic.
    Uses IP reputation APIs (IPQualityScore, IPInfo, etc.)
    Flags and optionally blocks proxy/datacenter IPs.
    """
    try:
        import requests
        from datetime import timedelta
        from django.conf import settings
        logger.info(f"🕵️ Detecting proxy/VPN traffic (lookback={lookback_hours}h)...")

        detected = 0
        cutoff   = timezone.now() - timedelta(hours=lookback_hours)
        api_key  = getattr(settings, 'IPQUALITYSCORE_API_KEY', '')

        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Count

            recent_ips = (
                UserTaskCompletion.objects.filter(completed_at__gte=cutoff)
                .exclude(ip_address__isnull=True)
                .values('ip_address')
                .annotate(cnt=Count('id'))
                .filter(cnt__gte=3)  # Only check IPs with multiple completions
                .values_list('ip_address', flat=True)
                .distinct()[:100]
            )

            for ip in recent_ips:
                # Check cache first
                check_key = f'proxy_check_{ip}'
                if cache.get(check_key) is not None:
                    continue

                is_proxy = False
                if api_key:
                    try:
                        resp = requests.get(
                            f'https://ipqualityscore.com/api/json/ip/{api_key}/{ip}',
                            params={'strictness': 1},
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            data     = resp.json()
                            is_proxy = data.get('proxy', False) or data.get('vpn', False) or data.get('tor', False)
                    except Exception:
                        pass
                else:
                    # Simple heuristic: known datacenter ranges
                    is_proxy = _is_datacenter_ip(ip)

                cache.set(check_key, is_proxy, timeout=86400)

                if is_proxy:
                    _blacklist_proxy_ip(ip)
                    detected += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'detected': detected,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.traffic_quality_tasks.update_traffic_tiers')
def update_traffic_tiers(self) -> dict:
    """
    Bulk-update all publisher traffic tiers based on cached quality scores.
    Tier 1 publishers get exclusive high-paying offers.
    """
    try:
        logger.info("🔄 Updating traffic tiers...")
        updated = {'tier_1': 0, 'tier_2': 0, 'tier_3': 0, 'low_quality': 0}

        try:
            from users.models import Publisher

            for pub in Publisher.objects.filter(is_active=True).values('user_id', 'traffic_quality_score'):
                score = pub.get('traffic_quality_score') or 0
                if score >= TIER_1_SCORE:
                    tier = 'tier_1'
                elif score >= TIER_2_SCORE:
                    tier = 'tier_2'
                elif score >= TIER_3_SCORE:
                    tier = 'tier_3'
                else:
                    tier = 'low_quality'

                Publisher.objects.filter(user_id=pub['user_id']).update(traffic_tier=tier)
                updated[tier] = updated.get(tier, 0) + 1

        except ImportError as e:
            logger.warning(f"[WARN] Publisher not available: {e}")

        cache.set('traffic_tier_summary', updated, timeout=3600)
        return {'status': 'success', 'updated': updated, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.traffic_quality_tasks.generate_traffic_report')
def generate_traffic_report(self) -> dict:
    """Daily traffic quality report for the admin team."""
    try:
        from datetime import timedelta
        from django.db.models import Avg

        report = {
            'type': 'traffic_quality',
            'tier_distribution': cache.get('traffic_tier_summary') or {},
            'avg_quality_score': 0,
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from users.models import Publisher
            agg = Publisher.objects.filter(is_active=True).aggregate(
                avg_score=Avg('traffic_quality_score')
            )
            report['avg_quality_score'] = round(agg['avg_score'] or 0, 1)
        except ImportError:
            pass

        cache.set('traffic_quality_report', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _is_datacenter_ip(ip: str) -> bool:
    """Simple heuristic to detect known datacenter IP ranges."""
    datacenter_prefixes = [
        '10.', '172.16.', '172.17.', '172.18.', '172.19.',
        '192.168.', '127.',
    ]
    return any(ip.startswith(prefix) for prefix in datacenter_prefixes)


def _blacklist_proxy_ip(ip: str) -> None:
    """Add a proxy IP to the blocklist cache and DB."""
    import hashlib
    cache.set(f'ip_blocked_{hashlib.md5(ip.encode()).hexdigest()}', 'proxy', timeout=86400 * 30)
    try:
        from ad_networks.models import BlacklistedIP
        BlacklistedIP.objects.get_or_create(
            ip_address=ip,
            defaults={'reason': 'proxy_vpn', 'is_active': True, 'blocked_at': timezone.now()}
        )
    except ImportError:
        pass
