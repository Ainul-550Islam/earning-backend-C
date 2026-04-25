# api/payment_gateways/services/ReconciliationService.py
# Match our DB records against gateway statements

from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Matches our GatewayTransaction records against gateway statements.
    Identifies mismatches, missing records, and amount differences.
    """

    AMOUNT_TOLERANCE = Decimal('0.01')  # 1 paisa tolerance

    def reconcile(self, gateway_name: str, date) -> dict:
        """Run reconciliation for a gateway on a given date."""
        from api.payment_gateways.models.core import PaymentGateway, GatewayTransaction
        from api.payment_gateways.models.reconciliation import (
            ReconciliationBatch, ReconciliationMismatch, GatewayStatement
        )
        from django.db.models import Sum

        gw    = PaymentGateway.objects.get(name=gateway_name)
        batch = ReconciliationBatch.objects.create(
            date=date, gateway=gw, status='running',
            started_at=timezone.now()
        )

        try:
            # Get our records
            our_txns = GatewayTransaction.objects.filter(
                gateway=gateway_name,
                created_at__date=date,
            ).values('reference_id', 'gateway_reference', 'amount', 'status')

            our_map     = {t['gateway_reference']: t for t in our_txns if t['gateway_reference']}
            our_total   = our_txns.aggregate(t=Sum('amount'))['t'] or Decimal('0')

            # Get gateway statement
            statement = GatewayStatement.objects.filter(
                gateway=gw, period_start__lte=date, period_end__gte=date
            ).first()

            if not statement:
                batch.status     = 'failed'
                batch.error_log  = 'No gateway statement imported for this date'
                batch.completed_at = timezone.now()
                batch.save()
                return {'error': 'No statement available'}

            gateway_txns = statement.raw_data
            gw_map       = {t.get('txn_id', t.get('id', '')): t for t in gateway_txns}
            gw_total     = sum(Decimal(str(t.get('amount', 0))) for t in gateway_txns)

            matched = mismatched = 0
            mismatches = []

            # Compare
            for ref, our in our_map.items():
                gw_txn = gw_map.get(ref)
                if not gw_txn:
                    mismatched += 1
                    mismatches.append({
                        'type': 'missing_gateway', 'our_ref': our['reference_id'],
                        'our_amount': our['amount'], 'gw_amount': None,
                        'diff': our['amount']
                    })
                else:
                    gw_amount = Decimal(str(gw_txn.get('amount', 0)))
                    diff      = abs(our['amount'] - gw_amount)
                    if diff > self.AMOUNT_TOLERANCE:
                        mismatched += 1
                        mismatches.append({
                            'type': 'amount_diff', 'our_ref': our['reference_id'],
                            'our_amount': our['amount'], 'gw_amount': gw_amount,
                            'diff': diff
                        })
                    else:
                        matched += 1

            # Check for records in gateway but not ours
            for gw_ref, gw_txn in gw_map.items():
                if gw_ref not in our_map:
                    mismatched += 1
                    mismatches.append({
                        'type': 'missing_ours', 'our_ref': None,
                        'gw_ref': gw_ref, 'gw_amount': gw_txn.get('amount'),
                    })

            # Save mismatches
            for mm in mismatches:
                ReconciliationMismatch.objects.create(
                    batch=batch,
                    mismatch_type=mm['type'],
                    our_reference_id=mm.get('our_ref', ''),
                    our_amount=mm.get('our_amount'),
                    gateway_txn_id=mm.get('gw_ref', ''),
                    gateway_amount=mm.get('gw_amount'),
                    amount_difference=mm.get('diff'),
                )

            batch.status              = 'completed'
            batch.completed_at        = timezone.now()
            batch.total_our_records   = len(our_map)
            batch.total_gateway_records = len(gw_map)
            batch.total_matched       = matched
            batch.total_mismatched    = mismatched
            batch.our_total_amount    = our_total
            batch.gateway_total_amount = gw_total
            batch.discrepancy_amount  = abs(our_total - gw_total)
            batch.save()

            logger.info(f'Reconciliation done: {gateway_name} {date} | matched={matched} mismatched={mismatched}')
            return {
                'matched':     matched,
                'mismatched':  mismatched,
                'discrepancy': float(batch.discrepancy_amount),
            }

        except Exception as e:
            batch.status    = 'failed'
            batch.error_log = str(e)
            batch.completed_at = timezone.now()
            batch.save()
            logger.error(f'Reconciliation failed: {e}')
            raise
