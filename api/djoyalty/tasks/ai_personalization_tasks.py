# api/djoyalty/tasks/ai_personalization_tasks.py
"""
AI Personalization Celery Tasks।
Daily RFM scoring, churn scan, personalized offer generation।
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.compute_rfm_scores', bind=True, max_retries=3)
def compute_rfm_scores_task(self, tenant_id=None):
    """
    Daily RFM score computation for all customers।
    Runs at 2am daily।
    """
    try:
        from ..models.core import Customer
        from ..services.AIPersonalizationService import AIPersonalizationService

        qs = Customer.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        updated = 0
        for customer in qs.iterator(chunk_size=100):
            try:
                AIPersonalizationService.update_ai_profile(customer)
                updated += 1
            except Exception as e:
                logger.debug('RFM update failed for %s: %s', customer.code, e)

        logger.info('compute_rfm_scores_task: updated %d profiles', updated)
        return {'updated': updated}
    except Exception as exc:
        logger.error('compute_rfm_scores_task error: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='djoyalty.run_churn_scan', bind=True)
def run_churn_scan_task(self, tenant_id=None):
    """
    Daily churn scan -- identify at-risk customers and send win-back offers।
    Runs at 3am daily।
    """
    try:
        from ..services.AIPersonalizationService import AIPersonalizationService
        from ..models.core import Tenant

        tenant = None
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                pass

        result = AIPersonalizationService.run_churn_scan(tenant=tenant)
        logger.info('run_churn_scan_task: %s', result)
        return result
    except Exception as exc:
        logger.error('run_churn_scan_task error: %s', exc)
        raise self.retry(exc=exc, countdown=600)


@shared_task(name='djoyalty.generate_birthday_offers')
def generate_birthday_offers_task():
    """
    Daily birthday offer generation for customers with upcoming birthdays।
    Runs at 8am daily।
    """
    try:
        from datetime import date, timedelta
        from ..models.core import Customer
        from ..services.AIPersonalizationService import AIPersonalizationService

        today = date.today()
        # Customers with birthdays in next 3 days
        upcoming = Customer.objects.filter(
            is_active=True,
            date_of_birth__isnull=False,
            date_of_birth__month=today.month,
            date_of_birth__day__gte=today.day,
            date_of_birth__day__lte=(today + timedelta(days=3)).day,
        )

        generated = 0
        for customer in upcoming:
            offer = AIPersonalizationService.generate_birthday_offer(customer)
            if offer:
                generated += 1
                # Send push notification
                try:
                    from ..integration_system.bridge import loyalty_bridge
                    loyalty_bridge.send_personalized_offer(customer, offer)
                except Exception:
                    pass

        logger.info('generate_birthday_offers_task: generated %d offers', generated)
        return {'generated': generated}
    except Exception as exc:
        logger.error('generate_birthday_offers_task error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.cleanup_expired_ai_offers')
def cleanup_expired_ai_offers_task():
    """Mark expired personalized offers as expired।"""
    try:
        from django.utils import timezone
        from ..models.ai_personalization import PersonalizedOffer

        count = PersonalizedOffer.objects.filter(
            status='active',
            valid_until__lt=timezone.now(),
        ).update(status='expired')

        logger.info('cleanup_expired_ai_offers_task: expired %d offers', count)
        return {'expired': count}
    except Exception as exc:
        logger.error('cleanup_expired_ai_offers_task error: %s', exc)
        return {'error': str(exc)}
