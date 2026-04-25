"""
Custom Model Managers for Advertiser Portal

This module contains custom Django model managers for advanced
query operations, data access patterns, and business logic.
"""

from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models, transaction, connection
from django.db.models import Q, F, Count, Sum, Avg, Max, Min, Prefetch, Case, When, Value, IntegerField
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from .models.advertiser import Advertiser
from .models.campaign import AdCampaign
from .models.offer import AdvertiserOffer
from .models.tracking import Conversion, TrackingPixel
from .models.billing import AdvertiserTransaction, AdvertiserWallet
from .models.reporting import AdvertiserReport
from .models.fraud_protection import ConversionQualityScore
from .utils import AdvertiserUtils, CampaignUtils, OfferUtils

logger = logging.getLogger(__name__)


class AdvertiserManager(models.Manager):
    """Custom manager for Advertiser model with high-concurrency operations."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('user', 'profile', 'wallet')
    
    def active(self):
        """Get active advertisers."""
        return self.get_queryset().filter(is_active=True)
    
    def verified(self):
        """Get verified advertisers."""
        return self.get_queryset().filter(verification_status='verified')
    
    def by_industry(self, industry: str):
        """Get advertisers by industry."""
        return self.get_queryset().filter(industry=industry)
    
    def by_country(self, country: str):
        """Get advertisers by country."""
        return self.get_queryset().filter(country=country)
    
    def with_balance_above(self, amount: Decimal):
        """Get advertisers with balance above specified amount."""
        return self.get_queryset().filter(wallet__balance__gte=amount)
    
    def with_legacy_id(self, legacy_id: str):
        """Get advertisers by legacy ID for Data Bridge integration."""
        return self.get_queryset().filter(metadata__legacy_id=legacy_id)
    
    def search_advanced(self, query: str, filters: Dict[str, Any] = None):
        """Advanced search with multiple criteria."""
        queryset = self.get_queryset()
        
        if query:
            queryset = queryset.filter(
                Q(company_name__icontains=query) |
                Q(user__email__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(industry__icontains=query)
            )
        
        if filters:
            if 'verification_status' in filters:
                queryset = queryset.filter(verification_status=filters['verification_status'])
            if 'country' in filters:
                queryset = queryset.filter(country=filters['country'])
            if 'industry' in filters:
                queryset = queryset.filter(industry=filters['industry'])
            if 'min_balance' in filters:
                queryset = queryset.filter(wallet__balance__gte=filters['min_balance'])
            if 'max_balance' in filters:
                queryset = queryset.filter(wallet__balance__lte=filters['max_balance'])
        
        return queryset
    
    def get_performance_metrics_batch(self, advertiser_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for multiple advertisers in a single query."""
        queryset = self.get_queryset().filter(id__in=advertiser_ids)
        
        # Annotate with performance metrics
        queryset = queryset.annotate(
            campaign_count=Count('adcampaign', distinct=True),
            active_campaign_count=Count('adcampaign', filter=Q(adcampaign__status='active'), distinct=True),
            total_conversions=Count('adcampaign__conversion', distinct=True),
            total_revenue=Sum('adcampaign__conversion__revenue'),
            avg_conversion_value=Avg('adcampaign__conversion__revenue')
        )
        
        results = {}
        for advertiser in queryset:
            results[str(advertiser.id)] = {
                'advertiser_id': str(advertiser.id),
                'company_name': advertiser.company_name,
                'verification_status': advertiser.verification_status,
                'campaign_count': advertiser.campaign_count or 0,
                'active_campaign_count': advertiser.active_campaign_count or 0,
                'total_conversions': advertiser.total_conversions or 0,
                'total_revenue': float(advertiser.total_revenue or 0),
                'avg_conversion_value': float(advertiser.avg_conversion_value or 0),
                'wallet_balance': float(advertiser.wallet.balance) if advertiser.wallet else 0
            }
        
        return results
    
    def bulk_update_with_atomic(self, updates: List[Dict[str, Any]]) -> int:
        """Bulk update advertisers with atomic transaction for high concurrency."""
        try:
            with transaction.atomic():
                # Use select_for_update to prevent race conditions
                advertiser_ids = [update['id'] for update in updates]
                advertisers = list(
                    self.get_queryset().filter(id__in=advertiser_ids).select_for_update()
                )
                
                advertiser_map = {str(adv.id): adv for adv in advertisers}
                
                updated_count = 0
                for update in updates:
                    advertiser = advertiser_map.get(update['id'])
                    if advertiser:
                        for field, value in update.items():
                            if field != 'id' and hasattr(advertiser, field):
                                setattr(advertiser, field, value)
                        advertiser.save()
                        updated_count += 1
                
                return updated_count
                
        except Exception as e:
            logger.error(f"Error in bulk_update_with_atomic: {e}")
            raise
    
    def get_or_create_with_lock(self, **kwargs):
        """Get or create advertiser with row-level lock for concurrency."""
        try:
            with transaction.atomic():
                return self.get_queryset().select_for_update().get_or_create(**kwargs)
        except self.model.DoesNotExist:
            # Retry once in case of race condition
            with transaction.atomic():
                return self.get_queryset().select_for_update().get_or_create(**kwargs)
    
    def with_active_campaigns(self):
        """Get advertisers with active campaigns."""
        return self.get_queryset().filter(
            adcampaign__status='active'
        ).distinct()
    
    def created_in_period(self, start_date: datetime, end_date: datetime):
        """Get advertisers created in specified period."""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def search(self, query: str):
        """Search advertisers by name, company, or email."""
        return self.get_queryset().filter(
            Q(company_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )
    
    def get_performance_metrics(self, advertiser_id: str) -> Dict[str, Any]:
        """Get comprehensive performance metrics for an advertiser."""
        cache_key = f"advertiser_metrics_{advertiser_id}"
        cached_metrics = cache.get(cache_key)
        
        if cached_metrics:
            return cached_metrics
        
        try:
            advertiser = self.get_queryset().get(id=advertiser_id)
            
            # Get campaign metrics
            campaigns = AdCampaign.objects.filter(advertiser=advertiser)
            campaign_metrics = CampaignUtils.calculate_campaign_metrics(campaigns.first()) if campaigns.exists() else {}
            
            # Get billing metrics
            billing_metrics = BillingUtils.calculate_billing_metrics(advertiser)
            
            # Get conversion metrics
            conversions = Conversion.objects.filter(advertiser=advertiser)
            total_conversions = conversions.count()
            total_revenue = conversions.aggregate(total=Sum('revenue'))['total'] or 0
            
            metrics = {
                'advertiser_id': str(advertiser.id),
                'company_name': advertiser.company_name,
                'verification_status': advertiser.verification_status,
                'is_active': advertiser.is_active,
                'created_at': advertiser.created_at,
                'campaigns': {
                    'total': campaigns.count(),
                    'active': campaigns.filter(status='active').count(),
                    'paused': campaigns.filter(status='paused').count(),
                    'completed': campaigns.filter(status='completed').count(),
                },
                'billing': billing_metrics,
                'conversions': {
                    'total': total_conversions,
                    'total_revenue': float(total_revenue),
                    'avg_revenue': float(total_revenue / total_conversions) if total_conversions > 0 else 0,
                },
                'performance': campaign_metrics
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, metrics, 300)
            return metrics
            
        except Advertiser.DoesNotExist:
            return {}
        except Exception as e:
            logger.error(f"Error getting advertiser metrics: {e}")
            return {}
    
    def bulk_update_status(self, advertiser_ids: List[str], status: str) -> int:
        """Bulk update advertiser status."""
        return self.get_queryset().filter(id__in=advertiser_ids).update(
            verification_status=status,
            updated_at=timezone.now()
        )


class CampaignManager(models.Manager):
    """Custom manager for AdCampaign model."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related(
            'advertiser', 'advertiser__user', 'advertiser__wallet'
        ).prefetch_related(
            'campaigncreative_set',
            'campaigntargeting_set',
            'campaignbid_set'
        )
    
    def active(self):
        """Get active campaigns."""
        return self.get_queryset().filter(status='active')
    
    def by_status(self, status: str):
        """Get campaigns by status."""
        return self.get_queryset().filter(status=status)
    
    def by_advertiser(self, advertiser_id: str):
        """Get campaigns by advertiser."""
        return self.get_queryset().filter(advertiser_id=advertiser_id)
    
    def by_objective(self, objective: str):
        """Get campaigns by objective."""
        return self.get_queryset().filter(objective=objective)
    
    def running_in_period(self, start_date: datetime, end_date: datetime):
        """Get campaigns running in specified period."""
        return self.get_queryset().filter(
            start_date__lte=end_date,
            end_date__gte=start_date
        )
    
    def with_low_budget(self, threshold: Decimal = Decimal('100')):
        """Get campaigns with low budget."""
        return self.get_queryset().filter(
            daily_budget__lte=threshold
        )
    
    def expiring_soon(self, days: int = 7):
        """Get campaigns expiring soon."""
        expiry_date = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            end_date__lte=expiry_date,
            status='active'
        )
    
    def search(self, query: str):
        """Search campaigns by name or description."""
        return self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(advertiser__company_name__icontains=query)
        )
    
    def get_performance_summary(self, campaign_ids: List[str] = None) -> Dict[str, Any]:
        """Get performance summary for campaigns."""
        queryset = self.get_queryset()
        if campaign_ids:
            queryset = queryset.filter(id__in=campaign_ids)
        
        # Basic counts
        total_campaigns = queryset.count()
        active_campaigns = queryset.filter(status='active').count()
        
        # Budget metrics
        total_budget = queryset.aggregate(total=Sum('total_budget'))['total'] or 0
        total_daily_budget = queryset.aggregate(total=Sum('daily_budget'))['total'] or 0
        
        # Performance metrics (simplified)
        performance_data = []
        for campaign in queryset:
            metrics = CampaignUtils.calculate_campaign_metrics(campaign)
            performance_data.append(metrics)
        
        return {
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_budget': float(total_budget),
            'total_daily_budget': float(total_daily_budget),
            'performance_data': performance_data
        }


class OfferManager(models.Manager):
    """Custom manager for AdvertiserOffer model."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related(
            'advertiser', 'advertiser__user'
        ).prefetch_related(
            'offerrequirement_set',
            'offercreative_set'
        )
    
    def active(self):
        """Get active offers."""
        return self.get_queryset().filter(status='active')
    
    def by_advertiser(self, advertiser_id: str):
        """Get offers by advertiser."""
        return self.get_queryset().filter(advertiser_id=advertiser_id)
    
    def by_type(self, offer_type: str):
        """Get offers by type."""
        return self.get_queryset().filter(offer_type=offer_type)
    
    def by_category(self, category: str):
        """Get offers by category."""
        return self.get_queryset().filter(category=category)
    
    def expiring_soon(self, days: int = 7):
        """Get offers expiring soon."""
        expiry_date = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            end_date__lte=expiry_date,
            status='active'
        )
    
    def with_payout_range(self, min_amount: Decimal, max_amount: Decimal):
        """Get offers within payout range."""
        return self.get_queryset().filter(
            payout_amount__gte=min_amount,
            payout_amount__lte=max_amount
        )
    
    def by_country_targeting(self, country: str):
        """Get offers targeting specific country."""
        return self.get_queryset().filter(
            country_targeting__icontains=country
        )
    
    def search(self, query: str):
        """Search offers by name or description."""
        return self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(advertiser__company_name__icontains=query)
        )
    
    def get_popular_offers(self, limit: int = 10) -> List['AdvertiserOffer']:
        """Get popular offers based on conversion count."""
        return self.get_queryset().annotate(
            conversion_count=Count('conversion')
        ).order_by('-conversion_count')[:limit]
    
    def get_compliance_summary(self, offer_ids: List[str] = None) -> Dict[str, Any]:
        """Get compliance summary for offers."""
        queryset = self.get_queryset()
        if offer_ids:
            queryset = queryset.filter(id__in=offer_ids)
        
        total_offers = queryset.count()
        active_offers = queryset.filter(status='active').count()
        
        compliance_issues = []
        for offer in queryset:
            compliance_data = OfferUtils.validate_offer_compliance(offer)
            if not compliance_data['is_compliant']:
                compliance_issues.append({
                    'offer_id': str(offer.id),
                    'offer_name': offer.name,
                    'issues': compliance_data['issues'],
                    'warnings': compliance_data['warnings']
                })
        
        return {
            'total_offers': total_offers,
            'active_offers': active_offers,
            'compliance_rate': (total_offers - len(compliance_issues)) / total_offers * 100 if total_offers > 0 else 0,
            'compliance_issues': compliance_issues
        }


class ConversionManager(models.Manager):
    """Custom manager for Conversion model."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related(
            'advertiser', 'offer', 'advertiser__user'
        ).prefetch_related(
            'conversionevent_set',
            'conversionqualityscore_set'
        )
    
    def by_advertiser(self, advertiser_id: str):
        """Get conversions by advertiser."""
        return self.get_queryset().filter(advertiser_id=advertiser_id)
    
    def by_offer(self, offer_id: str):
        """Get conversions by offer."""
        return self.get_queryset().filter(offer_id=offer_id)
    
    def by_status(self, status: str):
        """Get conversions by status."""
        return self.get_queryset().filter(status=status)
    
    def in_period(self, start_date: datetime, end_date: datetime):
        """Get conversions in specified period."""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def by_country(self, country: str):
        """Get conversions by country."""
        return self.get_queryset().filter(country=country)
    
    def by_device_type(self, device_type: str):
        """Get conversions by device type."""
        return self.get_queryset().filter(device_type=device_type)
    
    def with_revenue_range(self, min_amount: Decimal, max_amount: Decimal):
        """Get conversions within revenue range."""
        return self.get_queryset().filter(
            revenue__gte=min_amount,
            revenue__lte=max_amount
        )
    
    def suspicious(self, threshold: float = 0.7):
        """Get suspicious conversions based on quality score."""
        return self.get_queryset().filter(
            conversionqualityscore__overall_score__lte=threshold
        ).distinct()
    
    def get_revenue_summary(self, advertiser_id: str = None, period_days: int = 30) -> Dict[str, Any]:
        """Get revenue summary for conversions."""
        queryset = self.get_queryset()
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        start_date = timezone.now() - timedelta(days=period_days)
        queryset = queryset.filter(created_at__gte=start_date)
        
        # Basic metrics
        total_conversions = queryset.count()
        total_revenue = queryset.aggregate(total=Sum('revenue'))['total'] or 0
        total_payout = queryset.aggregate(total=Sum('payout'))['total'] or 0
        
        # Daily breakdown
        daily_data = queryset.extra(
            {'date': 'date(created_at)'}
        ).values('date').annotate(
            conversions=Count('id'),
            revenue=Sum('revenue'),
            payout=Sum('payout')
        ).order_by('date')
        
        return {
            'period_days': period_days,
            'total_conversions': total_conversions,
            'total_revenue': float(total_revenue),
            'total_payout': float(total_payout),
            'net_revenue': float(total_revenue - total_payout),
            'avg_revenue_per_conversion': float(total_revenue / total_conversions) if total_conversions > 0 else 0,
            'daily_breakdown': list(daily_data)
        }


class TransactionManager(models.Manager):
    """Custom manager for AdvertiserTransaction with high-concurrency operations."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related(
            'wallet', 'wallet__advertiser', 'wallet__advertiser__user'
        )
    
    def by_advertiser(self, advertiser_id: str):
        """Get transactions by advertiser."""
        return self.get_queryset().filter(wallet__advertiser_id=advertiser_id)
    
    def by_type(self, transaction_type: str):
        """Get transactions by type."""
        return self.get_queryset().filter(transaction_type=transaction_type)
    
    def by_status(self, status: str):
        """Get transactions by status."""
        return self.get_queryset().filter(status=status)
    
    def in_period(self, start_date: datetime, end_date: datetime):
        """Get transactions in specified period."""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def by_amount_range(self, min_amount: Decimal, max_amount: Decimal):
        """Get transactions within amount range."""
        return self.get_queryset().filter(
            amount__gte=min_amount,
            amount__lte=max_amount
        )
    
    def pending(self):
        """Get pending transactions."""
        return self.get_queryset().filter(status='pending')
    
    def failed(self):
        """Get failed transactions."""
        return self.get_queryset().filter(status='failed')
    
    def create_with_balance_update(self, wallet, amount: Decimal, transaction_type: str, 
                              description: str = None, metadata: Dict[str, Any] = None):
        """Create transaction with atomic balance update for Data Bridge sync."""
        try:
            with transaction.atomic():
                # Lock wallet row
                wallet = AdvertiserWallet.objects.select_for_update().get(id=wallet.id)
                
                # Create transaction
                transaction_obj = self.model(
                    wallet=wallet,
                    amount=amount,
                    transaction_type=transaction_type,
                    description=description,
                    metadata=metadata or {},
                    status='completed'
                )
                transaction_obj.save()
                
                # Update wallet balance
                if transaction_type in ['deposit', 'refund']:
                    wallet.balance += amount
                elif transaction_type in ['withdrawal', 'spend']:
                    wallet.balance -= amount
                
                wallet.save()
                
                return transaction_obj
                
        except Exception as e:
            logger.error(f"Error in create_with_balance_update: {e}")
            raise
    
    def bulk_create_with_balance_updates(self, transactions_data: List[Dict[str, Any]]) -> List:
        """Bulk create transactions with atomic balance updates."""
        created_transactions = []
        
        try:
            with transaction.atomic():
                # Group by wallet for efficient updates
                wallet_updates = {}
                
                for tx_data in transactions_data:
                    wallet_id = tx_data['wallet_id']
                    amount = tx_data['amount']
                    tx_type = tx_data['transaction_type']
                    
                    if wallet_id not in wallet_updates:
                        wallet_updates[wallet_id] = Decimal('0')
                    
                    # Calculate net balance change
                    if tx_type in ['deposit', 'refund']:
                        wallet_updates[wallet_id] += amount
                    elif tx_type in ['withdrawal', 'spend']:
                        wallet_updates[wallet_id] -= amount
                
                # Lock and update wallets
                wallet_ids = list(wallet_updates.keys())
                wallets = list(
                    AdvertiserWallet.objects.filter(id__in=wallet_ids).select_for_update()
                )
                wallet_map = {w.id: w for w in wallets}
                
                for wallet_id, balance_change in wallet_updates.items():
                    wallet = wallet_map.get(wallet_id)
                    if wallet:
                        wallet.balance += balance_change
                        wallet.save()
                
                # Create transactions
                created_transactions = self.bulk_create([
                    self.model(
                        wallet_id=tx_data['wallet_id'],
                        amount=tx_data['amount'],
                        transaction_type=tx_data['transaction_type'],
                        description=tx_data.get('description'),
                        metadata=tx_data.get('metadata', {}),
                        status='completed'
                    )
                    for tx_data in transactions_data
                ])
                
                return created_transactions
                
        except Exception as e:
            logger.error(f"Error in bulk_create_with_balance_updates: {e}")
            raise
    
    def get_financial_summary(self, advertiser_id: str = None, period_days: int = 30) -> Dict[str, Any]:
        """Get financial summary for transactions."""
        queryset = self.get_queryset()
        if advertiser_id:
            queryset = queryset.filter(wallet__advertiser_id=advertiser_id)
        
        start_date = timezone.now() - timedelta(days=period_days)
        queryset = queryset.filter(created_at__gte=start_date)
        
        # Transaction counts by type
        transaction_counts = queryset.values('transaction_type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('transaction_type')
        
        # Status breakdown
        status_counts = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Total amounts
        total_deposits = queryset.filter(
            transaction_type='deposit'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_withdrawals = queryset.filter(
            transaction_type='withdrawal'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_spend = queryset.filter(
            transaction_type='spend'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'period_days': period_days,
            'transaction_counts': list(transaction_counts),
            'status_counts': list(status_counts),
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'total_spend': float(total_spend),
            'net_flow': float(total_deposits - total_withdrawals - total_spend)
        }


class WalletManager(models.Manager):
    """Custom manager for AdvertiserWallet with high-concurrency operations."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related('advertiser', 'advertiser__user')
    
    def with_balance_above(self, amount: Decimal):
        """Get wallets with balance above specified amount."""
        return self.get_queryset().filter(balance__gte=amount)
    
    def with_balance_below(self, amount: Decimal):
        """Get wallets with balance below specified amount."""
        return self.get_queryset().filter(balance__lte=amount)
    
    def by_advertiser(self, advertiser_id: str):
        """Get wallet by advertiser."""
        return self.get_queryset().filter(advertiser_id=advertiser_id)
    
    def update_balance_atomic(self, wallet_id: str, new_balance: Decimal, 
                          transaction_type: str = 'adjustment', 
                          description: str = None) -> AdvertiserTransaction:
        """Update wallet balance with atomic transaction for Data Bridge sync."""
        try:
            with transaction.atomic():
                # Lock wallet row
                wallet = self.get_queryset().select_for_update().get(id=wallet_id)
                old_balance = wallet.balance
                
                # Create transaction record
                transaction_obj = AdvertiserTransaction(
                    wallet=wallet,
                    amount=new_balance - old_balance,
                    transaction_type=transaction_type,
                    description=description or f"Balance update: {old_balance} -> {new_balance}",
                    metadata={'old_balance': float(old_balance), 'new_balance': float(new_balance)},
                    status='completed'
                )
                transaction_obj.save()
                
                # Update wallet balance
                wallet.balance = new_balance
                wallet.save()
                
                return transaction_obj
                
        except Exception as e:
            logger.error(f"Error in update_balance_atomic: {e}")
            raise
    
    def get_balance_snapshot(self, advertiser_ids: List[str]) -> Dict[str, Decimal]:
        """Get current balance snapshot for multiple advertisers."""
        wallets = self.get_queryset().filter(advertiser_id__in=advertiser_ids)
        
        return {
            str(wallet.advertiser_id): wallet.balance 
            for wallet in wallets
        }
    
    def bulk_balance_update(self, balance_updates: Dict[str, Decimal]) -> int:
        """Bulk update balances for multiple advertisers."""
        try:
            with transaction.atomic():
                # Lock wallets
                wallets = list(
                    self.get_queryset().filter(
                        advertiser_id__in=list(balance_updates.keys())
                    ).select_for_update()
                )
                wallet_map = {w.advertiser_id: w for w in wallets}
                
                updated_count = 0
                for advertiser_id, new_balance in balance_updates.items():
                    wallet = wallet_map.get(advertiser_id)
                    if wallet and wallet.balance != new_balance:
                        old_balance = wallet.balance
                        
                        # Create transaction
                        AdvertiserTransaction.objects.create(
                            wallet=wallet,
                            amount=new_balance - old_balance,
                            transaction_type='bulk_update',
                            description=f"Bulk balance update: {old_balance} -> {new_balance}",
                            metadata={'bulk_update': True, 'old_balance': float(old_balance), 'new_balance': float(new_balance)},
                            status='completed'
                        )
                        
                        # Update balance
                        wallet.balance = new_balance
                        wallet.save()
                        updated_count += 1
                
                return updated_count
                
        except Exception as e:
            logger.error(f"Error in bulk_balance_update: {e}")
            raise


class ReportManager(models.Manager):
    """Custom manager for AdvertiserReport model."""
    
    def get_queryset(self):
        """Get base queryset with optimizations."""
        return super().get_queryset().select_related(
            'advertiser', 'advertiser__user'
        )
    
    def by_advertiser(self, advertiser_id: str):
        """Get reports by advertiser."""
        return self.get_queryset().filter(advertiser_id=advertiser_id)
    
    def by_type(self, report_type: str):
        """Get reports by type."""
        return self.get_queryset().filter(report_type=report_type)
    
    def by_status(self, status: str):
        """Get reports by status."""
        return self.get_queryset().filter(status=status)
    
    def in_period(self, start_date: datetime, end_date: datetime):
        """Get reports in specified period."""
        return self.get_queryset().filter(
            generated_at__gte=start_date,
            generated_at__lte=end_date
        )
    
    def pending_generation(self):
        """Get reports pending generation."""
        return self.get_queryset().filter(status='pending')
    
    def failed_generation(self):
        """Get reports with failed generation."""
        return self.get_queryset().filter(status='failed')
    
    def get_usage_statistics(self, period_days: int = 30) -> Dict[str, Any]:
        """Get report usage statistics."""
        start_date = timezone.now() - timedelta(days=period_days)
        queryset = self.get_queryset().filter(generated_at__gte=start_date)
        
        # Report type usage
        type_counts = queryset.values('report_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Format usage
        format_counts = queryset.values('format').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Status breakdown
        status_counts = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        return {
            'period_days': period_days,
            'total_reports': queryset.count(),
            'type_usage': list(type_counts),
            'format_usage': list(format_counts),
            'status_breakdown': list(status_counts)
        }


# Base manager with common functionality
class BaseManager(models.Manager):
    """Base manager with common functionality."""
    
    def get_or_none(self, **kwargs):
        """Get object or return None."""
        try:
            return self.get(**kwargs)
        except self.model.DoesNotExist:
            return None
    
    def get_cached(self, cache_key: str, timeout: int = 300, **kwargs):
        """Get cached object or cache it."""
        obj = cache.get(cache_key)
        if obj is None:
            obj = self.get_or_none(**kwargs)
            if obj:
                cache.set(cache_key, obj, timeout)
        return obj
    
    def bulk_create_with_cache(self, objects, cache_keys: List[str] = None, timeout: int = 300):
        """Bulk create objects and update cache."""
        with transaction.atomic():
            created_objects = self.bulk_create(objects)
            
            if cache_keys:
                for obj, cache_key in zip(created_objects, cache_keys):
                    cache.set(cache_key, obj, timeout)
            
            return created_objects
    
    def annotate_with_counts(self, *fields):
        """Annotate queryset with count fields."""
        queryset = self.get_queryset()
        for field in fields:
            queryset = queryset.annotate(**{f"{field}_count": Count(field)})
        return queryset
    
    def annotate_with_sums(self, **fields):
        """Annotate queryset with sum fields."""
        queryset = self.get_queryset()
        for field_name, field in fields.items():
            queryset = queryset.annotate(**{f"{field_name}_sum": Sum(field)})
        return queryset


# Manager factory for dynamic manager creation
class ManagerFactory:
    """Factory class for creating custom managers."""
    
    @staticmethod
    def create_performance_manager(model_class, metrics_fields: List[str]):
        """Create a manager with performance metrics."""
        class PerformanceManager(BaseManager):
            def get_performance_metrics(self, obj_id):
                """Get performance metrics for an object."""
                obj = self.get_queryset().get(id=obj_id)
                metrics = {}
                
                for field in metrics_fields:
                    if hasattr(obj, field):
                        metrics[field] = getattr(obj, field)
                
                return metrics
        
        return PerformanceManager()
    
    @staticmethod
    def create_cached_manager(model_class, cache_timeout: int = 300):
        """Create a manager with caching capabilities."""
        class CachedManager(BaseManager):
            def get_cached_queryset(self, cache_key: str):
                """Get cached queryset."""
                return cache.get(cache_key)
            
            def cache_queryset(self, cache_key: str, queryset, timeout: int = None):
                """Cache queryset."""
                timeout = timeout or cache_timeout
                cache.set(cache_key, list(queryset), timeout)
                return queryset
        
        return CachedManager()


# Export all managers
__all__ = [
    'AdvertiserManager',
    'CampaignManager',
    'OfferManager',
    'ConversionManager',
    'TransactionManager',
    'ReportManager',
    'BaseManager',
    'ManagerFactory',
]
