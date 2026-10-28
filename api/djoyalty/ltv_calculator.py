# api/djoyalty/ltv_calculator.py
"""
Djoyalty LTV Calculator -- Customer Lifetime Value computation।
Traditional LTV + Loyalty-adjusted LTV + Predicted LTV।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class LTVCalculator:
    """
    Customer Lifetime Value calculator with loyalty adjustments।

    Formulas:
    1. Historical LTV    = total lifetime spend
    2. Avg LTV           = avg order value × purchase frequency × customer lifespan
    3. Loyalty LTV Boost = how much loyalty program increased LTV
    4. Predicted LTV     = RFM-based future value prediction

    Usage:
        calc = LTVCalculator(customer)
        ltv = calc.get_full_ltv()
    """

    def __init__(self, customer):
        self.customer = customer

    def get_historical_ltv(self) -> Decimal:
        """Total spend across all transactions."""
        from .models.core import Txn
        result = Txn.objects.filter(
            customer=self.customer
        ).aggregate(total=Sum('value'))
        return result['total'] or Decimal('0')

    def get_avg_order_value(self) -> Decimal:
        """Average transaction value."""
        from .models.core import Txn
        result = Txn.objects.filter(
            customer=self.customer
        ).aggregate(avg=Avg('value'))
        return result['avg'] or Decimal('0')

    def get_purchase_frequency(self, days: int = 365) -> float:
        """Average purchases per month over last N days."""
        from .models.core import Txn
        cutoff = timezone.now() - timedelta(days=days)
        count = Txn.objects.filter(
            customer=self.customer,
            created_at__gte=cutoff,
        ).count()
        months = days / 30
        return count / max(months, 1)

    def get_customer_lifespan_months(self) -> float:
        """Months since first purchase."""
        from .models.core import Txn
        first_txn = Txn.objects.filter(
            customer=self.customer
        ).order_by('created_at').first()
        if not first_txn:
            return 0
        delta = timezone.now() - first_txn.created_at
        return max(delta.days / 30, 0.1)

    def get_traditional_ltv(self) -> Decimal:
        """Classic LTV = AOV × frequency_per_month × lifespan_months."""
        aov = self.get_avg_order_value()
        freq = Decimal(str(self.get_purchase_frequency()))
        lifespan = Decimal(str(self.get_customer_lifespan_months()))
        return (aov * freq * lifespan).quantize(Decimal('0.01'))

    def get_predicted_ltv(self, months_ahead: int = 12) -> Decimal:
        """Predict future LTV based on recent behavior."""
        from .logic import compute_rfm_score
        from .helpers import days_since

        # Get recent metrics
        last_txn = None
        try:
            from .models.core import Txn
            last_txn = Txn.objects.filter(
                customer=self.customer
            ).order_by('-created_at').first()
        except Exception:
            pass

        recency_days = days_since(last_txn.created_at) if last_txn else 999
        frequency = int(self.get_purchase_frequency() * 12)  # per year
        monetary = self.get_historical_ltv()

        rfm = compute_rfm_score(recency_days, frequency, monetary)
        rfm_total = rfm['total_score']  # 3-15

        # Base prediction: monthly spend × months ahead × retention probability
        monthly_spend = self.get_avg_order_value() * Decimal(str(self.get_purchase_frequency()))

        # Retention factor based on RFM (higher score = higher retention)
        retention_factor = Decimal(str(rfm_total / 15))  # 0.2 to 1.0

        predicted = (monthly_spend * Decimal(str(months_ahead)) * retention_factor).quantize(
            Decimal('0.01')
        )
        return predicted

    def get_loyalty_ltv_boost(self) -> dict:
        """
        Estimate how much the loyalty program increased LTV।
        Industry average: loyalty members spend 12-18% more।
        """
        historical = self.get_historical_ltv()
        # Conservative estimate: 15% boost from loyalty
        boost_pct = Decimal('0.15')
        boost_amount = (historical * boost_pct).quantize(Decimal('0.01'))

        return {
            'historical_ltv': str(historical),
            'loyalty_boost_pct': '15%',
            'loyalty_boost_amount': str(boost_amount),
            'ltv_without_loyalty_estimate': str((historical - boost_amount).quantize(Decimal('0.01'))),
            'note': 'Industry average: loyalty members spend 12-18% more',
        }

    def get_full_ltv(self) -> dict:
        """Get complete LTV analysis for a customer."""
        return {
            'customer_code': self.customer.code,
            'historical_ltv': str(self.get_historical_ltv()),
            'avg_order_value': str(self.get_avg_order_value()),
            'purchase_frequency_per_month': round(self.get_purchase_frequency(), 2),
            'lifespan_months': round(self.get_customer_lifespan_months(), 1),
            'traditional_ltv': str(self.get_traditional_ltv()),
            'predicted_ltv_12m': str(self.get_predicted_ltv(12)),
            'predicted_ltv_24m': str(self.get_predicted_ltv(24)),
            'loyalty_boost': self.get_loyalty_ltv_boost(),
            'calculated_at': timezone.now().isoformat(),
        }


class ProgramLTVAnalysis:
    """Aggregate LTV analysis for the whole program।"""

    @staticmethod
    def get_avg_program_ltv(tenant=None) -> dict:
        """Get average LTV across all active customers."""
        from .models.core import Customer, Txn
        from django.db.models import Sum, Count

        qs = Customer.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)

        # Get customers with transactions
        customer_spend = Txn.objects.filter(
            customer__in=qs
        ).values('customer_id').annotate(
            total_spend=Sum('value'),
            txn_count=Count('id'),
        )

        if not customer_spend.exists():
            return {'avg_ltv': '0', 'median_ltv': '0', 'top_20_pct_ltv': '0'}

        spends = sorted([float(c['total_spend']) for c in customer_spend], reverse=True)
        avg = sum(spends) / len(spends)
        median = spends[len(spends) // 2]
        top_20_idx = max(1, len(spends) // 5)
        top_20_avg = sum(spends[:top_20_idx]) / top_20_idx

        return {
            'total_customers_with_spend': len(spends),
            'avg_ltv': f'{avg:.2f}',
            'median_ltv': f'{median:.2f}',
            'top_20_pct_avg_ltv': f'{top_20_avg:.2f}',
            'top_20_pct_of_revenue': f'{sum(spends[:top_20_idx]) / max(sum(spends), 1) * 100:.1f}%',
        }
