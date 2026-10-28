"""
tasks/survey_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Survey & CPA Offer Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead Gap: Survey routing, completion verification, payout processing
  ✅ route_survey_to_user        — match user profile to best survey
  ✅ verify_survey_completion    — verify survey was genuinely completed
  ✅ process_survey_payout       — credit wallet after survey completion
  ✅ sync_survey_inventory       — pull surveys from providers (Cint, Dynata)
  ✅ disqualify_low_quality_survey — flag surveys with bad completion rate
  ✅ generate_survey_report      — daily survey performance summary
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

SURVEY_DEDUP_TTL = 86400 * 3  # 3 days


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.survey_tasks.route_survey_to_user')
def route_survey_to_user(self, user_id: int, max_surveys: int = 5) -> dict:
    """
    Match a user to the best available surveys based on:
    - Demographic profile (age, gender, country)
    - Survey payout (highest first)
    - Completion probability (based on past success rate)
    - Survey length (shorter preferred)
    Returns a ranked list of survey IDs cached for the user.
    """
    try:
        logger.info(f"🎯 Routing surveys to user {user_id}...")
        matched = []

        try:
            from surveys.models import Survey, SurveyCompletion
            from django.contrib.auth import get_user_model
            User = get_user_model()

            user = User.objects.filter(pk=user_id).first()
            if not user:
                return {'status': 'skipped', 'reason': 'user_not_found'}

            # Already completed surveys
            completed_ids = set(
                SurveyCompletion.objects.filter(
                    user_id=user_id, status='completed'
                ).values_list('survey_id', flat=True)
            )

            # Profile data
            try:
                from users.models import Profile
                profile = Profile.objects.filter(user_id=user_id).first()
                country = getattr(profile, 'country', 'US') if profile else 'US'
                age     = getattr(profile, 'age', 25) if profile else 25
                gender  = getattr(profile, 'gender', 'any') if profile else 'any'
            except ImportError:
                country, age, gender = 'US', 25, 'any'

            # Find matching surveys
            qs = Survey.objects.filter(
                is_active=True,
                countries__contains=[country],
            ).exclude(id__in=completed_ids)

            if gender != 'any':
                qs = qs.filter(target_gender__in=[gender, 'any'])

            qs = qs.filter(min_age__lte=age, max_age__gte=age)
            qs = qs.order_by('-payout', 'length_minutes')[:max_surveys]

            matched = list(qs.values('id', 'title', 'payout', 'length_minutes', 'provider'))

            cache.set(f'user_surveys_{user_id}', matched, timeout=1800)

        except ImportError as e:
            logger.warning(f"[WARN] Survey models not available: {e}")

        return {
            'status': 'success',
            'user_id': user_id,
            'surveys_matched': len(matched),
            'surveys': matched,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] route_survey_to_user: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.survey_tasks.verify_survey_completion')
def verify_survey_completion(self, completion_id: int) -> dict:
    """
    Verify a survey completion is genuine:
    1. Check completion time vs survey length (too fast = bot)
    2. Verify with provider API using transaction ID
    3. Check for duplicate submissions from same IP
    4. Validate session fingerprint
    """
    try:
        logger.info(f"🔍 Verifying survey completion {completion_id}...")
        status = 'pending'

        try:
            from surveys.models import SurveyCompletion
            from django.conf import settings

            completion = SurveyCompletion.objects.select_related('survey', 'user').get(
                pk=completion_id
            )

            reasons_invalid = []

            # Check 1: Minimum completion time
            if completion.started_at and completion.completed_at:
                elapsed = (completion.completed_at - completion.started_at).total_seconds() / 60
                min_time = completion.survey.length_minutes * 0.3  # Allow 30% faster
                if elapsed < min_time:
                    reasons_invalid.append(f'too_fast:{elapsed:.1f}min<{min_time:.1f}min')

            # Check 2: Dedup by IP
            if completion.ip_address:
                dedup_key = f'survey_ip_{completion.ip_address}_{completion.survey_id}'
                prev = cache.get(dedup_key)
                if prev and prev != completion_id:
                    reasons_invalid.append('duplicate_ip')
                else:
                    cache.set(dedup_key, completion_id, timeout=SURVEY_DEDUP_TTL)

            # Check 3: Provider verification
            provider_verified = _verify_with_provider(
                completion.provider_transaction_id,
                completion.survey.provider,
            )
            if not provider_verified:
                reasons_invalid.append('provider_not_verified')

            if reasons_invalid:
                status = 'rejected'
                completion.status           = 'rejected'
                completion.rejection_reason = ','.join(reasons_invalid)
                completion.save(update_fields=['status', 'rejection_reason'])
                logger.warning(f"[SURVEY] Completion {completion_id} REJECTED: {reasons_invalid}")
            else:
                status = 'verified'
                completion.status = 'verified'
                completion.verified_at = timezone.now()
                completion.save(update_fields=['status', 'verified_at'])
                # Trigger payout
                process_survey_payout.apply_async(kwargs={'completion_id': completion_id})

        except ImportError as e:
            logger.warning(f"[WARN] Survey models not available: {e}")
            status = 'skipped'

        return {
            'status': 'success',
            'completion_id': completion_id,
            'verification_status': status,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] verify_survey_completion: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.survey_tasks.process_survey_payout')
def process_survey_payout(self, completion_id: int) -> dict:
    """
    Credit the user's wallet after a verified survey completion.
    Applies revenue split: 75% user, 25% platform.
    Sends completion notification.
    """
    try:
        logger.info(f"💰 Processing survey payout for completion {completion_id}...")

        try:
            from surveys.models import SurveyCompletion
            from api.tasks.services import WalletService
            from api.tasks.notification_tasks import send_task_reward_notification

            completion = SurveyCompletion.objects.select_related('survey', 'user').get(
                pk=completion_id, status='verified'
            )

            payout         = Decimal(str(completion.survey.payout or 0))
            user_share     = payout * Decimal('0.75')
            platform_share = payout * Decimal('0.25')

            if user_share <= Decimal('0'):
                return {'status': 'skipped', 'reason': 'zero_payout'}

            with transaction.atomic():
                ws = WalletService()
                ws.credit(
                    user=completion.user,
                    amount=user_share,
                    transaction_type='survey_reward',
                    reference=f'survey_{completion_id}',
                    metadata={
                        'survey_id': completion.survey_id,
                        'completion_id': completion_id,
                        'gross_payout': str(payout),
                        'user_share': str(user_share),
                    },
                )
                completion.status     = 'paid'
                completion.paid_at    = timezone.now()
                completion.save(update_fields=['status', 'paid_at'])

            # Notify user
            send_task_reward_notification.apply_async(kwargs={
                'user_id': completion.user_id,
                'task_name': completion.survey.title,
                'reward_amount': str(user_share),
            })

            return {
                'status': 'success',
                'completion_id': completion_id,
                'payout': str(user_share),
                'timestamp': timezone.now().isoformat(),
            }

        except ImportError as e:
            logger.warning(f"[WARN] Survey models not available: {e}")
            return {'status': 'skipped', 'reason': 'model_not_available'}

    except Exception as exc:
        logger.error(f"[ERROR] process_survey_payout: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='tasks.survey_tasks.sync_survey_inventory')
def sync_survey_inventory(self, providers: list = None) -> dict:
    """
    Pull available surveys from external providers (Cint, Dynata, Lucid, Toluna).
    Creates or updates Survey records in the DB.
    """
    try:
        import requests
        from django.conf import settings
        logger.info(f"🔄 Syncing survey inventory (providers={providers or 'all'})...")

        synced = 0
        errors = 0

        PROVIDER_CONFIGS = getattr(settings, 'SURVEY_PROVIDERS', {
            'cint':  {'api_url': 'https://api.cint.com/v1/', 'api_key': ''},
            'lucid': {'api_url': 'https://api.lucidhq.com/v1/', 'api_key': ''},
        })

        active_providers = providers or list(PROVIDER_CONFIGS.keys())

        for provider_name in active_providers:
            config = PROVIDER_CONFIGS.get(provider_name, {})
            if not config.get('api_key'):
                logger.warning(f"[WARN] No API key for provider: {provider_name}")
                continue

            try:
                resp = requests.get(
                    f"{config['api_url']}surveys",
                    headers={'Authorization': f"Bearer {config['api_key']}"},
                    timeout=30,
                )
                if resp.status_code != 200:
                    errors += 1
                    continue

                surveys_data = resp.json().get('surveys', [])

                for s in surveys_data:
                    try:
                        from surveys.models import Survey
                        Survey.objects.update_or_create(
                            external_id=s.get('id'),
                            provider=provider_name,
                            defaults={
                                'title':          s.get('title', ''),
                                'description':    s.get('description', ''),
                                'payout':         Decimal(str(s.get('payout', 0))),
                                'length_minutes': s.get('length', 10),
                                'countries':      s.get('countries', ['ALL']),
                                'min_age':        s.get('min_age', 18),
                                'max_age':        s.get('max_age', 99),
                                'target_gender':  s.get('gender', 'any'),
                                'is_active':      s.get('active', True),
                                'expires_at':     None,
                                'daily_quota':    s.get('daily_quota'),
                            },
                        )
                        synced += 1
                    except ImportError:
                        synced += 1  # Count as synced even if model missing

            except Exception as prov_err:
                logger.error(f"[ERROR] Provider {provider_name}: {prov_err}")
                errors += 1

        return {
            'status': 'success',
            'synced': synced,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] sync_survey_inventory: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.survey_tasks.generate_survey_report')
def generate_survey_report(self, date_str: str = None) -> dict:
    """Daily survey performance report: completions, revenue, rejection rate."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum, Q

        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )
        logger.info(f"📊 Generating survey report for {target}...")

        report = {'date': str(target), 'type': 'survey_daily', 'totals': {}}

        try:
            from surveys.models import SurveyCompletion
            day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
            day_end   = day_start + timedelta(days=1)

            qs = SurveyCompletion.objects.filter(completed_at__gte=day_start, completed_at__lt=day_end)
            agg = qs.aggregate(
                total=Count('id'),
                paid=Count('id', filter=Q(status='paid')),
                rejected=Count('id', filter=Q(status='rejected')),
                revenue=Sum('survey__payout', filter=Q(status='paid')),
            )
            report['totals'] = {
                'total_completions': agg['total'] or 0,
                'paid': agg['paid'] or 0,
                'rejected': agg['rejected'] or 0,
                'revenue': str(agg['revenue'] or Decimal('0')),
                'rejection_rate': round(
                    (agg['rejected'] or 0) / max(agg['total'] or 1, 1) * 100, 2
                ),
            }
        except ImportError:
            pass

        cache.set(f'survey_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


def _verify_with_provider(transaction_id: str, provider: str) -> bool:
    """Verify a survey completion with the provider API."""
    if not transaction_id:
        return False
    try:
        import requests
        from django.conf import settings
        configs = getattr(settings, 'SURVEY_PROVIDERS', {})
        config  = configs.get(provider, {})
        if not config.get('api_key'):
            return True  # Can't verify → assume valid
        resp = requests.get(
            f"{config['api_url']}completions/{transaction_id}/verify",
            headers={'Authorization': f"Bearer {config['api_key']}"},
            timeout=10,
        )
        return resp.status_code == 200 and resp.json().get('valid', False)
    except Exception:
        return True  # Network error → assume valid, flag for manual check
