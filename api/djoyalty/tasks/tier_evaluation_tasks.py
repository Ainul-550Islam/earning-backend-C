# api/djoyalty/tasks/tier_evaluation_tasks.py
"""Monthly: সব customer এর tier re-evaluate করো।"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func: return func
        return lambda f: f

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.evaluate_all_tiers', bind=True, max_retries=3, default_retry_delay=120)
def evaluate_all_tiers_task(self):
    """Monthly: সব active customers এর tier evaluate করো।"""
    try:
        from ..models.core import Customer
        from ..services.tiers.TierEvaluationService import TierEvaluationService

        customers = Customer.objects.filter(is_active=True).only('id', 'tenant')
        count = 0
        errors = 0
        for customer in customers:
            try:
                TierEvaluationService.evaluate(customer, tenant=customer.tenant)
                count += 1
            except Exception as e:
                errors += 1
                logger.warning('[djoyalty] Tier eval error for %s: %s', customer.id, e)

        logger.info('[djoyalty] Tier evaluation done: %d ok, %d errors', count, errors)
        return {'evaluated': count, 'errors': errors}
    except Exception as exc:
        logger.error('[djoyalty] evaluate_all_tiers error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.evaluate_single_customer_tier', bind=True, max_retries=3, default_retry_delay=30)
def evaluate_single_customer_tier_task(self, customer_id: int):
    """Single customer tier evaluation — signal থেকে trigger হয়।"""
    try:
        from ..models.core import Customer
        from ..services.tiers.TierEvaluationService import TierEvaluationService
        customer = Customer.objects.get(id=customer_id)
        result = TierEvaluationService.evaluate(customer, tenant=customer.tenant)
        tier_name = result.tier.name if result and result.tier else 'no_change'
        logger.info('[djoyalty] Tier eval for customer %d: %s', customer_id, tier_name)
        return tier_name
    except Exception as exc:
        logger.error('[djoyalty] evaluate_single_customer_tier error: %s', exc)
        raise self.retry(exc=exc) if hasattr(self, 'retry') else exc
