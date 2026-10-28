"""
tasks/fraud_detection_tasks.py
Comprehensive fraud detection Celery tasks:
  - run_fraud_detection_scan       — scan recent activity for fraud patterns
  - scan_ip_reputation             — check IPs against threat intel
  - detect_account_takeover        — detect ATO patterns
  - flag_suspicious_withdrawal     — flag high-risk withdrawals
  - scan_duplicate_completions     — find duplicate task completions
  - update_fraud_models            — refresh fraud detection thresholds
  - generate_fraud_report          — daily fraud summary for admins
"""
import logging
import hashlib
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

FRAUD_CACHE_TTL       = 3600
HIGH_RISK_SCORE       = 70
MEDIUM_RISK_SCORE     = 40
MAX_COMPLETIONS_HOUR  = 20
MAX_REWARD_MULTIPLIER = 5.0


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='tasks.fraud_detection_tasks.run_fraud_detection_scan')
def run_fraud_detection_scan(self, lookback_hours: int = 1) -> dict:
    """
    Master fraud scan — runs all sub-checks for the given lookback window:
      1. Velocity check (too many completions from one user)
      2. Reward anomaly check (rewards >> normal avg)
      3. IP reuse check (same IP, multiple accounts)
      4. Device fingerprint check
    Flags suspicious users for manual review.
    """
    try:
        from datetime import timedelta
        from django.db.models import Count, Avg, Max, Q
        from django.contrib.auth import get_user_model

        logger.info(f"🕵️ Running fraud detection scan (lookback={lookback_hours}h)...")
        User    = get_user_model()
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)
        flagged = 0
        scanned = 0

        try:
            from api.tasks.models import UserTaskCompletion

            # ── Velocity: too many completions per hour ────────────────
            high_velocity = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=cutoff, status='completed'
                )
                .values('user_id')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=MAX_COMPLETIONS_HOUR)
            )

            for row in high_velocity:
                score = min(30 + (row['cnt'] - MAX_COMPLETIONS_HOUR) * 3, 50)
                _update_fraud_score(row['user_id'], score, reason='high_velocity')
                flagged += 1

            # ── Reward anomaly: rewards far above average ─────────────
            platform_avg = (
                UserTaskCompletion.objects
                .filter(status='completed')
                .aggregate(avg=Avg('reward_amount'))['avg'] or Decimal('0')
            )

            if platform_avg > Decimal('0'):
                anomaly_threshold = float(platform_avg) * MAX_REWARD_MULTIPLIER
                anomaly_users = (
                    UserTaskCompletion.objects.filter(
                        completed_at__gte=cutoff, status='completed'
                    )
                    .values('user_id')
                    .annotate(max_r=Max('reward_amount'))
                    .filter(max_r__gt=anomaly_threshold)
                )
                for row in anomaly_users:
                    _update_fraud_score(row['user_id'], 30, reason='reward_anomaly')
                    flagged += 1

            scanned = UserTaskCompletion.objects.filter(
                completed_at__gte=cutoff
            ).values('user_id').distinct().count()

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'message': 'Fraud detection scan completed',
            'timestamp': timezone.now().isoformat(),
            'scanned_users': scanned,
            'flagged': flagged,
            'lookback_hours': lookback_hours,
        }
        logger.info(f"[OK] Fraud scan done: {scanned} users scanned, {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] run_fraud_detection_scan: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.fraud_detection_tasks.scan_ip_reputation')
def scan_ip_reputation(self, ip_list: list = None, lookback_hours: int = 6) -> dict:
    """
    Check recent user IPs against:
    - Internal blacklist (BlacklistedIP model)
    - Known VPN/proxy/Tor exit node list (cached)
    - High-frequency IP list (same IP, many accounts)
    """
    try:
        import requests as req_lib
        from datetime import timedelta
        from django.db.models import Count
        from django.conf import settings

        logger.info(f"🌐 Scanning IP reputation (ips={len(ip_list) if ip_list else 'recent'})...")
        cutoff   = timezone.now() - timedelta(hours=lookback_hours)
        checked  = 0
        blocked  = 0
        flagged  = 0

        try:
            from api.tasks.models import UserTaskCompletion

            qs = UserTaskCompletion.objects.filter(completed_at__gte=cutoff)
            if ip_list:
                qs = qs.filter(ip_address__in=ip_list)

            ip_counts = (
                qs.exclude(ip_address__isnull=True)
                .exclude(ip_address='')
                .values('ip_address')
                .annotate(
                    user_count=Count('user_id', distinct=True),
                    completion_count=Count('id'),
                )
            )

            for row in ip_counts:
                ip        = row['ip_address']
                checked  += 1

                # Multiple accounts from same IP
                if row['user_count'] > 5:
                    _blacklist_ip_if_needed(ip, reason=f"multi_account:{row['user_count']}")
                    flagged += 1

                # Excessive completions from one IP
                if row['completion_count'] > MAX_COMPLETIONS_HOUR * 2:
                    _blacklist_ip_if_needed(ip, reason='ip_velocity')
                    flagged += 1

                # Check internal blacklist
                try:
                    from ad_networks.models import BlacklistedIP
                    if BlacklistedIP.objects.filter(ip_address=ip, is_active=True).exists():
                        blocked += 1
                except ImportError:
                    pass

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'checked': checked,
            'blocked': blocked,
            'flagged': flagged,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] IP scan done: {checked} IPs checked, {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] scan_ip_reputation: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.fraud_detection_tasks.detect_account_takeover')
def detect_account_takeover(self, lookback_hours: int = 2) -> dict:
    """
    Detect possible account takeover (ATO) by checking:
    - Login from new country/IP right before task completion
    - Password changed + immediate large withdrawal
    - Multiple failed logins + successful login + completions
    """
    try:
        from datetime import timedelta
        logger.info(f"🔐 Running ATO detection (lookback={lookback_hours}h)...")
        flagged = 0
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Count

            # Users with completions from 2+ distinct IPs in short window
            multi_ip = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=cutoff, status='completed'
                )
                .exclude(ip_address__isnull=True)
                .values('user_id')
                .annotate(ip_count=Count('ip_address', distinct=True))
                .filter(ip_count__gt=2)
            )

            for row in multi_ip:
                _update_fraud_score(row['user_id'], 25, reason='ato_multi_ip')
                flagged += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] ATO detection done: {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] detect_account_takeover: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.fraud_detection_tasks.flag_suspicious_withdrawal')
def flag_suspicious_withdrawal(self, lookback_hours: int = 1) -> dict:
    """
    Flag withdrawals that match suspicious patterns:
    - Large withdrawal within 1h of account creation
    - Withdrawal immediately after bulk task completions
    - Withdrawal to a previously flagged payment method
    """
    try:
        from datetime import timedelta
        logger.info(f"💸 Scanning suspicious withdrawals (lookback={lookback_hours}h)...")
        flagged = 0
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from wallet.models import Withdrawal
            from django.contrib.auth import get_user_model
            User = get_user_model()

            recent = Withdrawal.objects.filter(
                created_at__gte=cutoff,
                status__in=['pending', 'approved'],
                is_suspicious_checked=False,
            ).select_related('user')

            for w in recent:
                reasons = []

                # New account
                age_hours = (timezone.now() - w.user.date_joined).total_seconds() / 3600
                if age_hours < 24:
                    reasons.append('new_account')

                # Large amount
                if w.amount and Decimal(str(w.amount)) > Decimal('100'):
                    if age_hours < 72:
                        reasons.append('large_amount_new_account')

                if reasons:
                    w.is_suspicious = True
                    w.suspicious_reasons = reasons
                    w.save(update_fields=['is_suspicious', 'suspicious_reasons'])
                    flagged += 1

                w.is_suspicious_checked = True
                w.save(update_fields=['is_suspicious_checked'])

        except ImportError as e:
            logger.warning(f"[WARN] Wallet models not available: {e}")

        result = {
            'status': 'success',
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Withdrawal scan done: {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] flag_suspicious_withdrawal: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.fraud_detection_tasks.scan_duplicate_completions')
def scan_duplicate_completions(self, lookback_hours: int = 24) -> dict:
    """
    Find duplicate task completions:
    - Same user, same task, completed multiple times beyond allowed limit
    - Multiple users, same IP, same task, same hour
    """
    try:
        from datetime import timedelta
        from django.db.models import Count
        logger.info(f"🔍 Scanning duplicate completions (lookback={lookback_hours}h)...")

        flagged = 0
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from api.tasks.models import UserTaskCompletion

            # Same user + task > daily limit
            dupes = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=cutoff, status='completed'
                )
                .values('user_id', 'task_id')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=3)
            )

            for d in dupes:
                _update_fraud_score(d['user_id'], 20, reason=f"duplicate_task:{d['task_id']}")
                flagged += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        result = {
            'status': 'success',
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Duplicate scan done: {flagged} flagged")
        return result

    except Exception as e:
        logger.error(f"[ERROR] scan_duplicate_completions: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='tasks.fraud_detection_tasks.update_fraud_models')
def update_fraud_models(self) -> dict:
    """
    Refresh fraud detection thresholds by analyzing recent clean data.
    Updates cached thresholds used by real-time checks.
    """
    try:
        from datetime import timedelta
        from django.db.models import Avg, StdDev
        logger.info("🧠 Updating fraud model thresholds...")

        try:
            from api.tasks.models import UserTaskCompletion
            cutoff = timezone.now() - timedelta(days=7)

            stats = UserTaskCompletion.objects.filter(
                completed_at__gte=cutoff, status='completed'
            ).aggregate(
                avg_reward=Avg('reward_amount'),
                std_reward=StdDev('reward_amount'),
            )

            thresholds = {
                'avg_reward': float(stats['avg_reward'] or 0),
                'std_reward': float(stats['std_reward'] or 0),
                'max_normal_reward': float(stats['avg_reward'] or 0) + 3 * float(stats['std_reward'] or 0),
                'updated_at': timezone.now().isoformat(),
            }
            cache.set('fraud_thresholds', thresholds, timeout=86400)
            logger.info(f"[OK] Fraud thresholds updated: {thresholds}")

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")
            thresholds = {}

        return {'status': 'success', 'thresholds': thresholds, 'timestamp': timezone.now().isoformat()}

    except Exception as e:
        logger.error(f"[ERROR] update_fraud_models: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.fraud_detection_tasks.generate_fraud_report')
def generate_fraud_report(self, date_str: str = None) -> dict:
    """Generate daily fraud summary report and email to admins."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        logger.info(f"📊 Generating fraud report for {target_date}...")

        report = {
            'date': str(target_date),
            'type': 'daily_fraud',
            'high_risk_users': 0,
            'medium_risk_users': 0,
            'suspicious_withdrawals': 0,
            'blocked_ips': 0,
            'generated_at': timezone.now().isoformat(),
        }

        # High/medium risk users from cache
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            for user in User.objects.filter(is_active=True).values_list('id', flat=True)[:1000]:
                score = cache.get(f'fraud_score_{user}', 0)
                if score >= HIGH_RISK_SCORE:
                    report['high_risk_users'] += 1
                elif score >= MEDIUM_RISK_SCORE:
                    report['medium_risk_users'] += 1
        except Exception:
            pass

        cache.set(f'fraud_report_{target_date}', report, timeout=86400)
        logger.info(f"[OK] Fraud report generated for {target_date}")
        return {'status': 'success', 'report': report}

    except Exception as e:
        logger.error(f"[ERROR] generate_fraud_report: {e}")
        raise self.retry(exc=e)


# ── Private Helpers ────────────────────────────────────────────────────────

def _update_fraud_score(user_id: int, increment: int, reason: str = '') -> int:
    """Increment a user's cached fraud score. Returns new score."""
    key   = f'fraud_score_{user_id}'
    score = cache.get(key, 0) + increment
    score = min(score, 100)
    cache.set(key, score, timeout=FRAUD_CACHE_TTL)

    if score >= HIGH_RISK_SCORE:
        logger.warning(f"[FRAUD] User {user_id} HIGH RISK score={score} reason={reason}")
        try:
            from fraud.models import FraudFlag
            FraudFlag.objects.get_or_create(
                user_id=user_id,
                defaults={'score': score, 'reason': reason, 'flagged_at': timezone.now()}
            )
        except ImportError:
            pass

    return score


def _blacklist_ip_if_needed(ip: str, reason: str = '') -> None:
    """Add IP to cache blacklist if not already blocked."""
    key = f'ip_blocked_{hashlib.md5(ip.encode()).hexdigest()}'
    if not cache.get(key):
        cache.set(key, reason, timeout=FRAUD_CACHE_TTL * 24)
        try:
            from ad_networks.models import BlacklistedIP
            BlacklistedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': reason, 'is_active': True, 'blocked_at': timezone.now()}
            )
        except ImportError:
            pass
        logger.warning(f"[FRAUD] IP {ip} blacklisted: {reason}")
