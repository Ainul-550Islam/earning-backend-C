# api/wallet/tasks/__init__.py
"""
All wallet Celery tasks — import from here for clean access.
"""
from .balance_sync_tasks import sync_balance, reconcile_all_balances
from .withdrawal_processing_tasks import (
    process_pending_withdrawals,
    auto_reject_stale_withdrawals,
    sync_gateway_statuses,
)
from .earning_cap_reset_tasks import reset_daily_earning_caps
from .bonus_expiry_tasks import expire_bonus_balances
from .ledger_snapshot_tasks import take_weekly_snapshots
from .liability_report_tasks import compute_daily_liability
from .withdrawal_reminder_tasks import send_withdrawal_reminders
from .fraud_check_tasks import run_fraud_checks, run_aml_scan
from .insight_tasks import (
    compute_daily_insights,
    compute_withdrawal_insights,
    compute_earning_insights,
)
from .reconciliation_tasks import run_daily_reconciliation
from .withdrawal_batch_tasks import process_withdrawal_batches, auto_batch_approvals
from .cleanup_tasks import (
    cleanup_idempotency_keys,
    cleanup_old_webhook_logs,
    cleanup_expired_sessions,
)

# CPAlead payout tasks (imported from tasks_extra via celery task names)
try:
    from ..tasks_extra import (
        deliver_webhook,
        process_mass_payout_job,
        activate_whitelists,
        process_settlements,
        generate_annual_tax_records,
        run_aml_check,
        reset_offer_daily_caps,
        auto_resolve_stale_disputes,
    )
except ImportError:
    pass

# CPAlead payout schedule tasks
try:
    from ..services import PayoutService as _PS

    from celery import shared_task

    @shared_task(bind=True, max_retries=3, name="wallet.run_daily_payouts")
    def run_daily_payouts(self):
        """CPAlead daily payment: earn $1+ today → paid tomorrow. Run: 00:05 AM."""
        try:
            result = _PS.process_daily_payouts()
            return result
        except Exception as e:
            raise self.retry(exc=e)

    @shared_task(bind=True, max_retries=3, name="wallet.release_publisher_holds")
    def release_publisher_holds(self):
        """Release 30-day new publisher fund hold. Run: 1 AM daily."""
        try:
            released = _PS.release_holds()
            return {"released": released}
        except Exception as e:
            raise self.retry(exc=e)

    @shared_task(bind=True, max_retries=3, name="wallet.check_publisher_upgrades")
    def check_publisher_upgrades(self):
        """Auto-upgrade publisher level (NET30→daily). Run: 2 AM daily."""
        try:
            from ..models_cpalead_extra import PublisherLevel
            upgraded = 0
            for pl in PublisherLevel.objects.filter(level__lt=5).select_related("user","wallet"):
                if pl.can_upgrade():
                    if pl.upgrade():
                        upgraded += 1
            return {"upgraded": upgraded}
        except Exception as e:
            raise self.retry(exc=e)

    @shared_task(bind=True, max_retries=3, name="wallet.expire_referrals")
    def expire_referrals(self):
        """Expire CPAlead 6-month referral programs. Run: 3 AM daily."""
        try:
            from django.utils import timezone
            from ..models_cpalead_extra import ReferralProgram
            expired = ReferralProgram.objects.filter(
                is_active=True, expires_at__lt=timezone.now()
            ).update(is_active=False)
            return {"expired": expired}
        except Exception as e:
            raise self.retry(exc=e)

    @shared_task(bind=True, max_retries=3, name="wallet.award_top_earner_bonuses")
    def award_top_earner_bonuses(self):
        """Award CPAlead top earner bonuses (up to 20%). Run: 1st of month."""
        try:
            awarded = _PS.award_top_earner_bonuses()
            return {"awarded": awarded}
        except Exception as e:
            raise self.retry(exc=e)

except Exception:
    pass
