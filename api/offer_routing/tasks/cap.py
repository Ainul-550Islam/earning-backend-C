"""
Cap Tasks for Offer Routing System

This module contains background tasks for cap management,
including daily resets, cap enforcement, and analytics.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.cap import cap_service
from ..constants import DAILY_CAP_RESET_HOUR

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.cap.reset_daily_caps')
def reset_daily_caps(self):
    """
    Reset daily caps for all users and offers.
    
    This task runs daily to reset daily caps and
    prepare for the new day's routing.
    """
    try:
        logger.info("Starting daily cap reset")
        
        if not cap_service:
            logger.warning("Cap service not available")
            return {'success': False, 'error': 'Cap service not available'}
        
        # Reset daily caps
        reset_count = cap_service.reset_daily_caps()
        
        logger.info(f"Daily cap reset completed: {reset_count} caps reset")
        return {
            'success': True,
            'reset_caps': reset_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Daily cap reset failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.enforce_global_caps')
def enforce_global_caps(self):
    """
    Enforce global caps and update usage statistics.
    
    This task checks global cap usage and enforces
    limits where necessary.
    """
    try:
        logger.info("Starting global cap enforcement")
        
        # Get all active global caps
        from ..models import OfferRoutingCap
        
        active_caps = OfferRoutingCap.objects.filter(
            is_active=True
        ).select_related('offer', 'tenant')
        
        enforced_count = 0
        failed_count = 0
        
        for cap in active_caps:
            try:
                # Check if cap is exceeded
                if not cap.is_active():
                    continue
                
                remaining_capacity = cap.get_remaining_capacity()
                
                if remaining_capacity <= 0:
                    # Cap is exceeded, enforce it
                    cap.enforce_cap()
                    enforced_count += 1
                    
                    # Log cap enforcement
                    logger.warning(f"Global cap enforced for offer {cap.offer.id} in tenant {cap.tenant.id}")
                
            except Exception as e:
                logger.error(f"Failed to enforce global cap {cap.id}: {e}")
                failed_count += 1
        
        logger.info(f"Global cap enforcement completed: {enforced_count} enforced, {failed_count} failed")
        return {
            'success': True,
            'enforced_caps': enforced_count,
            'failed_caps': failed_count,
            'total_active_caps': active_caps.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Global cap enforcement failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.update_cap_analytics')
def update_cap_analytics(self):
    """
    Update cap usage analytics and generate insights.
    
    This task analyzes cap usage patterns and generates
    analytics for optimization.
    """
    try:
        logger.info("Starting cap analytics update")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        total_tenants = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                # Get cap analytics for this tenant
                analytics = cap_service.get_cap_analytics(tenant_id=tenant.id, days=30)
                total_tenants += 1
                
                # Store analytics (placeholder)
                # This would store the analytics in the database or cache
                
            except Exception as e:
                logger.error(f"Failed to update cap analytics for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Cap analytics update completed: {total_tenants} tenants updated, {len(failed_tenants)} failed")
        return {
            'success': True,
            'updated_tenants': total_tenants,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap analytics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.check_cap_health')
def check_cap_health(self):
    """
    Check health of cap configurations and usage.
    
    This task validates cap configurations and checks
    for potential issues.
    """
    try:
        logger.info("Starting cap health check")
        
        # Check global caps
        from ..models import OfferRoutingCap, UserOfferCap, CapOverride
        
        global_caps = OfferRoutingCap.objects.filter(is_active=True)
        user_caps = UserOfferCap.objects.all()
        overrides = CapOverride.objects.filter(is_active=True)
        
        health_issues = []
        
        # Check for caps with no remaining capacity
        for cap in global_caps:
            try:
                remaining_capacity = cap.get_remaining_capacity()
                if remaining_capacity <= 0:
                    health_issues.append({
                        'type': 'cap_exhausted',
                        'cap_id': cap.id,
                        'offer_id': cap.offer.id,
                        'message': f"Global cap exhausted for offer {cap.offer.id}"
                    })
            except Exception as e:
                logger.error(f"Failed to check global cap {cap.id}: {e}")
        
        # Check for user caps that are consistently reached
        for user_cap in user_caps:
            try:
                if user_cap.cap_type == 'daily' and user_cap.is_daily_cap_reached():
                    health_issues.append({
                        'type': 'user_cap_reached',
                        'cap_id': user_cap.id,
                        'user_id': user_cap.user.id,
                        'offer_id': user_cap.offer.id,
                        'message': f"Daily cap reached for user {user_cap.user.id} and offer {user_cap.offer.id}"
                    })
            except Exception as e:
                logger.error(f"Failed to check user cap {user_cap.id}: {e}")
        
        # Check for expired overrides
        expired_overrides = overrides.filter(
            valid_to__lt=timezone.now()
        ).update(is_active=False)
        
        if expired_overrides > 0:
            health_issues.append({
                'type': 'expired_overrides',
                'count': expired_overrides,
                'message': f"Deactivated {expired_overrides} expired overrides"
            })
        
        logger.info(f"Cap health check completed: {len(health_issues)} issues found")
        return {
            'success': True,
            'health_issues': health_issues,
            'global_caps_checked': global_caps.count(),
            'user_caps_checked': user_caps.count(),
            'overrides_checked': overrides.count(),
            'expired_overrides_deactivated': expired_overrides,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap health check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.optimize_cap_configuration')
def optimize_cap_configuration(self):
    """
    Optimize cap configurations based on usage patterns.
    
    This task analyzes cap usage and suggests optimizations
    for better performance.
    """
    try:
        logger.info("Starting cap configuration optimization")
        
        # Get cap usage analytics
        from ..models import OfferRoutingCap, UserOfferCap
        
        global_caps = OfferRoutingCap.objects.filter(is_active=True)
        user_caps = UserOfferCap.objects.all()
        
        optimizations = []
        
        # Analyze global caps
        for cap in global_caps:
            try:
                # Get usage statistics
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=30)
                
                # This would get actual usage statistics
                # For now, use placeholder logic
                
                current_usage = cap.current_count
                cap_value = cap.cap_value
                
                # Suggest optimizations based on usage
                if cap.cap_type == 'daily' and current_usage < cap_value * 0.5:
                    optimizations.append({
                        'type': 'increase_cap',
                        'cap_id': cap.id,
                        'offer_id': cap.offer.id,
                        'message': f"Consider increasing cap for offer {cap.offer.id} - usage is low ({current_usage}/{cap_value})",
                        'suggestion': 'Increase cap value or reduce frequency'
                    })
                elif current_usage >= cap_value * 0.9:
                    optimizations.append({
                        'type': 'cap_near_limit',
                        'cap_id': cap.id,
                        'offer_id': cap.offer.id,
                        'message': f"Cap for offer {cap.offer.id} is near limit ({current_usage}/{cap_value})",
                        'suggestion': 'Consider increasing cap value or optimizing offer selection'
                    })
                
            except Exception as e:
                logger.error(f"Failed to analyze global cap {cap.id}: {e}")
        
        # Analyze user caps
        for user_cap in user_caps:
            try:
                if user_cap.cap_type == 'daily':
                    usage_ratio = user_cap.shown_today / user_cap.max_shows_per_day
                    
                    if usage_ratio < 0.3:
                        optimizations.append({
                            'type': 'user_cap_underutilized',
                            'cap_id': user_cap.id,
                            'user_id': user_cap.user.id,
                            'offer_id': user_cap.offer.id,
                            'message': f"User cap underutilized for user {user_cap.user.id} and offer {user_cap.offer.id}",
                            'suggestion': 'Consider reducing cap or increasing offer exposure'
                        })
                    elif usage_ratio > 0.9:
                        optimizations.append({
                            'type': 'user_cap_overutilized',
                            'cap_id': user_cap.id,
                            'user_id': user_cap.user.id,
                            'offer_id': user_cap.offer.id,
                            'message': f"User cap overutilized for user {user_cap.user.id} and offer {user_cap.offer.id}",
                            'suggestion': 'Consider increasing cap or optimizing offer selection'
                        })
                
            except Exception as e:
                logger.error(f"Failed to analyze user cap {user_cap.id}: {e}")
        
        logger.info(f"Cap configuration optimization completed: {len(optimizations)} optimizations suggested")
        return {
            'success': True,
            'optimizations': optimizations,
            'global_caps_analyzed': global_caps.count(),
            'user_caps_analyzed': user_caps.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap configuration optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.cleanup_old_cap_data')
def cleanup_old_cap_data(self):
    """
    Clean up old cap data and maintain performance.
    
    This task removes old cap data and optimizes
    cap-related database tables.
    """
    try:
        logger.info("Starting cap data cleanup")
        
        from datetime import timedelta
        
        # Clean up old user cap history
        from ..models import UserOfferCap
        
        # This would clean up old cap history records
        # For now, just log the action
        
        # Clean up expired cap overrides
        from ..models import CapOverride
        
        expired_overrides = CapOverride.objects.filter(
            valid_to__lt=timezone.now()
        ).delete()[0]
        
        # Clean up old cap analytics data
        # This would clean up old analytics records
        
        logger.info(f"Cap data cleanup completed: {expired_overrides} expired overrides deleted")
        return {
            'success': True,
            'deleted_overrides': expired_overrides,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap data cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.generate_cap_reports')
def generate_cap_reports(self):
    """
    Generate cap usage reports for analysis.
    
    This task generates comprehensive reports on cap usage,
    performance, and trends.
    """
    try:
        logger.info("Starting cap report generation")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        generated_reports = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                # Generate cap report for this tenant
                report_data = {
                    'tenant_id': tenant.id,
                    'generated_at': timezone.now().isoformat(),
                    'period_days': 30,
                    'global_caps': {},
                    'user_caps': {},
                    'overrides': {},
                    'analytics': {}
                }
                
                # Get global cap data
                from ..models import OfferRoutingCap
                global_caps = OfferRoutingCap.objects.filter(tenant=tenant, is_active=True)
                
                report_data['global_caps'] = {
                    'total_caps': global_caps.count(),
                    'active_caps': global_caps.count(),
                    'caps_by_type': {},  # Would group by cap_type
                    'total_usage': sum(cap.current_count for cap in global_caps),
                    'total_capacity': sum(cap.cap_value for cap in global_caps)
                }
                
                # Get user cap data
                from ..models import UserOfferCap
                user_caps = UserOfferCap.objects.filter(user__tenant=tenant)
                
                report_data['user_caps'] = {
                    'total_user_caps': user_caps.count(),
                    'daily_caps': user_caps.filter(cap_type='daily').count(),
                    'caps_reached_today': user_caps.filter(
                        cap_type='daily',
                        shown_today__gte=F('max_shows_per_day')
                    ).count()
                }
                
                # Get override data
                from ..models import CapOverride
                overrides = CapOverride.objects.filter(tenant=tenant, is_active=True)
                
                report_data['overrides'] = {
                    'total_overrides': overrides.count(),
                    'overrides_by_type': {},  # Would group by override_type
                    'active_overrides': overrides.count()
                }
                
                # Store report (placeholder)
                # This would save the report to database or file
                
                generated_reports += 1
                
            except Exception as e:
                logger.error(f"Failed to generate cap report for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Cap report generation completed: {generated_reports} reports generated, {len(failed_tenants)} failed")
        return {
            'success': True,
            'generated_reports': generated_reports,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap report generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.cap.update_cap_usage_statistics')
def update_cap_usage_statistics(self):
    """
    Update cap usage statistics for monitoring.
    
    This task updates statistics tables for cap usage
    monitoring and analytics.
    """
    try:
        logger.info("Starting cap usage statistics update")
        
        # Get current cap usage
        from ..models import OfferRoutingCap, UserOfferCap
        
        # Update global cap statistics
        global_caps = OfferRoutingCap.objects.filter(is_active=True)
        
        global_stats = {
            'total_caps': global_caps.count(),
            'total_usage': sum(cap.current_count for cap in global_caps),
            'total_capacity': sum(cap.cap_value for cap in global_caps),
            'caps_exhausted': sum(1 for cap in global_caps if cap.get_remaining_capacity() <= 0)
        }
        
        # Update user cap statistics
        user_caps = UserOfferCap.objects.all()
        
        user_stats = {
            'total_user_caps': user_caps.count(),
            'daily_caps': user_caps.filter(cap_type='daily').count(),
            'caps_reached_today': user_caps.filter(
                cap_type='daily',
                shown_today__gte=F('max_shows_per_day')
            ).count()
        }
        
        # Store statistics (placeholder)
        # This would save the statistics to database or cache
        
        logger.info(f"Cap usage statistics update completed")
        return {
            'success': True,
            'global_stats': global_stats,
            'user_stats': user_stats,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cap usage statistics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
