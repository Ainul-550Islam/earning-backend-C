"""
Advertiser Onboarding Service

Service for managing advertiser onboarding process,
including setup wizard and checklist management.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.advertiser import Advertiser, AdvertiserProfile
from ...models.offer import AdvertiserOffer
from ...models.campaign import AdCampaign
from ...models.billing import AdvertiserWallet
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserOnboardingService:
    """
    Service for managing advertiser onboarding process.
    
    Handles setup wizard, checklist management,
    and guided onboarding workflows.
    """
    
    def __init__(self):
        self.logger = logger
    
    def start_onboarding(self, advertiser: Advertiser) -> Dict[str, Any]:
        """
        Start onboarding process for advertiser.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Onboarding checklist and steps
        """
        try:
            # Initialize onboarding checklist
            checklist = self._generate_onboarding_checklist(advertiser)
            
            # Create wallet if not exists
            self._ensure_wallet_exists(advertiser)
            
            # Send welcome notification with onboarding guide
            self._send_onboarding_welcome_notification(advertiser)
            
            self.logger.info(f"Started onboarding for: {advertiser.company_name}")
            
            return {
                'checklist': checklist,
                'current_step': self._get_current_step(advertiser),
                'progress': self._calculate_progress(advertiser),
                'estimated_time': '15-30 minutes',
            }
            
        except Exception as e:
            self.logger.error(f"Error starting onboarding: {e}")
            raise ValidationError(f"Failed to start onboarding: {str(e)}")
    
    def complete_onboarding_step(self, advertiser: Advertiser, step_id: str, 
                               data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Complete an onboarding step.
        
        Args:
            advertiser: Advertiser instance
            step_id: Step identifier
            data: Step completion data
            
        Returns:
            Dict[str, Any]: Updated onboarding status
        """
        try:
            with transaction.atomic():
                # Process step completion
                result = self._process_step_completion(advertiser, step_id, data)
                
                # Update onboarding progress
                progress = self._calculate_progress(advertiser)
                
                # Check if onboarding is complete
                if progress['percentage'] >= 100:
                    self._complete_onboarding(advertiser)
                
                # Send progress notification
                self._send_progress_notification(advertiser, step_id, progress)
                
                self.logger.info(f"Completed onboarding step: {advertiser.company_name} - {step_id}")
                
                return {
                    'step_completed': step_id,
                    'progress': progress,
                    'next_step': self._get_next_step(advertiser),
                    'is_complete': progress['percentage'] >= 100,
                }
                
        except Exception as e:
            self.logger.error(f"Error completing onboarding step: {e}")
            raise ValidationError(f"Failed to complete onboarding step: {str(e)}")
    
    def skip_onboarding_step(self, advertiser: Advertiser, step_id: str, 
                           reason: str = None) -> Dict[str, Any]:
        """
        Skip an onboarding step.
        
        Args:
            advertiser: Advertiser instance
            step_id: Step identifier
            reason: Reason for skipping
            
        Returns:
            Dict[str, Any]: Updated onboarding status
        """
        try:
            with transaction.atomic():
                # Mark step as skipped
                self._mark_step_skipped(advertiser, step_id, reason)
                
                # Update progress
                progress = self._calculate_progress(advertiser)
                
                # Send notification about skipped step
                self._send_step_skipped_notification(advertiser, step_id, reason)
                
                self.logger.info(f"Skipped onboarding step: {advertiser.company_name} - {step_id}")
                
                return {
                    'step_skipped': step_id,
                    'progress': progress,
                    'next_step': self._get_next_step(advertiser),
                }
                
        except Exception as e:
            self.logger.error(f"Error skipping onboarding step: {e}")
            raise ValidationError(f"Failed to skip onboarding step: {str(e)}")
    
    def get_onboarding_status(self, advertiser: Advertiser) -> Dict[str, Any]:
        """
        Get current onboarding status.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Onboarding status
        """
        try:
            checklist = self._generate_onboarding_checklist(advertiser)
            progress = self._calculate_progress(advertiser)
            current_step = self._get_current_step(advertiser)
            
            return {
                'checklist': checklist,
                'progress': progress,
                'current_step': current_step,
                'is_complete': progress['percentage'] >= 100,
                'started_at': advertiser.created_at.isoformat(),
                'estimated_completion': self._estimate_completion_time(advertiser),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting onboarding status: {e}")
            raise ValidationError(f"Failed to get onboarding status: {str(e)}")
    
    def reset_onboarding(self, advertiser: Advertiser) -> Dict[str, Any]:
        """
        Reset onboarding process.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Reset onboarding status
        """
        try:
            with transaction.atomic():
                # Clear onboarding metadata
                if advertiser.profile:
                    advertiser.profile.metadata = {}
                    advertiser.profile.save()
                
                # Restart onboarding
                return self.start_onboarding(advertiser)
                
        except Exception as e:
            self.logger.error(f"Error resetting onboarding: {e}")
            raise ValidationError(f"Failed to reset onboarding: {str(e)}")
    
    def get_onboarding_tips(self, advertiser: Advertiser, step_id: str = None) -> List[Dict[str, Any]]:
        """
        Get onboarding tips and guidance.
        
        Args:
            advertiser: Advertiser instance
            step_id: Optional specific step
            
        Returns:
            List[Dict[str, Any]]: Onboarding tips
        """
        tips = []
        
        if step_id is None or step_id == 'profile_completion':
            tips.extend([
                {
                    'title': _('Complete Your Profile'),
                    'description': _('Add detailed information about your business to help us serve you better.'),
                    'action_text': _('Update Profile'),
                    'action_url': '/advertiser/profile/',
                },
                {
                    'title': _('Upload Your Logo'),
                    'description': _('Add your company logo to personalize your campaigns and offers.'),
                    'action_text': _('Upload Logo'),
                    'action_url': '/advertiser/profile/logo/',
                }
            ])
        
        if step_id is None or step_id == 'payment_setup':
            tips.extend([
                {
                    'title': _('Set Up Payment Method'),
                    'description': _('Add a payment method to fund your campaigns and start advertising.'),
                    'action_text': _('Add Payment Method'),
                    'action_url': '/advertiser/billing/payment-methods/',
                },
                {
                    'title': _('Set Up Auto-Refill'),
                    'description': _('Enable auto-refill to ensure your campaigns never run out of funds.'),
                    'action_text': _('Configure Auto-Refill'),
                    'action_url': '/advertiser/billing/auto-refill/',
                }
            ])
        
        if step_id is None or step_id == 'first_campaign':
            tips.extend([
                {
                    'title': _('Create Your First Campaign'),
                    'description': _('Start with a simple campaign to understand the platform.'),
                    'action_text': _('Create Campaign'),
                    'action_url': '/advertiser/campaigns/create/',
                },
                {
                    'title': _('Set Your Budget'),
                    'description': _('Define daily and total budgets to control your spending.'),
                    'action_text': _('Set Budget'),
                    'action_url': '/advertiser/campaigns/budget/',
                }
            ])
        
        if step_id is None or step_id == 'first_offer':
            tips.extend([
                {
                    'title': _('Create Your First Offer'),
                    'description': _('Define what you want to promote and how you\'ll pay for results.'),
                    'action_text': _('Create Offer'),
                    'action_url': '/advertiser/offers/create/',
                },
                {
                    'title': _('Set Up Tracking'),
                    'description': _('Add tracking pixels to measure your campaign performance.'),
                    'action_text': _('Set Up Tracking'),
                    'action_url': '/advertiser/tracking/pixels/',
                }
            ])
        
        return tips
    
    def _generate_onboarding_checklist(self, advertiser: Advertiser) -> List[Dict[str, Any]]:
        """Generate onboarding checklist for advertiser."""
        checklist = [
            {
                'id': 'profile_completion',
                'title': _('Complete Your Profile'),
                'description': _('Add your business information and contact details'),
                'required': True,
                'status': self._get_step_status(advertiser, 'profile_completion'),
                'estimated_time': '5 minutes',
                'category': 'setup',
            },
            {
                'id': 'payment_setup',
                'title': _('Set Up Payment Method'),
                'description': _('Add a payment method to fund your campaigns'),
                'required': True,
                'status': self._get_step_status(advertiser, 'payment_setup'),
                'estimated_time': '3 minutes',
                'category': 'billing',
            },
            {
                'id': 'verification_documents',
                'title': _('Submit Verification Documents'),
                'description': _('Upload required documents for account verification'),
                'required': True,
                'status': self._get_step_status(advertiser, 'verification_documents'),
                'estimated_time': '10 minutes',
                'category': 'verification',
            },
            {
                'id': 'first_campaign',
                'title': _('Create Your First Campaign'),
                'description': _('Set up your first advertising campaign'),
                'required': False,
                'status': self._get_step_status(advertiser, 'first_campaign'),
                'estimated_time': '5 minutes',
                'category': 'campaigns',
            },
            {
                'id': 'first_offer',
                'title': _('Create Your First Offer'),
                'description': _('Define your first offer and tracking setup'),
                'required': False,
                'status': self._get_step_status(advertiser, 'first_offer'),
                'estimated_time': '5 minutes',
                'category': 'offers',
            },
            {
                'id': 'tracking_setup',
                'title': _('Set Up Tracking Pixels'),
                'description': _('Add tracking pixels to measure performance'),
                'required': False,
                'status': self._get_step_status(advertiser, 'tracking_setup'),
                'estimated_time': '3 minutes',
                'category': 'tracking',
            },
        ]
        
        return checklist
    
    def _get_step_status(self, advertiser: Advertiser, step_id: str) -> str:
        """Get status of a specific onboarding step."""
        metadata = advertiser.profile.metadata if advertiser.profile else {}
        onboarding_progress = metadata.get('onboarding_progress', {})
        
        return onboarding_progress.get(step_id, 'pending')
    
    def _process_step_completion(self, advertiser: Advertiser, step_id: str, data: Dict[str, Any] = None):
        """Process completion of an onboarding step."""
        metadata = advertiser.profile.metadata if advertiser.profile else {}
        onboarding_progress = metadata.get('onboarding_progress', {})
        
        # Mark step as completed
        onboarding_progress[step_id] = 'completed'
        
        # Store completion data
        if data:
            onboarding_progress[f'{step_id}_data'] = data
            onboarding_progress[f'{step_id}_completed_at'] = timezone.now().isoformat()
        
        # Update metadata
        metadata['onboarding_progress'] = onboarding_progress
        advertiser.profile.metadata = metadata
        advertiser.profile.save()
        
        return True
    
    def _mark_step_skipped(self, advertiser: Advertiser, step_id: str, reason: str = None):
        """Mark an onboarding step as skipped."""
        metadata = advertiser.profile.metadata if advertiser.profile else {}
        onboarding_progress = metadata.get('onboarding_progress', {})
        
        onboarding_progress[step_id] = 'skipped'
        if reason:
            onboarding_progress[f'{step_id}_skip_reason'] = reason
        onboarding_progress[f'{step_id}_skipped_at'] = timezone.now().isoformat()
        
        metadata['onboarding_progress'] = onboarding_progress
        advertiser.profile.metadata = metadata
        advertiser.profile.save()
    
    def _calculate_progress(self, advertiser: Advertiser) -> Dict[str, Any]:
        """Calculate onboarding progress."""
        checklist = self._generate_onboarding_checklist(advertiser)
        
        completed_steps = 0
        total_steps = len(checklist)
        required_completed = 0
        required_total = 0
        
        for step in checklist:
            status = step['status']
            if status == 'completed':
                completed_steps += 1
                if step['required']:
                    required_completed += 1
            elif status == 'skipped':
                if step['required']:
                    # Skipped required steps don't count toward completion
                    pass
                else:
                    completed_steps += 1
            
            if step['required']:
                required_total += 1
        
        percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        required_percentage = (required_completed / required_total * 100) if required_total > 0 else 0
        
        return {
            'percentage': round(percentage, 2),
            'required_percentage': round(required_percentage, 2),
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'required_completed': required_completed,
            'required_total': required_total,
        }
    
    def _get_current_step(self, advertiser: Advertiser) -> Optional[Dict[str, Any]]:
        """Get current onboarding step."""
        checklist = self._generate_onboarding_checklist(advertiser)
        
        for step in checklist:
            if step['status'] == 'pending':
                return step
        
        return None
    
    def _get_next_step(self, advertiser: Advertiser) -> Optional[Dict[str, Any]]:
        """Get next onboarding step."""
        checklist = self._generate_onboarding_checklist(advertiser)
        
        for step in checklist:
            if step['status'] in ['pending', 'skipped']:
                return step
        
        return None
    
    def _ensure_wallet_exists(self, advertiser: Advertiser):
        """Ensure advertiser has a wallet."""
        if not hasattr(advertiser, 'wallet'):
            AdvertiserWallet.objects.create(advertiser=advertiser)
    
    def _complete_onboarding(self, advertiser: Advertiser):
        """Complete onboarding process."""
        # Send completion notification
        self._send_onboarding_complete_notification(advertiser)
        
        # Update metadata
        metadata = advertiser.profile.metadata if advertiser.profile else {}
        metadata['onboarding_completed_at'] = timezone.now().isoformat()
        metadata['onboarding_complete'] = True
        advertiser.profile.metadata = metadata
        advertiser.profile.save()
    
    def _estimate_completion_time(self, advertiser: Advertiser) -> str:
        """Estimate time to complete onboarding."""
        progress = self._calculate_progress(advertiser)
        remaining_percentage = 100 - progress['percentage']
        
        if remaining_percentage <= 20:
            return 'Less than 5 minutes'
        elif remaining_percentage <= 50:
            return '5-10 minutes'
        elif remaining_percentage <= 80:
            return '10-20 minutes'
        else:
            return '20-30 minutes'
    
    def _send_onboarding_welcome_notification(self, advertiser: Advertiser):
        """Send welcome notification with onboarding guide."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='welcome',
            title=_('Welcome! Let\'s Get You Set Up'),
            message=_(
                'Welcome to our Advertiser Portal! Let\'s complete your setup '
                'so you can start running successful campaigns. This should only take 15-30 minutes.'
            ),
            priority='high',
            action_url='/advertiser/onboarding/',
            action_text=_('Start Setup')
        )
    
    def _send_progress_notification(self, advertiser: Advertiser, step_id: str, progress: Dict[str, Any]):
        """Send progress notification."""
        if progress['percentage'] >= 100:
            return  # Will send completion notification separately
        
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='welcome',
            title=_('Great Progress!'),
            message=_(
                'You\'ve completed {percentage}% of your setup. '
                'Keep going to get your campaigns running!'
            ).format(percentage=round(progress['percentage'])),
            priority='medium',
            action_url='/advertiser/onboarding/',
            action_text=_('Continue Setup')
        )
    
    def _send_onboarding_complete_notification(self, advertiser: Advertiser):
        """Send onboarding completion notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='welcome',
            title=_('Setup Complete!'),
            message=_(
                'Congratulations! Your account setup is complete. '
                'You\'re now ready to create campaigns and start advertising.'
            ),
            priority='high',
            action_url='/advertiser/dashboard/',
            action_text=_('Go to Dashboard')
        )
    
    def _send_step_skipped_notification(self, advertiser: Advertiser, step_id: str, reason: str):
        """Send notification when step is skipped."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='welcome',
            title=_('Step Skipped'),
            message=_(
                'You\'ve skipped the onboarding step. '
                'You can always complete this later from your profile settings.'
            ),
            priority='low'
        )
