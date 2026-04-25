# api/payment_gateways/schedules/ScheduleProcessor.py
# Automated payout schedule processor

from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class ScheduleProcessor:
    """
    Processes all due scheduled payouts.
    Called by Celery Beat daily.
    """

    def process_due_payouts(self) -> dict:
        """Process all payouts due today."""
        from .models import PaymentSchedule, ScheduledPayout

        today    = date.today()
        due      = PaymentSchedule.objects.filter(
            status='active',
            next_payout_date__lte=today,
        ).select_related('user')

        results  = {'processed': 0, 'skipped': 0, 'failed': 0}

        for schedule in due:
            try:
                result = self._process_single(schedule, today)
                if result == 'processed':
                    results['processed'] += 1
                elif result == 'skipped':
                    results['skipped'] += 1
            except Exception as e:
                logger.error(f'ScheduleProcessor: failed for user {schedule.user_id}: {e}')
                results['failed'] += 1

        logger.info(f'ScheduleProcessor: {results}')
        return results

    def _process_single(self, schedule, today: date) -> str:
        from .models import ScheduledPayout

        user           = schedule.user
        balance        = Decimal(str(getattr(user, 'balance', '0') or '0'))
        minimum        = schedule.minimum_payout

        if balance < minimum:
            logger.info(f'Skipping {user.username}: balance {balance} < minimum {minimum}')
            return 'skipped'

        # Determine period
        period_end   = today - timedelta(days=1)
        period_start = self._get_period_start(schedule.schedule_type, today)

        # Calculate fee
        from api.payment_gateways.services.PaymentFactory import PaymentFactory
        try:
            processor = PaymentFactory.get_processor(schedule.payment_method)
            fee       = processor.calculate_fee(balance)
        except Exception:
            fee = Decimal('0')

        net_amount = balance - fee

        # Create payout record
        payout = ScheduledPayout.objects.create(
            schedule        = schedule,
            user            = user,
            amount          = balance,
            fee             = fee,
            net_amount      = net_amount,
            currency        = schedule.payment_currency,
            payment_method  = schedule.payment_method,
            payment_account = schedule.payment_account,
            status          = 'processing',
            period_start    = period_start,
            period_end      = period_end,
            scheduled_date  = today,
        )

        # Initiate actual payout
        try:
            processor = PaymentFactory.get_processor(schedule.payment_method)

            class _MethodProxy:
                account_number = schedule.payment_account
                account_name   = user.get_full_name() or user.username
                gateway        = schedule.payment_method

            result = processor.process_withdrawal(
                user=user,
                amount=balance,
                payment_method=_MethodProxy(),
                metadata={'scheduled_payout_id': payout.id}
            )

            payout.status       = 'completed'
            payout.processed_at = timezone.now()
            payout.gateway_reference = str(result.get('payout', {}).id if hasattr(result.get('payout', {}), 'id') else '')
            payout.save()

            # Update user balance
            user.balance = Decimal('0')
            user.save(update_fields=['balance'])

            # Update schedule
            schedule.last_payout_date   = today
            schedule.last_payout_amount = balance
            schedule.calculate_next_payout()

            logger.info(f'Scheduled payout processed: user={user.id} amount={balance}')
            return 'processed'

        except Exception as e:
            payout.status        = 'failed'
            payout.error_message = str(e)
            payout.save()
            logger.error(f'Scheduled payout failed: user={user.id} error={e}')
            return 'failed'

    def _get_period_start(self, schedule_type: str, today: date) -> date:
        if schedule_type == 'daily':
            return today
        elif schedule_type == 'weekly':
            return today - timedelta(days=7)
        elif schedule_type == 'net15':
            return today - timedelta(days=15)
        elif schedule_type == 'net30':
            return today - timedelta(days=30)
        return today - timedelta(days=30)
