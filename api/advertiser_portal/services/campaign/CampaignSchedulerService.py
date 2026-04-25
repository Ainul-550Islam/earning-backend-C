"""
Campaign Scheduler Service

Service for time-based campaign activation,
including scheduling and automated campaign management.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from ...models.campaign import AdCampaign, CampaignSchedule
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class CampaignSchedulerService:
    """
    Service for time-based campaign scheduling.
    
    Handles campaign activation, pausing,
    and schedule-based management.
    """
    
    def __init__(self):
        self.logger = logger
    
    def schedule_campaign(self, campaign: AdCampaign, schedule_data: Dict[str, Any]) -> CampaignSchedule:
        """
        Create campaign schedule.
        
        Args:
            campaign: Campaign instance
            schedule_data: Schedule configuration
            
        Returns:
            CampaignSchedule: Created schedule instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate schedule data
                self._validate_schedule_data(schedule_data)
                
                # Create or update schedule
                schedule, created = CampaignSchedule.objects.get_or_create(
                    campaign=campaign,
                    defaults={
                        'hours': schedule_data.get('hours', {}),
                        'timezone': schedule_data.get('timezone', 'UTC'),
                        'custom_rules': schedule_data.get('custom_rules', {}),
                    }
                )
                
                if not created:
                    schedule.hours = schedule_data.get('hours', {})
                    schedule.timezone = schedule_data.get('timezone', 'UTC')
                    schedule.custom_rules = schedule_data.get('custom_rules', {})
                    schedule.save()
                
                # Send notification
                if created:
                    self._send_schedule_created_notification(campaign, schedule)
                
                self.logger.info(f"Created schedule for campaign: {campaign.name}")
                return schedule
                
        except Exception as e:
            self.logger.error(f"Error creating campaign schedule: {e}")
            raise ValidationError(f"Failed to create schedule: {str(e)}")
    
    def check_and_activate_scheduled_campaigns(self) -> Dict[str, Any]:
        """
        Check and activate campaigns scheduled to start.
        
        Returns:
            Dict[str, Any]: Activation results
        """
        try:
            now = timezone.now()
            activated_count = 0
            skipped_count = 0
            errors = []
            
            # Find campaigns that should start now
            campaigns_to_start = AdCampaign.objects.filter(
                status='draft',
                start_date__lte=now.date(),
                start_date__gte=now.date() - timezone.timedelta(days=1)  # Within last day
            ).select_related('advertiser', 'schedule')
            
            for campaign in campaigns_to_start:
                try:
                    if self._should_activate_campaign_now(campaign, now):
                        self._activate_campaign(campaign)
                        activated_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns_to_start.count(),
                'activated_count': activated_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking scheduled campaigns: {e}")
            raise ValidationError(f"Failed to check scheduled campaigns: {str(e)}")
    
    def check_and_pause_scheduled_campaigns(self) -> Dict[str, Any]:
        """
        Check and pause campaigns scheduled to end.
        
        Returns:
            Dict[str, Any]: Pause results
        """
        try:
            now = timezone.now()
            paused_count = 0
            skipped_count = 0
            errors = []
            
            # Find campaigns that should end now
            campaigns_to_end = AdCampaign.objects.filter(
                status='active',
                end_date__lte=now.date()
            ).select_related('advertiser')
            
            for campaign in campaigns_to_end:
                try:
                    self._end_campaign(campaign, 'Scheduled end date reached')
                    paused_count += 1
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns_to_end.count(),
                'paused_count': paused_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking campaign endings: {e}")
            raise ValidationError(f"Failed to check campaign endings: {str(e)}")
    
    def check_hourly_schedules(self) -> Dict[str, Any]:
        """
        Check and apply hourly schedule rules.
        
        Returns:
            Dict[str, Any]: Schedule application results
        """
        try:
            now = timezone.now()
            current_hour = now.hour
            current_day = now.strftime('%A').lower()
            
            campaigns_with_schedules = AdCampaign.objects.filter(
                status='active',
                schedule__isnull=False
            ).select_related('advertiser', 'schedule')
            
            paused_count = 0
            resumed_count = 0
            errors = []
            
            for campaign in campaigns_with_schedules:
                try:
                    schedule = campaign.schedule
                    
                    # Check if campaign should be paused for this hour
                    if self._should_pause_for_hour(schedule, current_day, current_hour):
                        if campaign.status == 'active':
                            self._pause_campaign(campaign, 'Scheduled pause')
                            paused_count += 1
                    
                    # Check if campaign should be resumed for this hour
                    elif self._should_resume_for_hour(schedule, current_day, current_hour):
                        if campaign.status == 'paused':
                            self._resume_campaign(campaign, 'Scheduled resume')
                            resumed_count += 1
                
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns_with_schedules.count(),
                'paused_count': paused_count,
                'resumed_count': resumed_count,
                'errors': errors,
                'timestamp': now.isoformat(),
                'current_hour': current_hour,
                'current_day': current_day,
            }
            
        except Exception as e:
            self.logger.error(f"Error checking hourly schedules: {e}")
            raise ValidationError(f"Failed to check hourly schedules: {str(e)}")
    
    def get_campaign_schedule_status(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Get current schedule status for campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Schedule status
        """
        try:
            schedule = getattr(campaign, 'schedule', None)
            
            if not schedule:
                return {
                    'has_schedule': False,
                    'status': 'no_schedule',
                    'current_action': 'none',
                    'next_action': None,
                }
            
            now = timezone.now()
            current_day = now.strftime('%A').lower()
            current_hour = now.hour
            
            # Check current status
            if campaign.status == 'active':
                current_action = 'running'
            elif campaign.status == 'paused':
                current_action = 'paused'
            else:
                current_action = campaign.status
            
            # Check next scheduled action
            next_action = self._get_next_scheduled_action(schedule, current_day, current_hour)
            
            return {
                'has_schedule': True,
                'schedule': {
                    'hours': schedule.hours,
                    'timezone': schedule.timezone,
                    'custom_rules': schedule.custom_rules,
                },
                'current_status': {
                    'day': current_day,
                    'hour': current_hour,
                    'action': current_action,
                },
                'next_action': next_action,
                'is_scheduled_to_run': self._should_be_running_now(schedule, current_day, current_hour),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting campaign schedule status: {e}")
            raise ValidationError(f"Failed to get schedule status: {str(e)}")
    
    def create_schedule_template(self, template_type: str) -> Dict[str, Any]:
        """
        Create schedule template.
        
        Args:
            template_type: Type of schedule template
            
        Returns:
            Dict[str, Any]: Schedule template
        """
        templates = {
            'business_hours': {
                'hours': {
                    'monday': list(range(9, 18)),  # 9 AM to 6 PM
                    'tuesday': list(range(9, 18)),
                    'wednesday': list(range(9, 18)),
                    'thursday': list(range(9, 18)),
                    'friday': list(range(9, 18)),
                    'saturday': [],
                    'sunday': [],
                },
                'timezone': 'UTC',
                'custom_rules': {},
            },
            '24_7': {
                'hours': {
                    'monday': list(range(24)),
                    'tuesday': list(range(24)),
                    'wednesday': list(range(24)),
                    'thursday': list(range(24)),
                    'friday': list(range(24)),
                    'saturday': list(range(24)),
                    'sunday': list(range(24)),
                },
                'timezone': 'UTC',
                'custom_rules': {},
            },
            'weekends_only': {
                'hours': {
                    'monday': [],
                    'tuesday': [],
                    'wednesday': [],
                    'thursday': [],
                    'friday': [],
                    'saturday': list(range(24)),
                    'sunday': list(range(24)),
                },
                'timezone': 'UTC',
                'custom_rules': {},
            },
            'peak_hours': {
                'hours': {
                    'monday': [8, 9, 10, 11, 12, 17, 18, 19, 20],
                    'tuesday': [8, 9, 10, 11, 12, 17, 18, 19, 20],
                    'wednesday': [8, 9, 10, 11, 12, 17, 18, 19, 20],
                    'thursday': [8, 9, 10, 11, 12, 17, 18, 19, 20],
                    'friday': [8, 9, 10, 11, 12, 17, 18, 19, 20],
                    'saturday': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                    'sunday': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                },
                'timezone': 'UTC',
                'custom_rules': {},
            },
        }
        
        return templates.get(template_type, templates['business_hours'])
    
    def validate_schedule_conflicts(self, campaign: AdCampaign, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate schedule for conflicts.
        
        Args:
            campaign: Campaign instance
            schedule_data: Schedule data to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            conflicts = []
            warnings = []
            
            # Check if schedule has any running hours
            hours = schedule_data.get('hours', {})
            total_hours = sum(len(day_hours) for day_hours in hours.values())
            
            if total_hours == 0:
                warnings.append("Schedule has no running hours - campaign will never run")
            
            # Check timezone compatibility
            schedule_timezone = schedule_data.get('timezone', 'UTC')
            if schedule_timezone != 'UTC':
                warnings.append(f"Non-UTC timezone ({schedule_timezone}) may cause confusion")
            
            # Check for very restrictive schedules
            if total_hours < 10:
                warnings.append("Very restrictive schedule - may limit campaign performance")
            
            # Check campaign date compatibility
            now = timezone.now()
            if campaign.start_date and campaign.start_date > now.date():
                conflicts.append("Campaign start date is in the future")
            
            if campaign.end_date and campaign.end_date < now.date():
                conflicts.append("Campaign end date is in the past")
            
            return {
                'is_valid': len(conflicts) == 0,
                'conflicts': conflicts,
                'warnings': warnings,
                'total_hours': total_hours,
                'days_with_hours': len([day for day, hours in hours.items() if hours]),
            }
            
        except Exception as e:
            self.logger.error(f"Error validating schedule conflicts: {e}")
            raise ValidationError(f"Failed to validate schedule: {str(e)}")
    
    def _validate_schedule_data(self, schedule_data: Dict[str, Any]):
        """Validate schedule data."""
        if not isinstance(schedule_data.get('hours', {}), dict):
            raise ValidationError("Hours must be a dictionary")
        
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        hours = schedule_data.get('hours', {})
        
        for day, day_hours in hours.items():
            if day not in valid_days:
                raise ValidationError(f"Invalid day: {day}")
            
            if not isinstance(day_hours, list):
                raise ValidationError(f"Hours for {day} must be a list")
            
            for hour in day_hours:
                if not isinstance(hour, int) or hour < 0 or hour > 23:
                    raise ValidationError(f"Invalid hour: {hour} for {day}")
    
    def _should_activate_campaign_now(self, campaign: AdCampaign, now: timezone.datetime) -> bool:
        """Check if campaign should be activated now."""
        # Check start date
        if campaign.start_date and now.date() >= campaign.start_date:
            # Check if within scheduled hours
            schedule = getattr(campaign, 'schedule', None)
            if not schedule:
                return True  # No schedule restrictions
            
            current_day = now.strftime('%A').lower()
            current_hour = now.hour
            
            return self._should_be_running_now(schedule, current_day, current_hour)
        
        return False
    
    def _should_be_running_now(self, schedule: CampaignSchedule, current_day: str, current_hour: int) -> bool:
        """Check if campaign should be running based on schedule."""
        hours = schedule.hours.get(current_day, [])
        return current_hour in hours
    
    def _should_pause_for_hour(self, schedule: CampaignSchedule, current_day: str, current_hour: int) -> bool:
        """Check if campaign should be paused for current hour."""
        return not self._should_be_running_now(schedule, current_day, current_hour)
    
    def _should_resume_for_hour(self, schedule: CampaignSchedule, current_day: str, current_hour: int) -> bool:
        """Check if campaign should be resumed for current hour."""
        return self._should_be_running_now(schedule, current_day, current_hour)
    
    def _get_next_scheduled_action(self, schedule: CampaignSchedule, current_day: str, current_hour: int) -> Optional[Dict[str, Any]]:
        """Get next scheduled action."""
        # This would implement logic to find next pause/resume time
        # For now, return None
        return None
    
    def _activate_campaign(self, campaign: AdCampaign):
        """Activate campaign."""
        campaign.status = 'active'
        campaign.actual_start_date = timezone.now()
        campaign.save()
        
        self._send_campaign_activated_notification(campaign)
        self.logger.info(f"Activated scheduled campaign: {campaign.name}")
    
    def _pause_campaign(self, campaign: AdCampaign, reason: str):
        """Pause campaign."""
        campaign.status = 'paused'
        campaign.notes = f"{reason}\n{campaign.notes or ''}"
        campaign.save()
        
        self._send_campaign_paused_notification(campaign, reason)
        self.logger.info(f"Paused scheduled campaign: {campaign.name}")
    
    def _resume_campaign(self, campaign: AdCampaign, reason: str):
        """Resume campaign."""
        campaign.status = 'active'
        campaign.notes = f"{reason}\n{campaign.notes or ''}"
        campaign.save()
        
        self._send_campaign_resumed_notification(campaign, reason)
        self.logger.info(f"Resumed scheduled campaign: {campaign.name}")
    
    def _end_campaign(self, campaign: AdCampaign, reason: str):
        """End campaign."""
        campaign.status = 'ended'
        campaign.actual_end_date = timezone.now()
        campaign.notes = f"{reason}\n{campaign.notes or ''}"
        campaign.save()
        
        self._send_campaign_ended_notification(campaign, reason)
        self.logger.info(f"Ended scheduled campaign: {campaign.name}")
    
    def _send_schedule_created_notification(self, campaign: AdCampaign, schedule: CampaignSchedule):
        """Send schedule created notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_started',
            title=_('Campaign Schedule Created'),
            message=_('Your campaign "{campaign_name}" has been scheduled with custom hours.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/schedule/',
            action_text=_('View Schedule')
        )
    
    def _send_campaign_activated_notification(self, campaign: AdCampaign):
        """Send campaign activated notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_started',
            title=_('Campaign Automatically Started'),
            message=_('Your campaign "{campaign_name}" has been automatically started according to schedule.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
    
    def _send_campaign_paused_notification(self, campaign: AdCampaign, reason: str):
        """Send campaign paused notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_paused',
            title=_('Campaign Automatically Paused'),
            message=_('Your campaign "{campaign_name}" has been automatically paused: {reason}').format(
                campaign_name=campaign.name,
                reason=reason
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
    
    def _send_campaign_resumed_notification(self, campaign: AdCampaign, reason: str):
        """Send campaign resumed notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_started',
            title=_('Campaign Automatically Resumed'),
            message=_('Your campaign "{campaign_name}" has been automatically resumed: {reason}').format(
                campaign_name=campaign.name,
                reason=reason
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
    
    def _send_campaign_ended_notification(self, campaign: AdCampaign, reason: str):
        """Send campaign ended notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_ended',
            title=_('Campaign Automatically Ended'),
            message=_('Your campaign "{campaign_name}" has been automatically ended: {reason}').format(
                campaign_name=campaign.name,
                reason=reason
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/report/',
            action_text=_('View Report')
        )
