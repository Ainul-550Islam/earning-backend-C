# api/cms/services_new/SurveyRewardService.py
"""
Service layer for Survey Reward Management
Handles reward calculation, distribution, and budget management
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.contrib.auth import get_user_model

from ..models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
from ..models_new.profile_surveys import SurveyCompletion, SurveyTemplate

logger = logging.getLogger(__name__)
User = get_user_model()


class SurveyRewardService:
    """
    Main service for survey reward management
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
    
    def calculate_reward(self, completion: SurveyCompletion, reward_config: SurveyReward) -> Decimal:
        """Calculate reward amount for a survey completion"""
        if not reward_config.is_active():
            return Decimal('0')
        
        reward_amount = reward_config.base_amount
        
        # Quality bonus for tiered rewards
        if (reward_config.reward_type == 'tiered' and 
            completion.quality_score and 
            completion.quality_score >= reward_config.min_quality_for_bonus):
            reward_amount += reward_config.bonus_amount
        
        # Speed bonus for performance rewards
        if (reward_config.reward_type == 'performance' and 
            reward_config.completion_time_threshold and 
            completion.time_spent_seconds <= reward_config.completion_time_threshold):
            reward_amount += reward_config.speed_bonus_amount
        
        # Apply penalties for quality issues.
        #
        # Previous code applied each penalty as a separate multiplicative step:
        #   reward *= 0.5           (speeding)
        #   reward *= (1 - checks)  (attention)
        #
        # Penalty accumulation.
        # Speeding penalty is WAIVED when the completion's quality_score meets or
        # exceeds the reward's min_quality_for_bonus threshold — the assumption is
        # that genuinely high-quality work cannot be fraudulently fast.
        total_penalty = Decimal('0')

        quality_threshold = reward_config.min_quality_for_bonus
        quality_score     = completion.quality_score or Decimal('0')
        speeding_waived   = (quality_threshold is not None and quality_score >= quality_threshold)

        if completion.flagged_for_speeding and not speeding_waived:
            total_penalty += Decimal('0.5')                          # 50 % speed penalty

        if completion.failed_attention_checks > 0:
            check_penalty  = Decimal('0.1') * completion.failed_attention_checks
            total_penalty += min(check_penalty, Decimal('0.5'))      # attention cap 50 %

        # Hard ceiling: never strip more than 75 %.
        total_penalty  = min(total_penalty, Decimal('0.75'))
        reward_amount *= (Decimal('1') - total_penalty)

        return max(reward_amount, Decimal('0'))
    
    def create_reward_transaction(self, completion: SurveyCompletion, 
                             reward_config: SurveyReward, 
                             amount: Decimal,
                             transaction_type: str = 'earned') -> RewardTransaction:
        """Create a reward transaction"""
        transaction = RewardTransaction.objects.create(
            user=completion.user,
            survey_completion=completion,
            reward_config=reward_config,
            transaction_type=transaction_type,
            amount=amount,
            currency=reward_config.currency,
            description=f"Reward for completing {completion.survey.title}",
            reference_id=str(completion.uuid)
        )
        
        logger.info(f"Created reward transaction: {transaction.uuid} for user {completion.user.username}")
        return transaction
    
    def approve_transaction(self, transaction_uuid: str, reviewer=None, notes: str = "") -> RewardTransaction:
        """Approve a reward transaction"""
        try:
            transaction = RewardTransaction.objects.get(uuid=transaction_uuid)
            transaction.approve(reviewer=reviewer, notes=notes)
            
            logger.info(f"Approved reward transaction: {transaction.uuid}")
            return transaction
            
        except RewardTransaction.DoesNotExist:
            raise ValueError("Transaction not found")
    
    def process_survey_completion_rewards(self, completion_uuid: str) -> List[RewardTransaction]:
        """Process all rewards for a survey completion"""
        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
            
            if completion.status != 'approved':
                logger.warning(f"Completion {completion_uuid} not approved, skipping rewards")
                return []
            
            # Get all applicable reward configs
            reward_configs = SurveyReward.objects.filter(
                survey=completion.survey,
                status='active'
            )
            
            transactions = []
            for reward_config in reward_configs:
                reward_amount = self.calculate_reward(completion, reward_config)
                
                if reward_amount > 0:
                    transaction = self.create_reward_transaction(
                        completion, reward_config, reward_amount
                    )
                    transactions.append(transaction)
            
            return transactions
            
        except SurveyCompletion.DoesNotExist:
            raise ValueError("Survey completion not found")
    
    def get_user_reward_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get user's reward summary for specified period"""
        cache_key = f"user_reward_summary_{user_id}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        start_date = timezone.now() - timedelta(days=days)
        
        transactions = RewardTransaction.objects.filter(
            user_id=user_id,
            created_at__gte=start_date,
            status='paid'
        ).select_related('currency', 'survey_completion__survey')
        
        summary = {
            'period_days': days,
            'total_transactions': transactions.count(),
            'total_amount': float(transactions.aggregate(
                total=Sum('amount')
            )['total'] or 0),
            'by_currency': list(
                transactions.values('currency')
                .annotate(
                    count=Count('id'),
                    total=Sum('amount')
                )
                .order_by('-total')
            ),
            'recent_transactions': list(
                transactions.order_by('-created_at')[:10]
                .values('uuid', 'amount', 'currency', 'created_at')
            ),
            'by_type': list(
                transactions.values('transaction_type')
                .annotate(
                    count=Count('id'),
                    total=Sum('amount')
                )
                .order_by('-total')
            )
        }
        
        cache.set(cache_key, summary, self.cache_timeout)
        return summary
    
    def get_reward_pool_utilization(self, pool_uuid: str) -> Dict[str, Any]:
        """Get reward pool utilization metrics"""
        cache_key = f"pool_utilization_{pool_uuid}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            pool = RewardPool.objects.get(uuid=pool_uuid)
            
            # Get recent transactions (30-day window; pool FK not stored on transaction)
            recent_transactions = RewardTransaction.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            )
            
            utilization = {
                'pool_info': {
                    'uuid': str(pool.uuid),
                    'name': pool.name,
                    'total_budget': float(pool.total_budget),
                    'allocated_amount': float(pool.allocated_amount),
                    'paid_amount': float(pool.paid_amount),
                    'remaining_budget': float(pool.remaining_budget),
                    'available_budget': float(pool.available_budget)
                },
                'utilization_rate': round(
                    (pool.allocated_amount / pool.total_budget * 100) 
                    if pool.total_budget > 0 else 0, 2
                ),
                'recent_activity': {
                    'total_transactions': recent_transactions.count(),
                    'total_amount': float(recent_transactions.aggregate(
                        total=Sum('amount')
                    )['total'] or 0),
                    'daily_average': float(recent_transactions.aggregate(
                        total=Sum('amount')
                    )['total'] or 0) / 30,  # 30-day average
                },
                'alerts': self._get_pool_alerts(pool)
            }
            
            cache.set(cache_key, utilization, self.cache_timeout)
            return utilization
            
        except RewardPool.DoesNotExist:
            raise ValueError("Reward pool not found")
    
    def _get_pool_alerts(self, pool: RewardPool) -> List[Dict[str, str]]:
        """Get alerts for a reward pool"""
        alerts = []
        
        # Low budget alert
        if pool.remaining_budget < (pool.total_budget * Decimal('0.1')):  # Less than 10%
            alerts.append({
                'type': 'low_budget',
                'severity': 'warning',
                'message': f"Pool {pool.name} has less than 10% budget remaining"
            })
        
        # High utilization alert
        utilization_rate = (pool.allocated_amount / pool.total_budget * 100) if pool.total_budget > 0 else 0
        if utilization_rate > 90:
            alerts.append({
                'type': 'high_utilization',
                'severity': 'warning',
                'message': f"Pool {pool.name} has {utilization_rate:.1f}% utilization rate"
            })
        
        # Auto-refill trigger alert
        if (pool.auto_refill and 
            pool.refill_amount and 
            pool.refill_threshold and 
            pool.remaining_budget <= pool.refill_threshold):
            alerts.append({
                'type': 'auto_refill_trigger',
                'severity': 'info',
                'message': f"Pool {pool.name} will auto-refill {pool.refill_amount}"
            })
        
        return alerts
    
    def get_survey_reward_analytics(self, survey_uuid: str, days: int = 30) -> Dict[str, Any]:
        """Get reward analytics for a specific survey"""
        cache_key = f"survey_reward_analytics_{survey_uuid}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            survey = SurveyTemplate.objects.get(uuid=survey_uuid)
            start_date = timezone.now() - timedelta(days=days)
            
            transactions = RewardTransaction.objects.filter(
                survey_completion__survey=survey,
                created_at__gte=start_date,
                status='paid'
            ).select_related('reward_config', 'user')
            
            analytics = {
                'survey_info': {
                    'uuid': str(survey.uuid),
                    'title': survey.title,
                    'base_reward': float(survey.base_reward),
                    'bonus_reward': float(survey.bonus_reward),
                    'estimated_minutes': survey.estimated_minutes
                },
                'reward_summary': {
                    'total_transactions': transactions.count(),
                    'total_amount': float(transactions.aggregate(
                        total=Sum('amount')
                    )['total'] or 0),
                    'average_reward': float(transactions.aggregate(
                        avg=Avg('amount')
                    )['avg'] or 0),
                    'unique_users': transactions.values('user').distinct().count()
                },
                'reward_types': list(
                    transactions.values('reward_config__reward_type')
                    .annotate(
                        count=Count('id'),
                        total=Sum('amount')
                    )
                    .order_by('-total')
                ),
                'top_earners': list(
                    transactions.values('user__username', 'user__id')
                    .annotate(total_earned=Sum('amount'))
                    .order_by('-total_earned')[:10]
                ),
                'daily_trends': self._get_daily_reward_trends(transactions),
                'demographics': self._get_reward_demographics(transactions)
            }
            
            cache.set(cache_key, analytics, self.cache_timeout)
            return analytics
            
        except SurveyTemplate.DoesNotExist:
            raise ValueError("Survey not found")
    
    def _get_daily_reward_trends(self, transactions) -> List[Dict[str, Any]]:
        """Get daily reward trends"""
        from django.db.models.functions import TruncDate
        
        return list(
            transactions
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                count=Count('id'),
                total=Sum('amount')
            )
            .order_by('date')[:30]
        )
    
    def _get_reward_demographics(self, transactions) -> Dict[str, Any]:
        """Get demographic breakdown of reward recipients"""
        demographics = {
            'age_groups': {},
            'countries': {},
            'user_segments': {},
            'registration_periods': {}
        }
        
        for transaction in transactions.select_related('user__profile'):
            profile = transaction.user.profile
            if not profile:
                continue
            
            # Age groups
            if profile.age:
                age_group = self._get_age_group(profile.age)
                demographics['age_groups'][age_group] = demographics['age_groups'].get(age_group, 0) + 1
            
            # Countries
            if profile.country:
                demographics['countries'][profile.country] = demographics['countries'].get(profile.country, 0) + 1
            
            # User segments (would need relationship)
            # This is a placeholder - would need to implement user segment tracking
            demographics['user_segments']['all_users'] = transactions.values('user').distinct().count()
        
        return demographics
    
    def _get_age_group(self, age: int) -> str:
        """Get age group category"""
        if age < 18:
            return 'Under 18'
        elif age < 25:
            return '18-24'
        elif age < 35:
            return '25-34'
        elif age < 45:
            return '35-44'
        elif age < 55:
            return '45-54'
        else:
            return '55+'
    
    def update_reward_statistics(self, reward_config_uuid: str) -> Dict[str, Any]:
        """Update statistics for a reward configuration"""
        try:
            reward_config = SurveyReward.objects.get(uuid=reward_config_uuid)
            
            # Get all transactions for this config
            transactions = RewardTransaction.objects.filter(reward_config=reward_config)
            
            # Update statistics
            total_paid = transactions.filter(status='paid').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')
            
            reward_config.total_paid = total_paid
            reward_config.times_paid = transactions.filter(status='paid').count()
            reward_config.save(update_fields=['total_paid', 'times_paid'])
            
            return {
                'reward_config_uuid': reward_config_uuid,
                'total_paid': float(total_paid),
                'times_paid': reward_config.times_paid,
                'updated_at': timezone.now().isoformat()
            }
            
        except SurveyReward.DoesNotExist:
            raise ValueError("Reward configuration not found")
    
    def get_system_reward_overview(self) -> Dict[str, Any]:
        """Get system-wide reward overview"""
        cache_key = "system_reward_overview"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Get all active reward pools
        pools = RewardPool.objects.filter(is_active=True)
        
        # Get all reward transactions
        transactions = RewardTransaction.objects.filter(status='paid')
        
        overview = {
            'pools': {
                'total_pools': pools.count(),
                'total_budget': float(pools.aggregate(
                    total=Sum('total_budget')
                )['total'] or 0),
                'total_allocated': float(pools.aggregate(
                    total=Sum('allocated_amount')
                )['total'] or 0),
                'total_paid': float(pools.aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0),
                'average_utilization': round(
                    sum((p.allocated_amount / p.total_budget * 100) 
                     for p in pools if p.total_budget > 0) / pools.count(), 2
                ) if pools.exists() else 0
            },
            'transactions': {
                'total_transactions': transactions.count(),
                'total_amount': float(transactions.aggregate(
                    total=Sum('amount')
                )['total'] or 0),
                'last_24h': float(transactions.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).aggregate(
                    total=Sum('amount')
                )['total'] or 0),
                'last_7d': float(transactions.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).aggregate(
                    total=Sum('amount')
                )['total'] or 0),
                'last_30d': float(transactions.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).aggregate(
                    total=Sum('amount')
                )['total'] or 0)
            },
            'generated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, overview, self.cache_timeout)
        return overview
