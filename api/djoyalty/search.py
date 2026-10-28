# api/djoyalty/search.py
"""
Djoyalty Search -- Full-text and filtered search across loyalty data।
Customer search, transaction search, offer search।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.utils import timezone

logger = logging.getLogger(__name__)


class CustomerSearch:
    """
    Search customers by code, phone, email, name, loyalty number।
    Supports fuzzy search and filter combinations।

    Usage:
        results = CustomerSearch.search('01700', limit=20)
        results = CustomerSearch.search_by_tier('gold', tenant=tenant)
    """

    @staticmethod
    def search(query: str, tenant=None, limit: int = 20,
               active_only: bool = True) -> list:
        """
        Full-text customer search।
        Searches: code, email, phone, firstname, lastname, loyalty_number।
        """
        from .models.core import Customer

        if not query or len(query) < 2:
            return []

        query = query.strip()
        qs = Customer.objects.all()

        if active_only:
            qs = qs.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)

        # Build search query
        search_q = (
            Q(code__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(firstname__icontains=query) |
            Q(lastname__icontains=query)
        )

        # Try loyalty_number field if exists
        try:
            search_q |= Q(loyalty_number__icontains=query)
        except Exception:
            pass

        # Try referral_code
        try:
            search_q |= Q(referral_code__iexact=query)
        except Exception:
            pass

        return list(
            qs.filter(search_q)
            .select_related()
            .order_by('-created_at')[:limit]
        )

    @staticmethod
    def search_by_tier(tier_name: str, tenant=None) -> list:
        """Get all customers currently in a specific tier."""
        from .models.core import Customer
        qs = Customer.objects.filter(
            is_active=True,
            user_tiers__tier__name__iexact=tier_name,
            user_tiers__is_current=True,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.select_related('user_tiers__tier'))

    @staticmethod
    def search_by_points_range(min_pts: Decimal, max_pts: Decimal,
                                tenant=None) -> list:
        """Get customers with balance in a range."""
        from .models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects.filter(
            balance__gte=min_pts,
            balance__lte=max_pts,
        ).select_related('customer')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return [lp.customer for lp in qs]

    @staticmethod
    def search_inactive(days: int = 30, tenant=None) -> list:
        """Find customers who haven't purchased in N days (churn risk)."""
        from .models.core import Customer
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        qs = Customer.objects.filter(
            is_active=True,
        ).filter(
            Q(last_activity_at__isnull=True) | Q(last_activity_at__lt=cutoff)
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs[:500])


class TransactionSearch:
    """
    Search transactions by customer, amount, date range, source।
    """

    @staticmethod
    def search(customer=None, source: str = '', date_from=None,
               date_to=None, min_value: Decimal = None,
               max_value: Decimal = None, limit: int = 50) -> list:
        """Full transaction search with multiple filters."""
        from .models.core import Txn

        qs = Txn.objects.all()
        if customer:
            qs = qs.filter(customer=customer)
        if source:
            qs = qs.filter(source__icontains=source)
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        if min_value is not None:
            qs = qs.filter(value__gte=min_value)
        if max_value is not None:
            qs = qs.filter(value__lte=max_value)

        return list(qs.select_related('customer').order_by('-created_at')[:limit])


class PointsLedgerSearch:
    """
    Search points ledger entries by customer, type, source, date।
    """

    @staticmethod
    def search(customer=None, txn_type: str = '', source: str = '',
               date_from=None, date_to=None,
               reference_id: str = '', limit: int = 50) -> list:
        """Search ledger with filters."""
        from .models.points import PointsLedger

        qs = PointsLedger.objects.all()
        if customer:
            qs = qs.filter(customer=customer)
        if txn_type:
            qs = qs.filter(txn_type=txn_type)
        if source:
            qs = qs.filter(source=source)
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        if reference_id:
            qs = qs.filter(reference_id__icontains=reference_id)

        return list(qs.select_related('customer').order_by('-created_at')[:limit])


class OfferSearch:
    """
    Search offers in the offerwall by type, geo, difficulty।
    """

    @staticmethod
    def search(query: str = '', offer_type: str = '',
               country: str = '', device: str = '',
               min_points: Decimal = None, max_points: Decimal = None,
               limit: int = 50) -> list:
        """Search offers with multiple filters."""
        from .models.offerwall import Offer

        qs = Offer.objects.filter(status='active')
        if query:
            qs = qs.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(advertiser_name__icontains=query)
            )
        if offer_type:
            qs = qs.filter(offer_type=offer_type)
        if country:
            qs = qs.filter(
                Q(geo_targets=[]) | Q(geo_targets__contains=country.upper())
            )
        if device:
            qs = qs.filter(
                Q(device_targets=[]) | Q(device_targets__contains=device.lower())
            )
        if min_points is not None:
            qs = qs.filter(points_reward__gte=min_points)
        if max_points is not None:
            qs = qs.filter(points_reward__lte=max_points)

        return list(qs.order_by('-is_featured', 'sort_order')[:limit])


class CatalogSearch:
    """
    Search reward catalog items।
    """

    @staticmethod
    def search(query: str = '', reward_type: str = '',
               max_points: Decimal = None,
               category_id: int = None, limit: int = 50) -> list:
        """Search catalog items."""
        from .models.catalog import RewardCatalogItem

        now = timezone.now()
        qs = RewardCatalogItem.objects.filter(
            is_active=True,
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=now)
        )

        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(supplier_name__icontains=query)
            )
        if reward_type:
            qs = qs.filter(reward_type=reward_type)
        if max_points is not None:
            qs = qs.filter(points_cost__lte=max_points)
        if category_id:
            qs = qs.filter(category_id=category_id)

        return list(qs.order_by('-is_featured', 'sort_order', 'points_cost')[:limit])


class GlobalLoyaltySearch:
    """
    Global search across all loyalty entities।
    Returns: {customers: [...], offers: [...], catalog: [...]}
    """

    @staticmethod
    def search(query: str, tenant=None, limit_each: int = 5) -> dict:
        """Global search across customers, offers, catalog."""
        results = {
            'customers': [],
            'offers': [],
            'catalog': [],
            'query': query,
        }

        if not query or len(query) < 2:
            return results

        results['customers'] = [
            {'id': c.id, 'code': c.code, 'name': f'{c.firstname or ""} {c.lastname or ""}'.strip(),
             'email': c.email or '', 'phone': c.phone or ''}
            for c in CustomerSearch.search(query, tenant=tenant, limit=limit_each)
        ]

        results['offers'] = [
            {'id': o.id, 'title': o.title, 'offer_type': o.offer_type,
             'points_reward': str(o.points_reward)}
            for o in OfferSearch.search(query=query, limit=limit_each)
        ]

        results['catalog'] = [
            {'id': i.id, 'name': i.name, 'reward_type': i.reward_type,
             'points_cost': str(i.points_cost)}
            for i in CatalogSearch.search(query=query, limit=limit_each)
        ]

        results['total'] = (
            len(results['customers']) +
            len(results['offers']) +
            len(results['catalog'])
        )

        return results
