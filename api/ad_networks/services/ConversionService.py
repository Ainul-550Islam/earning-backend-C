"""
api/ad_networks/services/ConversionService.py
Service for processing, verifying, and approving conversions
SaaS-ready with tenant support
"""

import logging
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from api.ad_networks.models import (
    OfferConversion, UserOfferEngagement, Offer, AdNetwork,
    OfferReward, NetworkAPILog
)
from api.ad_networks.choices import (
    ConversionStatus, EngagementStatus, RiskLevel
)
from api.ad_networks.constants import (
    FRAUD_SCORE_THRESHOLD,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class ConversionService:
    """
    Service for processing and managing conversions
    """
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
    
    def process_conversion(self, conversion_data: Dict) -> Dict:
        """
        Process a new conversion
        """
        try:
            with transaction.atomic():
                # Validate conversion data
                validation_result = self._validate_conversion_data(conversion_data)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': validation_result['error'],
                        'code': 'validation_failed'
                    }
                
                # Get or create engagement
                engagement = self._get_or_create_engagement(conversion_data)
                if not engagement:
                    return {
                        'success': False,
                        'error': 'Engagement not found or could not be created',
                        'code': 'engagement_error'
                    }
                
                # Check for duplicate conversion
                if self._conversion_exists(engagement):
                    return {
                        'success': False,
                        'error': 'Conversion already exists',
                        'code': 'duplicate_conversion'
                    }
                
                # Calculate fraud score
                fraud_score = self._calculate_fraud_score(engagement, conversion_data)
                
                # Create conversion
                conversion = self._create_conversion(engagement, conversion_data, fraud_score)
                
                # Auto-approve if low fraud score
                if fraud_score < 30:
                    self._approve_conversion(conversion, 'auto_approved_low_risk')
                elif fraud_score < FRAUD_SCORE_THRESHOLD:
                    self._flag_for_review(conversion)
                else:
                    self._reject_conversion(conversion, 'auto_rejected_high_fraud')
                
                # Create reward if approved
                if conversion.conversion_status == ConversionStatus.APPROVED:
                    self._create_reward(engagement, conversion)
                
                # Update engagement status
                engagement.status = EngagementStatus.COMPLETED
                engagement.completed_at = timezone.now()
                engagement.save(update_fields=['status', 'completed_at'])
                
                # Update offer stats
                self._update_offer_stats(engagement.offer)
                
                # Clear caches
                self._clear_user_caches(engagement.user)
                
                logger.info(f"Conversion processed: {conversion.id} for user {engagement.user.id}")
                
                return {
                    'success': True,
                    'conversion_id': conversion.id,
                    'engagement_id': engagement.id,
                    'status': conversion.conversion_status,
                    'fraud_score': fraud_score,
                    'auto_approved': fraud_score < 30
                }
                
        except Exception as e:
            logger.error(f"Conversion processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'processing_error'
            }
    
    def verify_conversion(self, conversion_id: int, verifier_user: User = None, 
                       approved: bool = None, notes: str = None) -> Dict:
        """
        Manually verify a conversion
        """
        try:
            with transaction.atomic():
                # Get conversion
                conversion = OfferConversion.objects.get(id=conversion_id)
                
                if conversion.is_verified:
                    return {
                        'success': False,
                        'error': 'Conversion already verified',
                        'code': 'already_verified'
                    }
                
                # Update verification status
                conversion.is_verified = True
                conversion.verified_at = timezone.now()
                conversion.verified_by = verifier_user
                
                if notes:
                    conversion.verification_notes = notes
                
                # Process approval/rejection
                if approved is True:
                    self._approve_conversion(conversion, 'manual_verification')
                    self._create_reward(conversion.engagement, conversion)
                elif approved is False:
                    self._reject_conversion(conversion, 'manual_verification')
                
                conversion.save()
                
                # Update engagement
                if approved:
                    conversion.engagement.status = EngagementStatus.APPROVED
                else:
                    conversion.engagement.status = EngagementStatus.REJECTED
                
                conversion.engagement.save(update_fields=['status'])
                
                # Update offer stats
                self._update_offer_stats(conversion.engagement.offer)
                
                # Clear caches
                self._clear_user_caches(conversion.engagement.user)
                
                action = 'approved' if approved else 'rejected'
                logger.info(f"Conversion {conversion_id} manually {action} by {verifier_user}")
                
                return {
                    'success': True,
                    'conversion_id': conversion.id,
                    'action': action,
                    'verified_by': verifier_user.id if verifier_user else None
                }
                
        except OfferConversion.DoesNotExist:
            return {
                'success': False,
                'error': f'Conversion with ID {conversion_id} not found',
                'code': 'not_found'
            }
        except Exception as e:
            logger.error(f"Conversion verification failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'verification_error'
            }
    
    def reverse_conversion(self, conversion_id: int, reason: str = None) -> Dict:
        """
        Reverse a conversion (chargeback)
        """
        try:
            with transaction.atomic():
                # Get conversion
                conversion = OfferConversion.objects.get(id=conversion_id)
                
                if conversion.conversion_status == ConversionStatus.CHARGEBACK:
                    return {
                        'success': False,
                        'error': 'Conversion already reversed',
                        'code': 'already_reversed'
                    }
                
                # Update conversion status
                conversion.conversion_status = ConversionStatus.CHARGEBACK
                conversion.chargeback_at = timezone.now()
                conversion.chargeback_reason = reason
                conversion.chargeback_processed = False
                
                conversion.save()
                
                # Update engagement
                conversion.engagement.status = EngagementStatus.CANCELED
                conversion.engagement.save(update_fields=['status'])
                
                # Remove or reverse reward
                self._reverse_reward(conversion)
                
                # Update offer stats
                self._update_offer_stats(conversion.engagement.offer)
                
                # Clear caches
                self._clear_user_caches(conversion.engagement.user)
                
                logger.info(f"Conversion {conversion_id} reversed: {reason}")
                
                return {
                    'success': True,
                    'conversion_id': conversion.id,
                    'reason': reason
                }
                
        except OfferConversion.DoesNotExist:
            return {
                'success': False,
                'error': f'Conversion with ID {conversion_id} not found',
                'code': 'not_found'
            }
        except Exception as e:
            logger.error(f"Conversion reversal failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'reversal_error'
            }
    
    def get_user_conversions(self, user_id: int, status: str = None, 
                           limit: int = None, offset: int = 0) -> Dict:
        """
        Get user's conversions with pagination
        """
        try:
            conversions = OfferConversion.objects.filter(
                engagement__user_id=user_id
            ).select_related(
                'engagement', 'engagement__user', 'engagement__offer',
                'engagement__offer__ad_network'
            ).order_by('-created_at')
            
            if status:
                conversions = conversions.filter(conversion_status=status)
            
            total_count = conversions.count()
            
            if limit:
                conversions = conversions[offset:offset + limit]
            
            conversions_data = []
            for conversion in conversions:
                conversions_data.append({
                    'id': conversion.id,
                    'engagement_id': conversion.engagement.id,
                    'offer_id': conversion.engagement.offer.id,
                    'offer_title': conversion.engagement.offer.title,
                    'network_name': conversion.engagement.offer.ad_network.name,
                    'payout': float(conversion.payout or 0),
                    'currency': conversion.network_currency,
                    'status': conversion.conversion_status,
                    'fraud_score': conversion.fraud_score,
                    'risk_level': conversion.risk_level,
                    'created_at': conversion.created_at,
                    'verified_at': conversion.verified_at,
                    'payment_date': conversion.payment_date,
                    'reward_earned': float(conversion.engagement.reward_earned or 0)
                })
            
            return {
                'success': True,
                'conversions': conversions_data,
                'total_count': total_count,
                'has_more': offset + limit < total_count if limit else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get user conversions: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'conversions': []
            }
    
    def get_conversion_stats(self, user_id: int = None, network_id: int = None,
                          days: int = 30) -> Dict:
        """
        Get conversion statistics
        """
        try:
            from django.db.models import Count, Sum, Avg, Q
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Base queryset
            conversions = OfferConversion.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            # Apply filters
            if user_id:
                conversions = conversions.filter(engagement__user_id=user_id)
            
            if network_id:
                conversions = conversions.filter(
                    engagement__offer__ad_network_id=network_id
                )
            
            # Calculate stats
            stats = conversions.aggregate(
                total_conversions=Count('id'),
                approved_conversions=Count(
                    'id', 
                    filter=Q(conversion_status=ConversionStatus.APPROVED)
                ),
                rejected_conversions=Count(
                    'id',
                    filter=Q(conversion_status=ConversionStatus.REJECTED)
                ),
                pending_conversions=Count(
                    'id',
                    filter=Q(conversion_status=ConversionStatus.PENDING)
                ),
                total_payout=Sum('payout'),
                approved_payout=Sum(
                    'payout',
                    filter=Q(conversion_status=ConversionStatus.APPROVED)
                ),
                avg_fraud_score=Avg('fraud_score'),
                high_risk_conversions=Count(
                    'id',
                    filter=Q(fraud_score__gte=FRAUD_SCORE_THRESHOLD)
                )
            )
            
            # Calculate rates
            approval_rate = 0
            if stats['total_conversions'] > 0:
                approval_rate = (stats['approved_conversions'] / stats['total_conversions']) * 100
            
            fraud_rate = 0
            if stats['total_conversions'] > 0:
                fraud_rate = (stats['high_risk_conversions'] / stats['total_conversions']) * 100
            
            return {
                'success': True,
                'period_days': days,
                'total_conversions': stats['total_conversions'],
                'approved_conversions': stats['approved_conversions'],
                'rejected_conversions': stats['rejected_conversions'],
                'pending_conversions': stats['pending_conversions'],
                'total_payout': float(stats['total_payout'] or 0),
                'approved_payout': float(stats['approved_payout'] or 0),
                'avg_fraud_score': float(stats['avg_fraud_score'] or 0),
                'high_risk_conversions': stats['high_risk_conversions'],
                'approval_rate': round(approval_rate, 2),
                'fraud_rate': round(fraud_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversion stats: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_conversion_data(self, conversion_data: Dict) -> Dict:
        """
        Validate conversion data
        """
        required_fields = ['user_id', 'offer_id', 'payout']
        
        for field in required_fields:
            if field not in conversion_data:
                return {
                    'valid': False,
                    'error': f'Missing required field: {field}'
                }
        
        # Validate payout
        try:
            payout = Decimal(str(conversion_data['payout']))
            if payout <= 0:
                return {
                    'valid': False,
                    'error': 'Payout must be positive'
                }
        except (ValueError, TypeError):
            return {
                'valid': False,
                'error': 'Invalid payout amount'
            }
        
        return {'valid': True}
    
    def _get_or_create_engagement(self, conversion_data: Dict) -> Optional[UserOfferEngagement]:
        """
        Get or create engagement for conversion
        """
        try:
            user_id = conversion_data['user_id']
            offer_id = conversion_data['offer_id']
            
            engagement = UserOfferEngagement.objects.filter(
                user_id=user_id,
                offer_id=offer_id,
                status__in=[EngagementStatus.CLICKED, EngagementStatus.STARTED, EngagementStatus.IN_PROGRESS]
            ).first()
            
            if not engagement:
                # Create new engagement if click_id is provided
                click_id = conversion_data.get('click_id')
                if click_id:
                    engagement = UserOfferEngagement.objects.create(
                        user_id=user_id,
                        offer_id=offer_id,
                        click_id=click_id,
                        status=EngagementStatus.STARTED,
                        ip_address=conversion_data.get('ip_address'),
                        user_agent=conversion_data.get('user_agent')
                    )
            
            return engagement
            
        except Exception as e:
            logger.error(f"Failed to get/create engagement: {str(e)}")
            return None
    
    def _conversion_exists(self, engagement: UserOfferEngagement) -> bool:
        """
        Check if conversion already exists for engagement
        """
        return OfferConversion.objects.filter(
            engagement=engagement
        ).exists()
    
    def _calculate_fraud_score(self, engagement: UserOfferEngagement, conversion_data: Dict) -> float:
        """
        Calculate fraud score for conversion
        """
        score = 0.0
        
        # Time-based check
        if engagement.started_at and engagement.created_at:
            completion_time = (engagement.created_at - engagement.started_at).total_seconds()
            if completion_time < 30:  # Less than 30 seconds
                score += 30
            elif completion_time < 60:  # Less than 1 minute
                score += 15
        
        # IP-based check
        ip_address = conversion_data.get('ip_address')
        if ip_address:
            from api.ad_networks.models import OfferConversion
            recent_conversions_same_ip = OfferConversion.objects.filter(
                engagement__ip_address=ip_address,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_conversions_same_ip > 5:
                score += 40
            elif recent_conversions_same_ip > 2:
                score += 20
        
        # User velocity check
        from api.ad_networks.models import OfferConversion
        recent_conversions_same_user = OfferConversion.objects.filter(
            engagement__user=engagement.user,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_conversions_same_user > 10:
            score += 50
        elif recent_conversions_same_user > 5:
            score += 25
        
        # Payout amount check (unusually high)
        payout = Decimal(str(conversion_data.get('payout', 0)))
        if payout > Decimal('100.00'):
            score += 30
        elif payout > Decimal('50.00'):
            score += 15
        
        return min(100.0, score)
    
    def _create_conversion(self, engagement: UserOfferEngagement, 
                        conversion_data: Dict, fraud_score: float) -> OfferConversion:
        """
        Create conversion record
        """
        # Determine risk level
        if fraud_score >= 80:
            risk_level = RiskLevel.HIGH
        elif fraud_score >= 50:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Determine initial status
        if fraud_score >= FRAUD_SCORE_THRESHOLD:
            initial_status = ConversionStatus.REJECTED
        elif fraud_score >= 50:
            initial_status = ConversionStatus.PENDING
        else:
            initial_status = ConversionStatus.APPROVED
        
        return OfferConversion.objects.create(
            engagement=engagement,
            postback_data=conversion_data,
            payout=Decimal(str(conversion_data.get('payout', 0))),
            network_currency=conversion_data.get('currency', 'USD'),
            exchange_rate=Decimal(str(conversion_data.get('exchange_rate', 1))),
            conversion_status=initial_status,
            fraud_score=fraud_score,
            risk_level=risk_level,
            metadata=conversion_data.get('metadata', {}),
            tenant_id=self.tenant_id
        )
    
    def _approve_conversion(self, conversion: OfferConversion, reason: str = None):
        """
        Approve a conversion
        """
        conversion.conversion_status = ConversionStatus.APPROVED
        conversion.approved_at = timezone.now()
        if reason:
            conversion.verification_notes = f"Approved: {reason}"
        conversion.save(update_fields=['conversion_status', 'approved_at', 'verification_notes'])
    
    def _reject_conversion(self, conversion: OfferConversion, reason: str = None):
        """
        Reject a conversion
        """
        conversion.conversion_status = ConversionStatus.REJECTED
        if reason:
            conversion.rejection_reason = reason
        conversion.save(update_fields=['conversion_status', 'rejection_reason'])
    
    def _flag_for_review(self, conversion: OfferConversion):
        """
        Flag conversion for manual review
        """
        conversion.conversion_status = ConversionStatus.PENDING
        conversion.save(update_fields=['conversion_status'])
    
    def _create_reward(self, engagement: UserOfferEngagement, conversion: OfferConversion):
        """
        Create reward for approved conversion
        """
        try:
            # Calculate reward amount
            reward_amount = conversion.payout
            
            # Create reward
            OfferReward.objects.create(
                user=engagement.user,
                offer=engagement.offer,
                engagement=engagement,
                amount=reward_amount,
                currency=conversion.network_currency,
                status='pending',
                approved_at=timezone.now(),
                tenant_id=self.tenant_id
            )
            
            logger.info(f"Reward created: {reward_amount} {conversion.network_currency} for user {engagement.user.id}")
            
        except Exception as e:
            logger.error(f"Failed to create reward: {str(e)}")
    
    def _reverse_reward(self, conversion: OfferConversion):
        """
        Reverse or remove reward for chargeback
        """
        try:
            # Find and update reward
            reward = OfferReward.objects.filter(
                engagement=conversion.engagement
            ).first()
            
            if reward:
                reward.status = 'cancelled'
                reward.save(update_fields=['status'])
                
                logger.info(f"Reward reversed for conversion {conversion.id}")
            
        except Exception as e:
            logger.error(f"Failed to reverse reward: {str(e)}")
    
    def _update_offer_stats(self, offer: Offer):
        """
        Update offer statistics
        """
        try:
            from django.db.models import Count, Sum
            
            # Calculate new stats
            stats = UserOfferEngagement.objects.filter(
                offer=offer
            ).aggregate(
                total_conversions=Count(
                    'id',
                    filter=Q(status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED])
                ),
                total_clicks=Count('id')
            )
            
            # Update offer
            offer.total_conversions = stats['total_conversions']
            offer.click_count = stats['total_clicks']
            offer.conversion_rate = (
                (stats['total_conversions'] / stats['total_clicks'] * 100)
                if stats['total_clicks'] > 0 else 0
            )
            offer.save(update_fields=['total_conversions', 'click_count', 'conversion_rate'])
            
        except Exception as e:
            logger.error(f"Failed to update offer stats: {str(e)}")
    
    def _clear_user_caches(self, user):
        """
        Clear user-related caches
        """
        try:
            # Clear user stats cache
            cache.delete(f'user_{user.id}_stats')
            
            # Clear user engagement cache
            cache.delete(f'user_{user.id}_engagements')
            
            # Clear user conversions cache
            cache.delete(f'user_{user.id}_conversions')
            
        except Exception as e:
            logger.error(f"Failed to clear user caches: {str(e)}")
    
    @classmethod
    def get_pending_conversions(cls, limit: int = 100) -> List[Dict]:
        """
        Get pending conversions for review
        """
        try:
            conversions = OfferConversion.objects.filter(
                conversion_status=ConversionStatus.PENDING
            ).select_related(
                'engagement', 'engagement__user', 'engagement__offer'
            ).order_by('created_at')[:limit]
            
            conversions_data = []
            for conversion in conversions:
                conversions_data.append({
                    'id': conversion.id,
                    'engagement_id': conversion.engagement.id,
                    'user_id': conversion.engagement.user.id,
                    'user_email': conversion.engagement.user.email,
                    'offer_id': conversion.engagement.offer.id,
                    'offer_title': conversion.engagement.offer.title,
                    'payout': float(conversion.payout or 0),
                    'fraud_score': conversion.fraud_score,
                    'risk_level': conversion.risk_level,
                    'created_at': conversion.created_at,
                    'postback_data': conversion.postback_data
                })
            
            return conversions_data
            
        except Exception as e:
            logger.error(f"Failed to get pending conversions: {str(e)}")
            return []
    
    @classmethod
    def bulk_approve_conversions(cls, conversion_ids: List[int], verifier_user: User) -> Dict:
        """
        Bulk approve conversions
        """
        try:
            with transaction.atomic():
                conversions = OfferConversion.objects.filter(
                    id__in=conversion_ids
                )
                
                approved_count = 0
                for conversion in conversions:
                    cls._approve_conversion(conversion, 'bulk_approval')
                    
                    # Create reward if not already created
                    if conversion.conversion_status == ConversionStatus.APPROVED:
                        # This would need the engagement object
                        pass
                    
                    approved_count += 1
                
                logger.info(f"Bulk approved {approved_count} conversions by {verifier_user.id}")
                
                return {
                    'success': True,
                    'approved_count': approved_count,
                    'total_requested': len(conversion_ids)
                }
                
        except Exception as e:
            logger.error(f"Bulk approval failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
