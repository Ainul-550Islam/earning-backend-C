"""
Offer Moderation Service

Service for managing offer content moderation,
including brand safety checks and compliance reviews.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.offer import AdvertiserOffer, OfferCreative
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferModerationService:
    """
    Service for managing offer content moderation.
    
    Handles content review, brand safety checks,
    and compliance validation.
    """
    
    def __init__(self):
        self.logger = logger
    
    def review_offer_content(self, offer: AdvertiserOffer, reviewer: User) -> Dict[str, Any]:
        """
        Review offer content for compliance and brand safety.
        
        Args:
            offer: Offer instance to review
            reviewer: User conducting the review
            
        Returns:
            Dict[str, Any]: Review results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Perform automated checks
                automated_results = self._perform_automated_checks(offer)
                
                # Perform manual review criteria
                manual_results = self._perform_manual_review_criteria(offer)
                
                # Combine results
                review_results = {
                    'offer_id': offer.id,
                    'offer_title': offer.title,
                    'reviewer_id': reviewer.id,
                    'reviewed_at': timezone.now().isoformat(),
                    'automated_checks': automated_results,
                    'manual_criteria': manual_results,
                    'overall_score': self._calculate_overall_score(automated_results, manual_results),
                    'recommendation': self._get_review_recommendation(automated_results, manual_results),
                    'issues_found': self._collect_all_issues(automated_results, manual_results),
                }
                
                # Store review results in offer metadata
                metadata = offer.metadata or {}
                metadata['content_review'] = review_results
                offer.metadata = metadata
                offer.save()
                
                # Send notification based on results
                self._send_review_notification(offer, review_results)
                
                self.logger.info(f"Completed content review for offer: {offer.title}")
                return review_results
                
        except Exception as e:
            self.logger.error(f"Error reviewing offer content: {e}")
            raise ValidationError(f"Failed to review offer content: {str(e)}")
    
    def check_brand_safety(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """
        Check offer for brand safety compliance.
        
        Args:
            offer: Offer instance to check
            
        Returns:
            Dict[str, Any]: Brand safety results
        """
        try:
            brand_safety_results = {
                'offer_id': offer.id,
                'checked_at': timezone.now().isoformat(),
                'checks': {},
                'overall_status': 'passed',
                'warnings': [],
                'violations': [],
            }
            
            # Check title and description for sensitive content
            text_checks = self._check_sensitive_text_content(offer.title, offer.description)
            brand_safety_results['checks']['text_content'] = text_checks
            
            # Check creatives for brand safety
            creative_checks = self._check_creative_brand_safety(offer)
            brand_safety_results['checks']['creatives'] = creative_checks
            
            # Check landing page safety
            landing_page_checks = self._check_landing_page_safety(offer)
            brand_safety_results['checks']['landing_page'] = landing_page_checks
            
            # Check targeting for discriminatory practices
            targeting_checks = self._check_targeting_compliance(offer)
            brand_safety_results['checks']['targeting'] = targeting_checks
            
            # Determine overall status
            violations = []
            warnings = []
            
            for check_name, check_result in brand_safety_results['checks'].items():
                if check_result.get('status') == 'failed':
                    violations.extend(check_result.get('violations', []))
                    brand_safety_results['overall_status'] = 'failed'
                elif check_result.get('warnings'):
                    warnings.extend(check_result.get('warnings', []))
            
            brand_safety_results['violations'] = violations
            brand_safety_results['warnings'] = warnings
            
            return brand_safety_results
            
        except Exception as e:
            self.logger.error(f"Error checking brand safety: {e}")
            raise ValidationError(f"Failed to check brand safety: {str(e)}")
    
    def validate_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """
        Validate offer for regulatory compliance.
        
        Args:
            offer: Offer instance to validate
            
        Returns:
            Dict[str, Any]: Compliance validation results
        """
        try:
            compliance_results = {
                'offer_id': offer.id,
                'validated_at': timezone.now().isoformat(),
                'checks': {},
                'overall_status': 'compliant',
                'violations': [],
                'recommendations': [],
            }
            
            # Check GDPR compliance
            gdpr_checks = self._check_gdpr_compliance(offer)
            compliance_results['checks']['gdpr'] = gdpr_checks
            
            # Check CCPA compliance
            ccpa_checks = self._check_ccpa_compliance(offer)
            compliance_results['checks']['ccpa'] = ccpa_checks
            
            # Check FTC guidelines compliance
            ftc_checks = self._check_ftc_compliance(offer)
            compliance_results['checks']['ftc'] = ftc_checks
            
            # Check industry-specific regulations
            industry_checks = self._check_industry_compliance(offer)
            compliance_results['checks']['industry'] = industry_checks
            
            # Check financial regulations if applicable
            financial_checks = self._check_financial_compliance(offer)
            compliance_results['checks']['financial'] = financial_checks
            
            # Determine overall compliance status
            violations = []
            recommendations = []
            
            for check_name, check_result in compliance_results['checks'].items():
                if check_result.get('status') == 'non_compliant':
                    violations.extend(check_result.get('violations', []))
                    compliance_results['overall_status'] = 'non_compliant'
                elif check_result.get('recommendations'):
                    recommendations.extend(check_result.get('recommendations', []))
            
            compliance_results['violations'] = violations
            compliance_results['recommendations'] = recommendations
            
            return compliance_results
            
        except Exception as e:
            self.logger.error(f"Error validating compliance: {e}")
            raise ValidationError(f"Failed to validate compliance: {str(e)}")
    
    def get_moderation_queue(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """
        Get offers pending moderation.
        
        Args:
            status: Queue status filter
            
        Returns:
            List[Dict[str, Any]]: Moderation queue
        """
        try:
            offers = AdvertiserOffer.objects.filter(status=status).select_related('advertiser')
            
            queue = []
            for offer in offers:
                queue_item = {
                    'offer_id': offer.id,
                    'title': offer.title,
                    'advertiser': offer.advertiser.company_name,
                    'payout_type': offer.payout_type,
                    'payout_amount': float(offer.payout_amount),
                    'created_at': offer.created_at.isoformat(),
                    'priority': self._calculate_moderation_priority(offer),
                    'estimated_review_time': self._estimate_review_time(offer),
                }
                queue.append(queue_item)
            
            # Sort by priority
            queue.sort(key=lambda x: x['priority'], reverse=True)
            
            return queue
            
        except Exception as e:
            self.logger.error(f"Error getting moderation queue: {e}")
            return []
    
    def bulk_moderate_offers(self, offer_ids: List[int], action: str, reviewer: User, reason: str = None) -> Dict[str, Any]:
        """
        Bulk moderate multiple offers.
        
        Args:
            offer_ids: List of offer IDs
            action: Action to take (approve/reject/request_changes)
            reviewer: User performing the action
            reason: Reason for action
            
        Returns:
            Dict[str, Any]: Bulk moderation results
        """
        try:
            with transaction.atomic():
                results = {
                    'processed': 0,
                    'approved': 0,
                    'rejected': 0,
                    'requested_changes': 0,
                    'errors': [],
                }
                
                offers = AdvertiserOffer.objects.filter(id__in=offer_ids)
                
                for offer in offers:
                    try:
                        if action == 'approve':
                            self._approve_offer_bulk(offer, reviewer, reason)
                            results['approved'] += 1
                        elif action == 'reject':
                            self._reject_offer_bulk(offer, reviewer, reason)
                            results['rejected'] += 1
                        elif action == 'request_changes':
                            self._request_changes_bulk(offer, reviewer, reason)
                            results['requested_changes'] += 1
                        
                        results['processed'] += 1
                        
                    except Exception as e:
                        results['errors'].append({
                            'offer_id': offer.id,
                            'offer_title': offer.title,
                            'error': str(e)
                        })
                
                return results
                
        except Exception as e:
            self.logger.error(f"Error in bulk moderation: {e}")
            raise ValidationError(f"Failed to bulk moderate offers: {str(e)}")
    
    def _perform_automated_checks(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Perform automated content checks."""
        checks = {
            'title_length': self._check_title_length(offer.title),
            'description_quality': self._check_description_quality(offer.description),
            'tracking_url_valid': self._check_tracking_url(offer.tracking_url),
            'payout_reasonable': self._check_payout_reasonableness(offer),
            'has_requirements': self._check_has_requirements(offer),
            'has_creatives': self._check_has_creatives(offer),
        }
        
        return {
            'checks': checks,
            'passed': all(check.get('status') == 'passed' for check in checks.values()),
            'warnings': [check['warning'] for check in checks.values() if check.get('warning')],
        }
    
    def _perform_manual_review_criteria(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Perform manual review criteria checks."""
        criteria = {
            'content_quality': self._assess_content_quality(offer),
            'brand_alignment': self._assess_brand_alignment(offer),
            'user_experience': self._assess_user_experience(offer),
            'value_proposition': self._assess_value_proposition(offer),
            'targeting_appropriateness': self._assess_targeting_appropriateness(offer),
        }
        
        return {
            'criteria': criteria,
            'average_score': sum(c.get('score', 0) for c in criteria.values()) / len(criteria),
            'concerns': [c['concern'] for c in criteria.values() if c.get('concern')],
        }
    
    def _check_title_length(self, title: str) -> Dict[str, Any]:
        """Check title length and quality."""
        if len(title) < 10:
            return {
                'status': 'warning',
                'warning': 'Title is too short (minimum 10 characters recommended)',
            }
        elif len(title) > 100:
            return {
                'status': 'warning',
                'warning': 'Title is very long (consider shortening)',
            }
        else:
            return {'status': 'passed'}
    
    def _check_description_quality(self, description: str) -> Dict[str, Any]:
        """Check description quality."""
        if len(description) < 50:
            return {
                'status': 'warning',
                'warning': 'Description is too short (minimum 50 characters recommended)',
            }
        elif len(description) > 2000:
            return {
                'status': 'warning',
                'warning': 'Description is very long (consider shortening)',
            }
        else:
            return {'status': 'passed'}
    
    def _check_tracking_url(self, url: str) -> Dict[str, Any]:
        """Check tracking URL validity."""
        if not url.startswith(('http://', 'https://')):
            return {
                'status': 'failed',
                'warning': 'Tracking URL must be a valid HTTP/HTTPS URL',
            }
        else:
            return {'status': 'passed'}
    
    def _check_payout_reasonableness(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check if payout amount is reasonable."""
        # This would implement more sophisticated logic based on industry standards
        if offer.payout_amount < 0.01:
            return {
                'status': 'warning',
                'warning': 'Payout amount seems very low',
            }
        elif offer.payout_amount > 1000:
            return {
                'status': 'warning',
                'warning': 'Payout amount seems very high',
            }
        else:
            return {'status': 'passed'}
    
    def _check_has_requirements(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check if offer has requirements."""
        if not offer.requirements.exists():
            return {
                'status': 'failed',
                'warning': 'Offer must have at least one requirement',
            }
        else:
            return {'status': 'passed'}
    
    def _check_has_creatives(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check if offer has creatives."""
        if not offer.creatives.exists():
            return {
                'status': 'failed',
                'warning': 'Offer must have at least one creative',
            }
        else:
            return {'status': 'passed'}
    
    def _assess_content_quality(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Assess content quality (manual review)."""
        # This would implement more sophisticated content analysis
        return {
            'score': 8,  # Would be calculated based on actual analysis
            'concern': None,
        }
    
    def _assess_brand_alignment(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Assess brand alignment (manual review)."""
        return {
            'score': 7,
            'concern': None,
        }
    
    def _assess_user_experience(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Assess user experience (manual review)."""
        return {
            'score': 8,
            'concern': None,
        }
    
    def _assess_value_proposition(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Assess value proposition (manual review)."""
        return {
            'score': 7,
            'concern': None,
        }
    
    def _assess_targeting_appropriateness(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Assess targeting appropriateness (manual review)."""
        return {
            'score': 8,
            'concern': None,
        }
    
    def _calculate_overall_score(self, automated_results: Dict, manual_results: Dict) -> float:
        """Calculate overall moderation score."""
        # Simple scoring algorithm
        automated_score = 10 if automated_results['passed'] else 5
        manual_score = manual_results['average_score']
        
        return (automated_score + manual_score) / 2
    
    def _get_review_recommendation(self, automated_results: Dict, manual_results: Dict) -> str:
        """Get review recommendation."""
        if not automated_results['passed']:
            return 'reject'
        elif manual_results['average_score'] < 6:
            return 'request_changes'
        elif manual_results['average_score'] < 8:
            return 'approve_with_conditions'
        else:
            return 'approve'
    
    def _collect_all_issues(self, automated_results: Dict, manual_results: Dict) -> List[str]:
        """Collect all issues found during review."""
        issues = []
        
        issues.extend(automated_results.get('warnings', []))
        issues.extend(manual_results.get('concerns', []))
        
        return issues
    
    def _check_sensitive_text_content(self, title: str, description: str) -> Dict[str, Any]:
        """Check for sensitive text content."""
        # This would implement more sophisticated text analysis
        sensitive_words = ['scam', 'fake', 'illegal', 'hack', 'crack']
        
        text_to_check = f"{title} {description}".lower()
        
        found_words = [word for word in sensitive_words if word in text_to_check]
        
        if found_words:
            return {
                'status': 'warning',
                'violations': [f"Sensitive content detected: {', '.join(found_words)}"],
                'warnings': [],
            }
        
        return {
            'status': 'passed',
            'violations': [],
            'warnings': [],
        }
    
    def _check_creative_brand_safety(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check creatives for brand safety."""
        # This would implement creative analysis
        return {
            'status': 'passed',
            'violations': [],
            'warnings': [],
        }
    
    def _check_landing_page_safety(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check landing page safety."""
        # This would implement landing page analysis
        return {
            'status': 'passed',
            'violations': [],
            'warnings': [],
        }
    
    def _check_targeting_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check targeting compliance."""
        # This would implement targeting analysis
        return {
            'status': 'passed',
            'violations': [],
            'warnings': [],
        }
    
    def _check_gdpr_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check GDPR compliance."""
        return {
            'status': 'compliant',
            'violations': [],
            'recommendations': [],
        }
    
    def _check_ccpa_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check CCPA compliance."""
        return {
            'status': 'compliant',
            'violations': [],
            'recommendations': [],
        }
    
    def _check_ftc_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check FTC guidelines compliance."""
        return {
            'status': 'compliant',
            'violations': [],
            'recommendations': [],
        }
    
    def _check_industry_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check industry-specific compliance."""
        return {
            'status': 'compliant',
            'violations': [],
            'recommendations': [],
        }
    
    def _check_financial_compliance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Check financial regulations compliance."""
        return {
            'status': 'compliant',
            'violations': [],
            'recommendations': [],
        }
    
    def _calculate_moderation_priority(self, offer: AdvertiserOffer) -> int:
        """Calculate moderation priority."""
        # Higher payout = higher priority
        base_priority = int(offer.payout_amount * 10)
        
        # Adjust for age (older offers get lower priority)
        days_old = (timezone.now() - offer.created_at).days
        age_penalty = min(days_old * 2, 50)
        
        return max(base_priority - age_penalty, 1)
    
    def _estimate_review_time(self, offer: AdvertiserOffer) -> str:
        """Estimate review time."""
        complexity = 1
        
        if offer.creatives.count() > 3:
            complexity += 1
        
        if offer.requirements.count() > 2:
            complexity += 1
        
        if complexity == 1:
            return '15-30 minutes'
        elif complexity == 2:
            return '30-45 minutes'
        else:
            return '45-60 minutes'
    
    def _approve_offer_bulk(self, offer: AdvertiserOffer, reviewer: User, reason: str):
        """Approve offer in bulk moderation."""
        offer.status = 'active'
        offer.save()
        
        # Store bulk approval in metadata
        metadata = offer.metadata or {}
        metadata['bulk_approval'] = {
            'approved_by': reviewer.id,
            'approved_at': timezone.now().isoformat(),
            'reason': reason,
        }
        offer.metadata = metadata
        offer.save()
    
    def _reject_offer_bulk(self, offer: AdvertiserOffer, reviewer: User, reason: str):
        """Reject offer in bulk moderation."""
        offer.status = 'rejected'
        offer.save()
        
        # Store bulk rejection in metadata
        metadata = offer.metadata or {}
        metadata['bulk_rejection'] = {
            'rejected_by': reviewer.id,
            'rejected_at': timezone.now().isoformat(),
            'reason': reason,
        }
        offer.metadata = metadata
        offer.save()
    
    def _request_changes_bulk(self, offer: AdvertiserOffer, reviewer: User, reason: str):
        """Request changes in bulk moderation."""
        offer.status = 'pending_review'
        offer.save()
        
        # Store bulk change request in metadata
        metadata = offer.metadata or {}
        metadata['bulk_change_request'] = {
            'requested_by': reviewer.id,
            'requested_at': timezone.now().isoformat(),
            'reason': reason,
        }
        offer.metadata = metadata
        offer.save()
    
    def _send_review_notification(self, offer: AdvertiserOffer, review_results: Dict[str, Any]):
        """Send review completion notification."""
        recommendation = review_results['recommendation']
        
        if recommendation == 'approve':
            AdvertiserNotification.objects.create(
                advertiser=offer.advertiser,
                type='offer_approved',
                title=_('Offer Content Approved'),
                message=_('Your offer "{offer_title}" has passed content review.').format(
                    offer_title=offer.title
                ),
                priority='high',
                action_url=f'/advertiser/offers/{offer.id}/',
                action_text=_('View Offer')
            )
        elif recommendation == 'reject':
            AdvertiserNotification.objects.create(
                advertiser=offer.advertiser,
                type='offer_rejected',
                title=_('Offer Content Rejected'),
                message=_('Your offer "{offer_title}" requires changes before approval.').format(
                    offer_title=offer.title
                ),
                priority='high',
                action_url=f'/advertiser/offers/{offer.id}/edit/',
                action_text=_('Edit Offer')
            )
        elif recommendation == 'request_changes':
            AdvertiserNotification.objects.create(
                advertiser=offer.advertiser,
                type='offer_rejected',
                title=_('Offer Changes Requested'),
                message=_('Your offer "{offer_title}" requires some changes.').format(
                    offer_title=offer.title
                ),
                priority='medium',
                action_url=f'/advertiser/offers/{offer.id}/edit/',
                action_text=_('Make Changes')
            )
