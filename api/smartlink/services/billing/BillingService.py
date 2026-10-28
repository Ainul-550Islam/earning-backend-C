"""
SmartLink Billing Service
===========================
Central billing coordinator. All wallet, payout, and batch operations
pass through here. SubPublisher commission chain is wired here.

Responsibilities:
  - credit_conversion()           → wallet credit on each conversion
  - release_pending()             → move pending → available after hold period
  - calculate_payout()            → period payout calculation per publisher
  - create_batch()                → batch-level payout calculation
  - approve_batch()               → admin approval
  - mark_batch_paid()             → manual paid mark
  - process_payment()             → payment gateway dispatch (PayPal / Wise)
  - process_batch_payments()      → batch gateway dispatch
  - send_payout_notifications()   → notify publishers of approved payouts
  - evaluate_publisher_tiers()    → recalculate Gold/Silver/Bronze/Standard tiers
  - _calculate_sub_commission()   → SubPublisher period commission summary
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger('smartlink.billing')


class BillingService:
    """
    Central billing coordinator.
    All public methods are callable from viewsets, signals, and Celery tasks.
    """

    HOLD_DAYS = 7  # Conversions go into pending for 7 days before becoming available

    # ── Wallet Credit ─────────────────────────────────────────────────────────

    def credit_conversion(self, publisher, amount_usd: float,
                          smartlink_id: int = None,
                          offer_id=None, click_id: int = None):
        """
        Credit a publisher's wallet for a conversion.
        Called from conversion_signals.py after attribution.
        New credits go into pending_usd first (held for HOLD_DAYS).
        """
        from api.smartlink.models.billing import PublisherWallet
        wallet, _ = PublisherWallet.objects.get_or_create(publisher=publisher)
        wallet.credit(amount_usd, hold_days=self.HOLD_DAYS)
        logger.info(
            f"Wallet credited: publisher={publisher.username} "
            f"amount=${amount_usd:.4f} sl={smartlink_id} offer={offer_id} "
            f"click={click_id}"
        )

    # ── Hold Release ──────────────────────────────────────────────────────────

    def release_pending(self, publisher=None) -> int:
        """
        Move pending balance → available after HOLD_DAYS expires.
        Called by the daily Celery beat task.

        Args:
            publisher: if given, release only for this publisher.
                       if None, release for all publishers.

        Returns:
            Number of wallets updated.
        """
        from api.smartlink.models.billing import PublisherWallet
        from django.db.models import F

        qs = PublisherWallet.objects.filter(pending_usd__gt=0)
        if publisher is not None:
            qs = qs.filter(publisher=publisher)

        released = 0
        for wallet in qs:
            updated = PublisherWallet.objects.filter(
                pk=wallet.pk, pending_usd__gt=0
            ).update(
                balance_usd=F('balance_usd') + F('pending_usd'),
                pending_usd=0,
            )
            if updated:
                released += 1

        logger.info(f"Pending balances released: {released} wallets")
        return released

    def release_pending_balances(self) -> dict:
        """
        Batch release of ALL publishers' pending balances.
        Alias called by Celery beat task `smartlink.release_pending_balances`.
        """
        released = self.release_pending(publisher=None)
        return {'released': released}

    # ── Payout Calculation ────────────────────────────────────────────────────

    def calculate_payout(self, publisher, date_from: date, date_to: date,
                         admin_user=None):
        """
        Calculate the payout owed to a publisher for a date range.
        Applies quality scrubbing rules from PublisherPayoutService.
        Returns a PayoutRecord (status=calculated) or None if below threshold.

        Also accounts for SubPublisher commission earned during the period —
        commission amounts credited to this publisher's wallet from referred
        publishers' conversions are included in their wallet balance and
        will be included in the net payout.
        """
        from api.smartlink.models.billing import PublisherWallet, PayoutRecord, PublisherProfile
        from api.smartlink.services.billing.PublisherPayoutService import PublisherPayoutService

        payout_svc = PublisherPayoutService()
        result = payout_svc.calculate_period_payout(publisher.id, date_from, date_to)

        net = Decimal(str(result.get('net_payout_usd', 0)))
        if net <= 0:
            return None

        # Check minimum threshold
        try:
            profile = publisher.publisher_profile
            if net < profile.min_payout:
                logger.info(
                    f"Payout below threshold for {publisher.username}: "
                    f"${net} < ${profile.min_payout}"
                )
                return None
            payment_method  = profile.payment_method
            payment_address = (
                profile.payment_email
                or getattr(profile, 'bank_account_number', None)
                or getattr(profile, 'crypto_address', None)
                or publisher.email
            )
            currency = profile.payout_currency or 'USD'
        except Exception:
            payment_method  = 'paypal'
            payment_address = publisher.email
            currency        = 'USD'

        with transaction.atomic():
            record = PayoutRecord.objects.create(
                publisher=publisher,
                period_from=date_from,
                period_to=date_to,
                gross_amount=Decimal(str(result.get('gross_payout_usd', net))),
                scrub_amount=Decimal(str(result.get('scrub_deduction_usd', 0))),
                net_amount=net,
                currency=currency,
                fx_rate=Decimal('1.000000'),
                local_amount=net,
                total_clicks=result.get('total_clicks', 0),
                total_conversions=result.get('total_conversions', 0),
                fraud_rate=Decimal(str(result.get('fraud_rate', 0))),
                scrub_rate=Decimal(str(result.get('scrub_rate', 0))),
                scrub_reason=result.get('scrub_reason', ''),
                payment_method=payment_method,
                payment_address=payment_address,
                calculated_by=admin_user,
            )

        logger.info(
            f"Payout calculated: {publisher.username} "
            f"${net} [{date_from}–{date_to}]"
        )
        return record

    def _calculate_sub_commission_earned(self, publisher, date_from: date,
                                         date_to: date) -> Decimal:
        """
        Sum all SubPublisher commissions earned by this publisher during the period.
        These credits are already in the wallet (credited on each conversion),
        so this method is used for reporting breakdowns only.

        Returns:
            Decimal: total commission earned from sub-publishers in the period.
        """
        from api.smartlink.models.publisher import SubPublisher
        from api.smartlink.models import Click

        sub_relationships = SubPublisher.objects.filter(
            parent_publisher=publisher,
            is_active=True,
        ).values_list('child_publisher_id', flat=True)

        if not sub_relationships:
            return Decimal('0')

        total_child_net = Click.objects.filter(
            smartlink__publisher_id__in=sub_relationships,
            is_converted=True,
            payout__gt=0,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).aggregate(total=Sum('payout'))['total'] or Decimal('0')

        # Sum commissions per relationship
        total_commission = Decimal('0')
        for rel in SubPublisher.objects.filter(
            parent_publisher=publisher, is_active=True
        ):
            child_net = Click.objects.filter(
                smartlink__publisher=rel.child_publisher,
                is_converted=True,
                payout__gt=0,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            ).aggregate(total=Sum('payout'))['total'] or 0.0
            total_commission += Decimal(
                str(rel.calculate_commission(float(child_net)))
            )

        return total_commission

    # ── Batch Management ─────────────────────────────────────────────────────

    def create_batch(self, label: str, date_from: date, date_to: date,
                     admin_user):
        """
        Create a new payout batch and calculate payouts for all eligible publishers.
        """
        from api.smartlink.models.billing import PayoutBatch, PublisherWallet

        with transaction.atomic():
            batch = PayoutBatch.objects.create(
                label=label,
                period_from=date_from,
                period_to=date_to,
                status='calculating',
                created_by=admin_user,
            )
            wallets = PublisherWallet.objects.filter(
                balance_usd__gt=0
            ).select_related('publisher__publisher_profile')

            records = []
            total   = Decimal('0')
            for wallet in wallets:
                record = self.calculate_payout(
                    wallet.publisher, date_from, date_to, admin_user
                )
                if record:
                    record.batch = batch
                    record.save()
                    records.append(record)
                    total += record.net_amount

            PayoutBatch.objects.filter(pk=batch.pk).update(
                total_records=len(records),
                total_amount=total,
                status='review',
            )
            batch.refresh_from_db()

        logger.info(
            f"Batch created: '{label}' — "
            f"{len(records)} publishers, ${total}"
        )
        return batch

    def approve_batch(self, batch, admin_user) -> int:
        """Mark all CALCULATED records in a batch as APPROVED."""
        from api.smartlink.models.billing import PayoutRecord, PayoutBatch
        updated = PayoutRecord.objects.filter(
            batch=batch,
            status=PayoutRecord.Status.CALCULATED,
        ).update(
            status=PayoutRecord.Status.APPROVED,
            approved_by=admin_user,
        )
        PayoutBatch.objects.filter(pk=batch.pk).update(status='processing')
        logger.info(
            f"Batch #{batch.pk} approved: {updated} records "
            f"by {admin_user.username}"
        )
        return updated

    def mark_batch_paid(self, batch) -> int:
        """Mark all APPROVED records as PAID (used for manual gateway workflows)."""
        from api.smartlink.models.billing import PayoutRecord, PayoutBatch
        from django.utils import timezone

        records = PayoutRecord.objects.filter(
            batch=batch,
            status=PayoutRecord.Status.APPROVED,
        ).select_related('publisher')

        paid = 0
        for record in records:
            record.mark_paid()
            paid += 1

        PayoutBatch.objects.filter(pk=batch.pk).update(
            status='completed',
            completed_at=timezone.now(),
        )
        logger.info(f"Batch #{batch.pk} marked paid: {paid} records")
        return paid

    # ── Payment Gateway Dispatch ──────────────────────────────────────────────

    def process_payment(self, payout_record) -> dict:
        """
        Send a payout via the publisher's configured payment gateway.

        Gateway routing (based on publisher's payment_method):
          paypal            → PayPal Payouts API
          wise              → Wise Transfers API
          wire/crypto/
          payoneer/unknown  → requires_manual=True (no API call)

        PayoutRecord status transitions:
          APPROVED → PROCESSING → PAID     (gateway success)
          APPROVED → PROCESSING → FAILED   (gateway error)
          APPROVED → APPROVED   (manual methods — reverted so admin sees it)

        Returns:
            Unified dict from PaymentGatewayRouter.process()
        """
        from api.smartlink.models.billing import PayoutRecord

        if payout_record.status != PayoutRecord.Status.APPROVED:
            return {
                'success':         False,
                'gateway':         '',
                'transaction_id':  '',
                'status':          payout_record.status,
                'error': (
                    f"PayoutRecord #{payout_record.reference_id} is not APPROVED "
                    f"(current status: {payout_record.status}). "
                    "Approve it before processing."
                ),
                'requires_manual': False,
            }

        # Mark PROCESSING immediately — prevents duplicate gateway calls
        PayoutRecord.objects.filter(pk=payout_record.pk).update(
            status=PayoutRecord.Status.PROCESSING,
        )

        from api.smartlink.services.billing.PaymentGatewayRouter import PaymentGatewayRouter
        router = PaymentGatewayRouter()
        result = router.process(payout_record)

        if result.get('requires_manual'):
            # Revert to APPROVED for admin to process externally
            PayoutRecord.objects.filter(pk=payout_record.pk).update(
                status=PayoutRecord.Status.APPROVED,
                failure_reason=result['error'],
            )
            logger.info(
                f"Manual payout required: ref={payout_record.reference_id} "
                f"method={payout_record.payment_method}"
            )
        elif result['success']:
            payout_record.mark_paid(transaction_ref=result['transaction_id'])
            logger.info(
                f"Payout processed: ref={payout_record.reference_id} "
                f"gateway={result['gateway']} txn={result['transaction_id']}"
            )
        else:
            payout_record.mark_failed(reason=result['error'])
            logger.error(
                f"Payout failed: ref={payout_record.reference_id} "
                f"gateway={result['gateway']} error={result['error']}"
            )

        return result

    def process_batch_payments(self, batch) -> dict:
        """
        Process payments for all APPROVED records in a batch.
        Each record is dispatched to its publisher's configured gateway.

        Returns:
            {
                'processed': int,  # total gateway calls attempted
                'paid':      int,  # successful gateway payouts
                'failed':    int,  # gateway errors
                'manual':    int,  # records needing manual processing
                'skipped':   int,  # records not in APPROVED status (safety)
                'results':   list, # per-record result summary
            }
        """
        from api.smartlink.models.billing import PayoutRecord, PayoutBatch
        from django.utils import timezone

        records = PayoutRecord.objects.filter(
            batch=batch,
            status=PayoutRecord.Status.APPROVED,
        ).select_related('publisher', 'publisher__publisher_profile')

        summary = {
            'processed': 0,
            'paid':      0,
            'failed':    0,
            'manual':    0,
            'skipped':   0,
            'results':   [],
        }

        for record in records:
            result = self.process_payment(record)
            summary['processed'] += 1
            summary['results'].append({
                'reference_id':   str(record.reference_id),
                'publisher':      record.publisher.username,
                'amount':         str(record.net_amount),
                'gateway':        result.get('gateway', ''),
                'success':        result.get('success', False),
                'transaction_id': result.get('transaction_id', ''),
                'requires_manual':result.get('requires_manual', False),
                'error':          result.get('error', ''),
            })
            if result.get('requires_manual'):
                summary['manual'] += 1
            elif result['success']:
                summary['paid'] += 1
            else:
                summary['failed'] += 1

        # Update batch status
        total_done = summary['paid'] + summary['manual']
        if total_done == summary['processed'] and summary['manual'] == 0:
            PayoutBatch.objects.filter(pk=batch.pk).update(
                status='completed', completed_at=timezone.now()
            )
        elif summary['paid'] > 0 or summary['manual'] > 0:
            PayoutBatch.objects.filter(pk=batch.pk).update(status='processing')

        logger.info(
            f"Batch payment run: batch={batch.pk} "
            f"processed={summary['processed']} paid={summary['paid']} "
            f"failed={summary['failed']} manual={summary['manual']}"
        )
        return summary

    # ── Notifications ─────────────────────────────────────────────────────────

    def send_payout_notifications(self, batch_id: int = None) -> int:
        """
        Notify publishers whose payout records are APPROVED and ready.
        Called by Celery task `smartlink.send_payout_ready_notifications`.

        Args:
            batch_id: if given, notify only publishers in this batch.
                      if None, notify all publishers with approved records.

        Returns:
            Number of notifications sent.
        """
        from api.smartlink.models.billing import PayoutRecord
        from api.smartlink.services.notification.NotificationService import NotificationService

        qs = PayoutRecord.objects.filter(
            status=PayoutRecord.Status.APPROVED,
            notified_at__isnull=True,
        ).select_related('publisher')

        if batch_id is not None:
            qs = qs.filter(batch_id=batch_id)

        notification_svc = NotificationService()
        sent = 0
        for record in qs:
            try:
                notification_svc.notify_payout_approved(
                    publisher=record.publisher,
                    payout_record=record,
                )
                # Mark notified so we don't send twice
                PayoutRecord.objects.filter(pk=record.pk).update(
                    notified_at=__import__('django.utils.timezone', fromlist=['timezone']).timezone.now()
                    if False else __import__('django.utils', fromlist=['timezone']).timezone.now()
                )
                sent += 1
            except Exception as exc:
                logger.warning(
                    f"Payout notification failed for {record.publisher.username}: {exc}"
                )

        logger.info(f"Payout notifications sent: {sent}")
        return sent

    # ── Publisher Tier Evaluation ─────────────────────────────────────────────

    def evaluate_publisher_tiers(self) -> dict:
        """
        Recalculate tier (Gold/Silver/Bronze/Standard) for all publishers
        based on their 30-day performance metrics.
        Called by Celery beat task `smartlink.evaluate_publisher_tiers`.

        Tier logic is delegated to PublisherTierService — this method
        coordinates the batch run and returns a summary.

        Returns:
            {'evaluated': int, 'changed': int, 'errors': int}
        """
        from api.smartlink.services.publisher.PublisherTierService import PublisherTierService
        tier_svc = PublisherTierService()

        publishers = User.objects.filter(
            is_active=True, is_staff=False
        ).only('pk', 'username')

        evaluated = 0
        changed   = 0
        errors    = 0

        for publisher in publishers:
            try:
                result = tier_svc.evaluate_and_update(publisher)
                evaluated += 1
                if result.get('changed'):
                    changed += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    f"Tier evaluation failed for {publisher.username}: {exc}"
                )

        logger.info(
            f"Publisher tier evaluation complete: "
            f"evaluated={evaluated} changed={changed} errors={errors}"
        )
        return {'evaluated': evaluated, 'changed': changed, 'errors': errors}
