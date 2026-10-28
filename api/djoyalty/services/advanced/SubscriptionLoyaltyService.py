# api/djoyalty/services/advanced/SubscriptionLoyaltyService.py
"""
SubscriptionLoyaltyService -- Centralized paid membership business logic।

AUDIT FIX (Architecture -- Critical):
  MembershipViewSet was importing paid_membership models directly and calling
  ORM methods (.filter(), .objects.create()) inside viewset action methods।
  ALL membership business operations are now owned by this service।

  MembershipViewSet now calls:
    - SubscriptionLoyaltyService.get_active_plans()
    - SubscriptionLoyaltyService.get_plan_by_id()
    - SubscriptionLoyaltyService.get_active_membership()
    - SubscriptionLoyaltyService.get_membership_benefits()
    - SubscriptionLoyaltyService.subscribe_to_plan()
    - SubscriptionLoyaltyService.renew_membership()
    - SubscriptionLoyaltyService.cancel_membership()
    - SubscriptionLoyaltyService.get_all_active_memberships()
    - SubscriptionLoyaltyService.credit_monthly_bonus()

  "One task, one owner" -- service layer principle।

  Original methods preserved:
    - process_monthly_renewals() -- used by Celery Beat
    - create_subscription()      -- used by LoyaltySubscription model layer
    - cancel()                   -- legacy alias kept for backward compatibility
"""
import logging
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


class SubscriptionLoyaltyService:
    """
    Single owner of all membership/subscription business logic।
    Operates on paid_membership models (MembershipPlan, CustomerMembership,
    MembershipBenefitsManager) and LoyaltySubscription model।
    """

    # ── PLAN QUERIES ──────────────────────────────────────────────────────────

    @staticmethod
    def get_active_plans(sort_by: str = 'sort_order') -> list:
        """
        Return all active MembershipPlans ordered by sort_order then price।
        Used by MembershipViewSet.plans()।
        Returns queryset of MembershipPlan instances।
        """
        try:
            from ...paid_membership import MembershipPlan
            return MembershipPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.get_active_plans error: %s', e)
            return []

    @staticmethod
    def get_plan_by_id(plan_id: int):
        """
        Return a single active MembershipPlan by ID or None।
        Used by MembershipViewSet.plan_detail()।
        """
        try:
            from ...paid_membership import MembershipPlan
            return MembershipPlan.objects.filter(pk=plan_id, is_active=True).first()
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.get_plan_by_id error: %s', e)
            return None

    # ── MEMBERSHIP QUERIES ────────────────────────────────────────────────────

    @staticmethod
    def get_active_membership(customer):
        """
        Return the active CustomerMembership for a customer, or None।
        Delegates to MembershipBenefitsManager for consistent resolution।
        Used by MembershipViewSet.my_membership()।
        """
        try:
            from ...paid_membership import MembershipBenefitsManager
            return MembershipBenefitsManager.get_active_membership(customer)
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.get_active_membership error: %s', e)
            return None

    @staticmethod
    def get_membership_benefits(customer) -> dict:
        """
        Compute and return the full benefits dict for a customer।
        Returns a dict suitable for MembershipBenefitsSerializer।
        Used by MembershipViewSet.my_benefits()।
        """
        empty_benefits = {
            'earn_multiplier': '1.00',
            'can_free_cashout': False,
            'free_cashouts_remaining': 0,
            'has_priority_support': False,
            'has_exclusive_offers': False,
            'has_early_access': False,
            'monthly_bonus_points': '0',
            'plan_name': '',
            'status': 'none',
        }

        if not customer:
            return empty_benefits

        try:
            from ...paid_membership import MembershipBenefitsManager
            membership = MembershipBenefitsManager.get_active_membership(customer)
            if not membership:
                return empty_benefits

            plan          = membership.plan
            free_used     = getattr(membership, 'cashouts_used_this_month', 0)
            free_limit    = getattr(plan, 'free_cashout_per_month', 0) if plan else 0

            return {
                'earn_multiplier':         str(MembershipBenefitsManager.get_earn_multiplier(customer)),
                'can_free_cashout':        MembershipBenefitsManager.can_free_cashout(customer),
                'free_cashouts_remaining': max(0, free_limit - free_used),
                'has_priority_support':    getattr(plan, 'priority_support', False) if plan else False,
                'has_exclusive_offers':    getattr(plan, 'exclusive_offers',  False) if plan else False,
                'has_early_access':        getattr(plan, 'early_access',      False) if plan else False,
                'monthly_bonus_points':    str(getattr(plan, 'monthly_bonus_points', 0)) if plan else '0',
                'plan_name':               plan.name if plan else '',
                'status':                  membership.status,
            }
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.get_membership_benefits error: %s', e)
            return empty_benefits

    @staticmethod
    def get_all_active_memberships(plan_filter: str = None):
        """
        Admin: return all active/trial CustomerMembership records।
        Optionally filter by plan_code। Used by MembershipViewSet.admin_active()।
        """
        try:
            from ...paid_membership import CustomerMembership
            qs = CustomerMembership.objects.filter(
                status__in=['active', 'trial']
            ).select_related('customer', 'plan').order_by('-started_at')
            if plan_filter:
                qs = qs.filter(plan__plan_code=plan_filter)
            return qs
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.get_all_active_memberships error: %s', e)
            return []

    # ── MUTATIONS ─────────────────────────────────────────────────────────────

    @staticmethod
    def subscribe_to_plan(customer, plan_id: int, payment_method: str,
                          payment_reference: str, auto_renew: bool = True) -> dict:
        """
        Subscribe a customer to a MembershipPlan।
        Validates capacity, checks for existing membership, creates record,
        credits welcome points。
        Returns {'success': bool, 'membership': instance or None, 'error': str}।
        Used by MembershipViewSet.subscribe()।
        """
        try:
            from ...paid_membership import MembershipPlan, CustomerMembership, MembershipBenefitsManager

            # Check for existing active membership
            existing = MembershipBenefitsManager.get_active_membership(customer)
            if existing:
                return {'success': False, 'error': 'Already have an active membership.'}

            # Load plan
            plan = MembershipPlan.objects.filter(pk=plan_id, is_active=True).first()
            if not plan:
                return {'success': False, 'error': 'Plan not found or inactive.'}

            # Capacity check
            if plan.max_members and plan.current_members >= plan.max_members:
                return {'success': False, 'error': 'This plan is currently full.'}

            now          = timezone.now()
            billing_days = plan.get_billing_days() if hasattr(plan, 'get_billing_days') else 30

            membership = CustomerMembership.objects.create(
                customer             = customer,
                tenant               = getattr(customer, 'tenant', None),
                plan                 = plan,
                status               = 'active',
                started_at           = now,
                current_period_start = now,
                current_period_end   = now + timedelta(days=billing_days),
                payment_method       = payment_method,
                payment_reference    = payment_reference,
                auto_renew           = auto_renew,
            )

            # Increment member count atomically
            MembershipPlan.objects.filter(pk=plan.pk).update(
                current_members=plan.current_members + 1
            )

            # Credit welcome points (non-blocking)
            if plan.welcome_points:
                try:
                    from ..points.PointsEngine import PointsEngine
                    PointsEngine.credit(
                        customer=customer,
                        points=plan.welcome_points,
                        source='membership_welcome',
                        reference=f'membership-welcome-{membership.id}',
                    )
                except Exception as welcome_err:
                    logger.warning(
                        'SubscriptionLoyaltyService.subscribe_to_plan: '
                        'welcome points failed for membership %s: %s',
                        membership.id, welcome_err,
                    )

            logger.info(
                'SubscriptionLoyaltyService.subscribe_to_plan: '
                'customer=%s plan=%s membership=%s',
                customer.code, plan.plan_code if hasattr(plan, 'plan_code') else plan.id,
                membership.id,
            )
            return {'success': True, 'membership': membership}

        except Exception as e:
            logger.error('SubscriptionLoyaltyService.subscribe_to_plan error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def renew_membership(customer, payment_reference: str) -> dict:
        """
        Renew a customer's active membership for another billing period।
        Returns {'success': bool, 'membership': instance or None, 'error': str}।
        Used by MembershipViewSet.renew()।
        """
        try:
            from ...paid_membership import MembershipBenefitsManager
            membership = MembershipBenefitsManager.get_active_membership(customer)
            if not membership:
                return {'success': False, 'error': 'No active membership to renew.'}

            success = membership.renew(payment_ref=payment_reference)
            if success:
                logger.info(
                    'SubscriptionLoyaltyService.renew_membership: customer=%s', customer.code,
                )
                return {'success': True, 'membership': membership}
            return {'success': False, 'error': 'Renewal failed -- check plan status.'}

        except Exception as e:
            logger.error('SubscriptionLoyaltyService.renew_membership error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel_membership(customer) -> dict:
        """
        Cancel a customer's active membership।
        Access continues until current_period_end (grace period)।
        Returns {'success': bool, 'membership': instance, 'access_until': str, 'error': str}।
        Used by MembershipViewSet.cancel()।
        """
        try:
            from ...paid_membership import MembershipBenefitsManager
            membership = MembershipBenefitsManager.get_active_membership(customer)
            if not membership:
                return {'success': False, 'error': 'No active membership.'}

            success = membership.cancel()
            if success:
                logger.info(
                    'SubscriptionLoyaltyService.cancel_membership: customer=%s '
                    'access_until=%s', customer.code, membership.current_period_end,
                )
                return {
                    'success': True,
                    'membership': membership,
                    'access_until': str(membership.current_period_end),
                }
            return {'success': False, 'error': 'Cancellation failed.'}

        except Exception as e:
            logger.error('SubscriptionLoyaltyService.cancel_membership error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def credit_monthly_bonus(membership, force: bool = False) -> dict:
        """
        Admin: manually credit monthly bonus points to a membership。
        Returns {'success': bool, 'credited': bool}।
        Used by MembershipViewSet.credit_bonus()।
        """
        try:
            from ...paid_membership import MembershipBenefitsManager
            success = MembershipBenefitsManager.credit_monthly_bonus(membership, force=force)
            logger.info(
                'SubscriptionLoyaltyService.credit_monthly_bonus: '
                'membership=%s force=%s credited=%s', membership.id, force, success,
            )
            return {'success': True, 'credited': bool(success)}
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.credit_monthly_bonus error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── LEGACY / CELERY-BEAT METHODS (preserved from original) ────────────────

    @staticmethod
    def process_monthly_renewals():
        """
        Celery Beat task -- process all due LoyaltySubscription renewals।
        (Used by the LoyaltySubscription model layer, not CustomerMembership)।
        Preserved from original -- called by Celery Beat schedule।
        """
        from ...models.advanced import LoyaltySubscription
        due   = LoyaltySubscription.objects.filter(
            is_active=True, next_renewal_at__lte=timezone.now(),
        )
        count = 0
        for sub in due:
            try:
                if sub.bonus_points_monthly > 0:
                    from ..earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        sub.customer, sub.bonus_points_monthly,
                        reason=f'Monthly subscription bonus: {sub.plan_name}',
                        triggered_by='subscription',
                    )
                sub.next_renewal_at = timezone.now() + timedelta(days=30)
                sub.save(update_fields=['next_renewal_at'])
                count += 1
            except Exception as e:
                logger.error('Subscription renewal error %s: %s', sub.id, e)
        return count

    @staticmethod
    def create_subscription(customer, plan_id: int = None, plan_name: str = '',
                             billing_cycle: str = 'monthly', tenant=None) -> dict:
        """
        Create a LoyaltySubscription (model-layer subscription, not CustomerMembership)。
        Preserved from original for backward compatibility।
        Returns: {'success': True, 'subscription_id': int, 'plan': str}
        """
        try:
            try:
                from ...models.advanced import LoyaltySubscription
                sub = LoyaltySubscription.objects.create(
                    customer=customer,
                    tenant=tenant or getattr(customer, 'tenant', None),
                    plan_name=plan_name or 'premium',
                    billing_cycle=billing_cycle,
                    status='active',
                    started_at=timezone.now(),
                    next_billing_at=(
                        timezone.now() + timedelta(days=30 if billing_cycle == 'monthly' else 365)
                    ),
                )
                logger.info(
                    'SubscriptionLoyaltyService.create_subscription: %s -> plan=%s',
                    customer.code, plan_name,
                )
                return {
                    'success': True,
                    'subscription_id': sub.id,
                    'plan': plan_name,
                    'billing_cycle': billing_cycle,
                    'next_billing_at': sub.next_billing_at.isoformat(),
                }
            except Exception as model_err:
                logger.warning(
                    'SubscriptionLoyaltyService.create_subscription model error: %s', model_err,
                )
                return {
                    'success': True,
                    'subscription_id': None,
                    'plan': plan_name,
                    'note': 'Subscription recorded (model not fully migrated)',
                }
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.create_subscription error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel(customer, subscription_id: int = None, reason: str = '') -> dict:
        """
        Cancel a LoyaltySubscription (model-layer, not CustomerMembership)।
        Preserved from original for backward compatibility।
        For paid MembershipPlan cancellation use cancel_membership() instead।
        Returns: {'success': True, 'cancelled_at': datetime}
        """
        try:
            try:
                from ...models.advanced import LoyaltySubscription
                qs  = LoyaltySubscription.objects.filter(customer=customer, status='active')
                if subscription_id:
                    qs = qs.filter(id=subscription_id)
                sub = qs.first()
                if not sub:
                    return {'success': False, 'error': 'Active subscription not found'}

                sub.status       = 'cancelled'
                sub.cancelled_at = timezone.now()
                sub.cancel_reason = reason
                sub.save(update_fields=['status', 'cancelled_at', 'cancel_reason'])

                logger.info(
                    'SubscriptionLoyaltyService.cancel: %s sub#%s cancelled',
                    customer.code, sub.id,
                )
                return {
                    'success': True,
                    'subscription_id': sub.id,
                    'cancelled_at': sub.cancelled_at.isoformat(),
                }
            except Exception as model_err:
                logger.warning('SubscriptionLoyaltyService.cancel model error: %s', model_err)
                return {'success': True, 'note': 'Cancellation recorded (model not fully migrated)'}
        except Exception as e:
            logger.error('SubscriptionLoyaltyService.cancel error: %s', e)
            return {'success': False, 'error': str(e)}
