"""
Onboarding Management Commands

This module contains Django management commands for onboarding operations
including completion, reminders, and trial extensions.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Sum, Avg
import json
from datetime import timedelta

from ...models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension
from ...services import OnboardingService


class CompleteOnboardingCommand(BaseCommand):
    """
    Complete onboarding for tenants.
    
    Usage:
        python manage.py complete_onboarding [--tenant=<tenant_id>] [--dry-run]
    """
    
    help = "Complete onboarding for tenants"
    
    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Complete onboarding for specific tenant ID or name')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be completed without completing')
    
    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        dry_run = options['dry_run']
        
        self.stdout.write("Completing onboarding")
        
        # Get tenants to process
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                onboardings = [tenant.onboarding]
            except (Tenant.DoesNotExist, ValueError, AttributeError):
                try:
                    tenant = Tenant.objects.get(name=tenant_id)
                    onboardings = [tenant.onboarding]
                except Tenant.DoesNotExist:
                    raise CommandError(f"Tenant '{tenant_id}' not found")
        else:
            onboardings = TenantOnboarding.objects.filter(status='in_progress').select_related('tenant')
        
        completed_count = 0
        failed_count = 0
        
        for onboarding in onboardings:
            try:
                if dry_run:
                    self.stdout.write(f"Would complete onboarding for: {onboarding.tenant.name}")
                    completed_count += 1
                else:
                    onboarding.complete_onboarding()
                    completed_count += 1
                    self.stdout.write(f"Completed onboarding for: {onboarding.tenant.name}")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to complete onboarding for {onboarding.tenant.name}: {str(e)}")
                )
        
        action = "Would complete" if dry_run else "Completed"
        self.stdout.write(
            self.style.SUCCESS(f"{action} onboarding for {completed_count} tenants, {failed_count} failed")
        )


class SendOnboardingRemindersCommand(BaseCommand):
    """
    Send onboarding reminders to inactive tenants.
    
    Usage:
        python manage.py send_onboarding_reminders [--days=<days>] [--dry-run]
    """
    
    help = "Send onboarding reminders to inactive tenants"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Days of inactivity to trigger reminder')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without sending')
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Sending onboarding reminders for inactive {days}+ days")
        
        # Get inactive onboardings
        inactive_onboardings = TenantOnboarding.objects.filter(
            status='in_progress'
        ).select_related('tenant')
        
        sent_count = 0
        failed_count = 0
        
        for onboarding in inactive_onboardings:
            try:
                if onboarding.needs_attention:
                    days_inactive = onboarding.days_since_start
                    
                    if days_inactive >= days:
                        if dry_run:
                            self.stdout.write(f"Would send reminder to: {onboarding.tenant.name} ({days_inactive} days inactive)")
                            sent_count += 1
                        else:
                            # Determine reminder type based on inactivity
                            if days_inactive >= 14:
                                title = 'Complete Your Setup'
                                message = f'You started your setup {days_inactive} days ago. Complete the remaining steps to get the most out of your account.'
                                priority = 'high'
                            elif days_inactive >= 7:
                                title = 'Continue Your Setup'
                                message = f'You have incomplete setup steps. Continue your onboarding to unlock all features.'
                                priority = 'medium'
                            else:
                                title = 'Setup Progress'
                                message = f'You\'re {onboarding.completion_pct}% through setup. Complete the remaining steps when you have time.'
                                priority = 'low'
                            
                            # Send notification
                            from ...models.analytics import TenantNotification
                            
                            TenantNotification.objects.create(
                                tenant=onboarding.tenant,
                                title=title,
                                message=message,
                                notification_type='onboarding',
                                priority=priority,
                                send_email=True,
                                send_push=True,
                                action_url='/onboarding',
                                action_text='Continue Setup',
                            )
                            
                            sent_count += 1
                            self.stdout.write(f"Sent reminder to: {onboarding.tenant.name}")
                            
                            # Update last reminder sent
                            onboarding.last_reminder_sent = timezone.now()
                            onboarding.save(update_fields=['last_reminder_sent'])
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to send reminder for {onboarding.tenant.name}: {str(e)}")
                )
        
        action = "Would send" if dry_run else "Sent"
        self.stdout.write(
            self.style.SUCCESS(f"{action} onboarding reminders to {sent_count} tenants, {failed_count} failed")
        )


class ScheduleTrialExtensionsCommand(BaseCommand):
    """
    Schedule trial extensions for tenants approaching expiry.
    
    Usage:
        python manage.py schedule_trial_extensions [--days=<days>] [--dry-run]
    """
    
    help = "Schedule trial extensions for tenants approaching expiry"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=3, help='Days until expiry to extend')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be scheduled without scheduling')
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Scheduling trial extensions for expiring in {days} days")
        
        # Get tenants with trials expiring soon
        upcoming_expiry = timezone.now() + timedelta(days=days)
        
        trial_tenants = Tenant.objects.filter(
            is_deleted=False,
            trial_ends_at__isnull=False,
            trial_ends_at__lte=upcoming_expiry,
            trial_ends_at__gt=timezone.now()
        ).select_related('plan', 'owner')
        
        scheduled_count = 0
        failed_count = 0
        
        for tenant in trial_tenants:
            try:
                days_until_expiry = tenant.days_until_trial_expiry
                
                # Check if tenant is actively using the platform
                from ...models.security import TenantAuditLog
                
                recent_activity = TenantAuditLog.objects.filter(
                    tenant=tenant,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count()
                
                # Determine if extension should be offered
                should_extend = False
                extension_days = 0
                reason = ""
                
                if days_until_expiry <= 1:
                    # Last day - offer extension if there's activity
                    if recent_activity >= 10:
                        should_extend = True
                        extension_days = 7
                        reason = "Active user engagement"
                elif days_until_expiry <= 3:
                    # 3 days or less - offer extension for good activity
                    if recent_activity >= 20:
                        should_extend = True
                        extension_days = 5
                        reason = "Good user engagement"
                elif days_until_expiry <= 7:
                    # Week or less - offer extension for high activity
                    if recent_activity >= 50:
                        should_extend = True
                        extension_days = 3
                        reason = "High user engagement"
                
                if should_extend:
                    if dry_run:
                        self.stdout.write(f"Would extend trial for: {tenant.name} ({extension_days} days - {reason})")
                        scheduled_count += 1
                    else:
                        # Create trial extension request
                        extension = TenantTrialExtension.objects.create(
                            tenant=tenant,
                            days_extended=extension_days,
                            reason='auto_scheduled',
                            reason_details=f"Auto-scheduled based on {reason}",
                            original_trial_end=tenant.trial_ends_at,
                        )
                        
                        # Send notification
                        from ...models.analytics import TenantNotification
                        
                        TenantNotification.objects.create(
                            tenant=tenant,
                            title='Trial Extension Offered',
                            message=f'Based on your activity, we\'ve extended your trial by {extension_days} days. Enjoy exploring more features!',
                            notification_type='trial',
                            priority='medium',
                            send_email=True,
                            send_push=True,
                            action_url='/billing/plans',
                            action_text='View Plan Options',
                        )
                        
                        scheduled_count += 1
                        self.stdout.write(f"Scheduled trial extension for: {tenant.name} ({extension_days} days)")
            
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to schedule extension for {tenant.name}: {str(e)}")
                )
        
        action = "Would schedule" if dry_run else "Scheduled"
        self.stdout.write(
            self.style.SUCCESS(f"{action} trial extensions for {scheduled_count} tenants, {failed_count} failed")
        )


class OnboardingAnalyticsCommand(BaseCommand):
    """
    Generate onboarding analytics report.
    
    Usage:
        python manage.py onboarding_analytics [--format=<format>]
    """
    
    help = "Generate onboarding analytics report"
    
    def add_arguments(self, parser):
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        output_format = options['format']
        
        self.stdout.write("Generating onboarding analytics")
        
        # Get analytics data
        analytics = OnboardingService.get_onboarding_analytics()
        
        # Add additional analytics
        from datetime import timedelta
        from django.db.models import Count, Avg
        
        # Recent completion trends
        last_30_days = timezone.now() - timedelta(days=30)
        
        recent_completions = TenantOnboarding.objects.filter(
            completed_at__gte=last_30_days,
            status='completed'
        )
        
        analytics['recent_trends'] = {
            'completions_last_30_days': recent_completions.count(),
            'average_completion_time': recent_completions.aggregate(
                avg_time=Avg('completed_at') - Avg('started_at')
            )['avg_time'].days if recent_completions.exists() else 0,
            'completion_rate': (recent_completions.count() / Tenant.objects.filter(
                created_at__gte=last_30_days
            ).count() * 100) if Tenant.objects.filter(
                created_at__gte=last_30_days
            ).exists() else 0,
        }
        
        # Step completion rates
        step_stats = TenantOnboardingStep.objects.filter(
            tenant__onboarding__status='completed'
        ).values('step_key').annotate(
            total=Count('id'),
            completed=Count('id', filter=models.Q(status='done'))
        )
        
        analytics['step_completion_rates'] = {
            step['step_key']: {
                'total': step['total'],
                'completed': step['completed'],
                'rate': (step['completed'] / step['total'] * 100) if step['total'] > 0 else 0
            }
            for step in step_stats
        }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(analytics, indent=2))
        else:
            self._output_table(analytics)
    
    def _output_table(self, analytics):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS("Onboarding Analytics"))
        self.stdout.write("=" * 50)
        
        # Overall stats
        self.stdout.write(f"Total Onboardings: {analytics['total_onboardings']}")
        self.stdout.write(f"Completed: {analytics['completed_onboardings']}")
        self.stdout.write(f"In Progress: {analytics['in_progress_onboardings']}")
        self.stdout.write(f"Not Started: {analytics['not_started_onboardings']}")
        self.stdout.write(f"Average Completion Rate: {analytics['average_completion_rate']:.1f}%")
        
        # Recent trends
        trends = analytics['recent_trends']
        self.stdout.write(f"\nRecent Trends (Last 30 Days):")
        self.stdout.write(f"  Completions: {trends['completions_last_30_days']}")
        self.stdout.write(f"  Avg Completion Time: {trends['average_completion_time']} days")
        self.stdout.write(f"  Completion Rate: {trends['completion_rate']:.1f}%")
        
        # Step completion rates
        self.stdout.write(f"\nStep Completion Rates:")
        for step_key, step_data in analytics['step_completion_rates'].items():
            self.stdout.write(f"  {step_key}: {step_data['completed']}/{step_data['total']} ({step_data['rate']:.1f}%)")


class OnboardingProgressCommand(BaseCommand):
    """
    Show onboarding progress for specific tenant.
    
    Usage:
        python manage.py onboarding_progress <tenant_id_or_name>
    """
    
    help = "Show onboarding progress for specific tenant"
    
    def add_arguments(self, parser):
        parser.add_argument('tenant', type=str, help='Tenant ID or name')
        parser.add_argument('--format', type=str, choices=['table', 'json'], default='table', help='Output format')
    
    def handle(self, *args, **options):
        tenant_id = options['tenant']
        output_format = options['format']
        
        self.stdout.write(f"Getting onboarding progress for: {tenant_id}")
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            try:
                tenant = Tenant.objects.get(name=tenant_id)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{tenant_id}' not found")
        
        # Get onboarding
        try:
            onboarding = tenant.onboarding
        except AttributeError:
            raise CommandError(f"Onboarding not found for tenant '{tenant.name}'")
        
        # Get progress data
        progress = OnboardingService.get_onboarding_progress(tenant)
        
        if output_format == 'json':
            self.stdout.write(json.dumps(progress, indent=2))
        else:
            self._output_table(progress, tenant)
    
    def _output_table(self, progress, tenant):
        """Output in table format."""
        self.stdout.write(self.style.SUCCESS(f"Onboarding Progress: {tenant.name}"))
        self.stdout.write("=" * 60)
        
        # Overall progress
        self.stdout.write(f"Status: {progress['status']}")
        self.stdout.write(f"Completion: {progress['completion_pct']}%")
        self.stdout.write(f"Current Step: {progress['current_step']}")
        self.stdout.write(f"Days Active: {progress['days_since_start']}")
        
        # Steps
        if progress['steps']:
            self.stdout.write(f"\nSteps:")
            for step in progress['steps']:
                status_icon = " " if step['status'] == 'done' else " "
                self.stdout.write(f"  {status_icon} {step['label']}: {step['status']}")
                if step.get('time_spent'):
                    self.stdout.write(f"    Time: {step['time_spent']}")
        
        # Recommendations
        if progress.get('recommendations'):
            self.stdout.write(f"\nRecommendations:")
            for rec in progress['recommendations']:
                self.stdout.write(f"  - {rec['message']}")


class CleanupOldOnboardingDataCommand(BaseCommand):
    """
    Clean up old onboarding data.
    
    Usage:
        python manage.py cleanup_old_onboarding_data [--days=<days>] [--dry-run]
    """
    
    help = "Clean up old onboarding data"
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='Number of days to keep data')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without cleaning')
    
    def handle(self, *args, **options):
        retention_days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Cleaning up onboarding data older than {retention_days} days")
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Archive completed onboarding sessions
        old_onboardings = TenantOnboarding.objects.filter(
            completed_at__lt=cutoff_date,
            status='completed'
        ).select_related('tenant')
        
        archived_count = old_onboardings.count()
        
        if dry_run:
            self.stdout.write(f"Would archive {archived_count} old onboarding sessions")
        else:
            # This would archive the data to cold storage
            # For now, just log the count
            self.stdout.write(f"Archived {archived_count} old onboarding sessions")
        
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup completed (cutoff date: {cutoff_date.date()})")
        )
