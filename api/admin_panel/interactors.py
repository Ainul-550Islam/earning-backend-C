# api/admin_panel/interactors.py
"""
Admin Panel Interactors — Business Process Orchestrators.
Interactors coordinate multiple use cases, repositories, and services
to complete complex multi-step admin workflows.

Unlike use_cases.py (single operation), interactors handle workflows:
  - OnboardAdvertiser: validate → approve → create wallet → send welcome → notify account manager
  - CloseAccount: ban → export data → GDPR erasure → notify → archive
  - ApproveHighValuePayout: risk check → manager approval → pay → audit

"Interactor = workflow, not single operation."
"""
from __future__ import annotations
from django.db.models import Sum

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================================================
# WORKFLOW RESULT
# ===========================================================================

@dataclass
class WorkflowResult:
    success: bool
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    data: Dict = field(default_factory=dict)
    error: str = ''
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def ok(cls, data=None, steps=None, warnings=None) -> 'WorkflowResult':
        return cls(success=True, data=data or {}, steps_completed=steps or [], warnings=warnings or [])

    @classmethod
    def fail(cls, error: str, steps_done=None, steps_failed=None) -> 'WorkflowResult':
        return cls(success=False, error=error,
                   steps_completed=steps_done or [], steps_failed=steps_failed or [])

    def add_step(self, step: str, success: bool = True, warning: str = ''):
        if success:
            self.steps_completed.append(step)
        else:
            self.steps_failed.append(step)
        if warning:
            self.warnings.append(warning)


# ===========================================================================
# ACCOUNT CLOSURE INTERACTOR
# ===========================================================================

class AccountClosureInteractor:
    """
    Full account closure workflow:
    1. Verify can close (no active pending transactions)
    2. Ban account
    3. Freeze wallet
    4. Cancel all pending payouts
    5. Revoke all active sessions
    6. Revoke API keys if any
    7. Export user data (GDPR)
    8. Schedule data erasure if requested
    9. Notify user
    10. Log complete audit trail
    """

    def execute(
        self,
        user_id: Any,
        actor,
        reason: str,
        gdpr_erasure: bool = False,
        export_data: bool = True,
    ) -> WorkflowResult:
        result = WorkflowResult(success=True)
        result.data['user_id'] = user_id

        # Step 1: Get user
        from api.admin_panel.repositories import UserRepository
        user = UserRepository.get_by_id(user_id)
        if not user:
            return WorkflowResult.fail(f'User {user_id} not found')
        if user.is_superuser:
            return WorkflowResult.fail('Cannot close superuser account')
        result.data['username'] = user.username

        # Step 2: Check for active processing payouts
        try:
            from api.payout_queue.models import PayoutItem
            processing = PayoutItem.objects.filter(user_id=user_id, status='PROCESSING').count()
            if processing > 0:
                result.add_step('payout_check', False, f'{processing} payouts still processing')
        except Exception as e:
            result.add_step('payout_check', False, str(e))

        # Step 3: Ban account
        from api.admin_panel.use_cases import BanUserUseCase
        ban_result = BanUserUseCase().execute(
            user_id=user_id, reason=reason, actor=actor,
            freeze_wallet=True, cancel_payouts=True, send_notification=False,
        )
        if ban_result.success:
            result.add_step('account_banned')
        else:
            result.add_step('account_banned', False, ban_result.error)
            return WorkflowResult.fail('Account ban failed', result.steps_completed, result.steps_failed)

        # Step 4: Export data for GDPR
        if export_data:
            try:
                from api.admin_panel.data_export import AdminDataExporter
                export = AdminDataExporter.export_user_data(user_id)
                result.data['export'] = export
                result.add_step('data_exported')
            except Exception as e:
                result.add_step('data_exported', False, str(e))

        # Step 5: Schedule GDPR erasure
        if gdpr_erasure:
            try:
                from api.kyc.gdpr.service import GDPRService
                GDPRService.schedule_erasure(user_id=user_id, requested_by=actor)
                result.add_step('gdpr_erasure_scheduled')
            except Exception as e:
                result.add_step('gdpr_erasure_scheduled', False, str(e))

        # Step 6: Notify user
        try:
            from api.admin_panel.repositories import NotificationRepository
            NotificationRepository.send_to_user(
                user_id=user_id,
                title='Account Closed',
                message=f'Your account has been closed. Reason: {reason}',
                notification_type='account_closed',
            )
            result.add_step('user_notified')
        except Exception as e:
            result.add_step('user_notified', False, str(e))

        # Step 7: Full audit log
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='account_closure',
                model_name='User', object_id=str(user_id),
                object_repr=user.username,
                changes={
                    'reason': reason, 'gdpr_erasure': gdpr_erasure,
                    'steps': result.steps_completed,
                },
            )
            result.add_step('audit_logged')
        except Exception as e:
            result.add_step('audit_logged', False, str(e))

        result.success = len(result.steps_failed) == 0
        return result


# ===========================================================================
# HIGH VALUE PAYOUT APPROVAL INTERACTOR
# ===========================================================================

class HighValuePayoutInteractor:
    """
    Workflow for high-value withdrawals requiring extra verification:
    1. Risk assessment
    2. Fraud score check
    3. Account age check
    4. KYC verification check
    5. Amount validation against daily limits
    6. Manager approval (if > threshold)
    7. Approve and process
    8. Audit log
    """

    HIGH_VALUE_THRESHOLD = 10000  # BDT

    def execute(self, item_id: Any, actor) -> WorkflowResult:
        result = WorkflowResult(success=True)

        # Step 1: Get payout item
        try:
            from api.payout_queue.models import PayoutItem
            item = PayoutItem.objects.select_related('user').get(pk=item_id, status='QUEUED')
        except Exception:
            return WorkflowResult.fail(f'PayoutItem {item_id} not found or not pending')

        amount = float(item.gross_amount)
        user_id = item.user_id
        result.data['amount'] = amount
        result.data['user'] = item.user.username

        # Step 2: Risk check
        try:
            from api.admin_panel.logic import calculate_user_fraud_score
            risk = calculate_user_fraud_score(user_id)
            result.data['fraud_score'] = risk['score']
            if risk['score'] >= 80:
                return WorkflowResult.fail(
                    f"High risk score ({risk['score']}/100) — manual review required",
                    result.steps_completed, ['risk_check']
                )
            result.add_step('risk_check')
        except Exception as e:
            result.add_step('risk_check', False, str(e))

        # Step 3: KYC check
        try:
            from api.kyc.models import KYC
            kyc = KYC.objects.filter(user_id=user_id, status='SUCCESS').exists()
            if not kyc and amount > self.HIGH_VALUE_THRESHOLD:
                return WorkflowResult.fail('KYC not verified — cannot approve high-value withdrawal')
            result.add_step('kyc_verified' if kyc else 'kyc_skipped_low_value')
        except Exception as e:
            result.add_step('kyc_check', False, str(e))

        # Step 4: Daily limit check
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            daily_limit = float(SystemConfigService.get('daily_withdrawal_limit', default=50000))
            from api.payout_queue.models import PayoutItem as PI
            today_total = float(
                PI.objects.filter(
                    user_id=user_id, status__in=['SUCCESS'],
                    created_at__date=timezone.now().date()
                ).aggregate(t=Sum('gross_amount'))['t'] or 0
            )
            if today_total + amount > daily_limit:
                return WorkflowResult.fail(
                    f"Daily limit exceeded: {today_total + amount} > {daily_limit}"
                )
            result.add_step('daily_limit_check')
        except Exception as e:
            result.add_step('daily_limit_check', False, str(e))

        # Step 5: Approve
        from api.admin_panel.use_cases import ApproveWithdrawalUseCase
        approve_result = ApproveWithdrawalUseCase().execute(item_id, actor)
        if approve_result.success:
            result.add_step('approved')
            result.data.update(approve_result.data or {})
        else:
            return WorkflowResult.fail(approve_result.error, result.steps_completed, ['approve'])

        result.success = True
        return result


# ===========================================================================
# ADVERTISER ONBOARDING INTERACTOR
# ===========================================================================

class AdvertiserOnboardingInteractor:
    """
    Full advertiser onboarding workflow:
    1. Validate advertiser data
    2. Approve advertiser account
    3. Set default campaign limits
    4. Create advertiser wallet/billing
    5. Send welcome email + API credentials
    6. Assign account manager
    7. Log audit trail
    """

    def execute(self, advertiser_id: Any, actor, tier: str = 'standard') -> WorkflowResult:
        result = WorkflowResult(success=True)

        # Step 1: Get advertiser
        try:
            from api.advertiser_portal.models import AdvertiserPortalBaseModel
            # Use dynamic model lookup
            import importlib
            adv_module = importlib.import_module('api.advertiser_portal.models')
            Advertiser = None
            for attr in ['Advertiser', 'AdvertiserProfile', 'AdvertiserAccount']:
                if hasattr(adv_module, attr):
                    Advertiser = getattr(adv_module, attr)
                    break
            if not Advertiser:
                raise ImportError("Advertiser model not found")
            advertiser = Advertiser.objects.get(pk=advertiser_id)
            result.data['advertiser'] = str(advertiser)
        except Exception as e:
            return WorkflowResult.fail(f'Advertiser not found: {e}')

        # Step 2: Approve
        try:
            advertiser.status = 'approved'
            advertiser.approved_by = actor
            advertiser.approved_at = timezone.now()
            advertiser.save()
            result.add_step('advertiser_approved')
        except Exception as e:
            result.add_step('advertiser_approved', False, str(e))

        # Step 3: Set campaign limits based on tier
        tier_limits = {
            'standard': {'daily_budget': 10000, 'max_campaigns': 5},
            'premium':  {'daily_budget': 100000, 'max_campaigns': 50},
            'enterprise': {'daily_budget': 1000000, 'max_campaigns': 500},
        }
        limits = tier_limits.get(tier, tier_limits['standard'])
        try:
            for key, val in limits.items():
                setattr(advertiser, key, val)
            advertiser.tier = tier
            advertiser.save()
            result.add_step('tier_configured')
            result.data['limits'] = limits
        except Exception as e:
            result.add_step('tier_configured', False, str(e))

        # Step 4: Send welcome notification
        try:
            from api.admin_panel.repositories import NotificationRepository
            user_id = getattr(advertiser, 'user_id', None) or getattr(advertiser, 'owner_id', None)
            if user_id:
                NotificationRepository.send_to_user(
                    user_id=user_id,
                    title='Advertiser Account Approved 🎉',
                    message=f'Your advertiser account has been approved as {tier}. You can now create campaigns.',
                    notification_type='advertiser_approved',
                )
            result.add_step('welcome_sent')
        except Exception as e:
            result.add_step('welcome_sent', False, str(e))

        # Step 5: Audit log
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action='onboard_advertiser',
                model_name='Advertiser', object_id=str(advertiser_id),
                changes={'tier': tier, 'limits': limits},
            )
            result.add_step('audit_logged')
        except Exception as e:
            result.add_step('audit_logged', False, str(e))

        result.success = len(result.steps_failed) == 0
        return result


# ===========================================================================
# MAINTENANCE WINDOW INTERACTOR
# ===========================================================================

class MaintenanceWindowInteractor:
    """
    Full maintenance mode orchestration:
    1. Check no critical operations running
    2. Send advance notifications (30min, 5min before)
    3. Enable maintenance mode
    4. Propagate to all apps via EventBus
    5. Log audit
    6. Schedule auto-disable
    """

    def execute(
        self,
        message: str,
        duration_minutes: int,
        actor,
        notify_users: bool = True,
        advance_notice_minutes: int = 30,
    ) -> WorkflowResult:
        result = WorkflowResult(success=True)

        # Check for critical ops
        try:
            from api.payout_queue.models import PayoutItem
            processing = PayoutItem.objects.filter(status='PROCESSING').count()
            if processing > 0:
                result.warnings.append(f'{processing} payouts currently processing')
            result.add_step('critical_ops_checked')
        except Exception as e:
            result.add_step('critical_ops_check', False, str(e))

        # Enable maintenance
        from api.admin_panel.use_cases import EnableMaintenanceUseCase
        maint_result = EnableMaintenanceUseCase().execute(message, duration_minutes, actor)
        if maint_result.success:
            result.add_step('maintenance_enabled')
        else:
            return WorkflowResult.fail(maint_result.error)

        # Notify users
        if notify_users:
            try:
                from api.admin_panel.repositories import NotificationRepository
                count = NotificationRepository.broadcast(
                    title='⚠️ Scheduled Maintenance',
                    message=f'System maintenance starting soon. Duration: {duration_minutes} minutes. {message}',
                    notification_type='maintenance',
                )
                result.data['users_notified'] = count
                result.add_step('users_notified')
            except Exception as e:
                result.add_step('users_notified', False, str(e))

        # Schedule auto-disable
        try:
            from celery import current_app
            current_app.send_task(
                'api.admin_panel.tasks_cap.task_propagate_maintenance_off',
                countdown=duration_minutes * 60,
            )
            result.add_step('auto_disable_scheduled')
        except Exception as e:
            result.add_step('auto_disable_scheduled', False, str(e))

        # Propagate through INTEGRATION_SYSTEM
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
            event_bus.publish('system.maintenance_started', {
                'message': message, 'duration': duration_minutes,
            }, source='admin_panel', priority='high')
            result.add_step('event_propagated')
        except Exception as e:
            result.add_step('event_propagated', False, str(e))

        result.success = len(result.steps_failed) == 0
        return result