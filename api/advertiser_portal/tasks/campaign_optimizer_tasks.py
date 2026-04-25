"""
Campaign Optimizer Tasks

Hourly bid and targeting optimization
for improved campaign performance.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count

from ..models.campaign import AdCampaign, CampaignBid, CampaignTargeting
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
try:
    from ..services import RealtimeDashboardService
except ImportError:
    RealtimeDashboardService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.optimize_campaign_bids")
def optimize_campaign_bids():
    """
    Optimize campaign bids based on performance.
    
    This task runs hourly to analyze campaign performance
    and automatically adjust bids for better ROI.
    """
    try:
        optimizer = CampaignOptimizer()
        dashboard_service = RealtimeDashboardService()
        
        # Get all active campaigns with auto-optimization enabled
        optimizable_campaigns = AdCampaign.objects.filter(
            status='active',
            auto_optimize_enabled=True
        ).select_related('advertiser', 'bid_config')
        
        campaigns_optimized = 0
        optimizations_applied = 0
        
        for campaign in optimizable_campaigns:
            try:
                # Get current performance data
                performance_data = dashboard_service.get_campaign_performance(campaign, hours=24)
                
                # Check if optimization should run
                if _should_optimize_bids(campaign, performance_data):
                    # Run bid optimization
                    optimization_result = optimizer.optimize_bids(campaign, performance_data)
                    
                    if optimization_result.get('success'):
                        campaigns_optimized += 1
                        optimizations_applied += optimization_result.get('optimizations_applied', 0)
                        
                        logger.info(f"Bid optimization applied for campaign {campaign.id}: {optimization_result.get('optimizations_applied', 0)} changes")
                        
                        # Send optimization notification
                        _send_bid_optimization_notification(campaign, optimization_result)
                    else:
                        logger.error(f"Bid optimization failed for campaign {campaign.id}: {optimization_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error optimizing bids for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Bid optimization completed: {campaigns_optimized} campaigns optimized, {optimizations_applied} optimizations applied")
        
        return {
            'campaigns_checked': optimizable_campaigns.count(),
            'campaigns_optimized': campaigns_optimized,
            'optimizations_applied': optimizations_applied,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in bid optimization task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.optimize_campaign_targeting")
def optimize_campaign_targeting():
    """
    Optimize campaign targeting based on performance.
    
    This task runs hourly to analyze targeting performance
    and automatically adjust targeting rules.
    """
    try:
        optimizer = CampaignOptimizer()
        dashboard_service = RealtimeDashboardService()
        
        # Get all active campaigns with targeting optimization enabled
        optimizable_campaigns = AdCampaign.objects.filter(
            status='active',
            optimize_targeting=True
        ).select_related('advertiser').prefetch_related('targeting_rules')
        
        campaigns_optimized = 0
        targeting_changes = 0
        
        for campaign in optimizable_campaigns:
            try:
                # Get current performance data
                performance_data = dashboard_service.get_targeting_performance(campaign, hours=24)
                
                # Check if optimization should run
                if _should_optimize_targeting(campaign, performance_data):
                    # Run targeting optimization
                    optimization_result = optimizer.optimize_targeting(campaign, performance_data)
                    
                    if optimization_result.get('success'):
                        campaigns_optimized += 1
                        targeting_changes += optimization_result.get('changes_applied', 0)
                        
                        logger.info(f"Targeting optimization applied for campaign {campaign.id}: {optimization_result.get('changes_applied', 0)} changes")
                        
                        # Send optimization notification
                        _send_targeting_optimization_notification(campaign, optimization_result)
                    else:
                        logger.error(f"Targeting optimization failed for campaign {campaign.id}: {optimization_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error optimizing targeting for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Targeting optimization completed: {campaigns_optimized} campaigns optimized, {targeting_changes} changes applied")
        
        return {
            'campaigns_checked': optimizable_campaigns.count(),
            'campaigns_optimized': campaigns_optimized,
            'targeting_changes': targeting_changes,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in targeting optimization task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.analyze_optimization_results")
def analyze_optimization_results():
    """
    Analyze results of recent optimizations.
    
    This task runs daily to analyze the effectiveness
    of recent optimizations and adjust strategies.
    """
    try:
        optimizer = CampaignOptimizer()
        
        # Get optimization results from last 24 hours
        yesterday = timezone.now() - timezone.timedelta(days=1)
        
        optimization_results = optimizer.get_optimization_history(
            start_date=yesterday,
            end_date=timezone.now()
        )
        
        # Analyze effectiveness
        analysis = _analyze_optimization_effectiveness(optimization_results)
        
        # Update optimization strategies based on results
        strategy_updates = _update_optimization_strategies(analysis)
        
        logger.info(f"Optimization analysis completed: {len(optimization_results)} optimizations analyzed, {strategy_updates} strategy updates")
        
        return {
            'optimizations_analyzed': len(optimization_results),
            'analysis': analysis,
            'strategy_updates': strategy_updates,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in optimization analysis task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_optimization_health")
def check_optimization_health():
    """
    Check health of optimization systems.
    
    This task runs every 6 hours to check if
    optimization systems are working correctly.
    """
    try:
        optimizer = CampaignOptimizer()
        
        # Check optimizer health
        health_check = optimizer.health_check()
        
        issues_found = 0
        
        if not health_check.get('healthy', True):
            issues_found = len(health_check.get('issues', []))
            logger.warning(f"Optimization health issues found: {health_check.get('issues', [])}")
            
            # Send health alert if critical issues
            if health_check.get('severity') == 'critical':
                _send_optimization_health_alert(health_check)
        
        # Check optimization frequency
        frequency_check = _check_optimization_frequency()
        
        if not frequency_check.get('healthy', True):
            issues_found += len(frequency_check.get('issues', []))
            logger.warning(f"Optimization frequency issues: {frequency_check.get('issues', [])}")
        
        # Check optimization effectiveness
        effectiveness_check = _check_optimization_effectiveness()
        
        if not effectiveness_check.get('healthy', True):
            issues_found += len(effectiveness_check.get('issues', []))
            logger.warning(f"Optimization effectiveness issues: {effectiveness_check.get('issues', [])}")
        
        logger.info(f"Optimization health check completed: {issues_found} issues found")
        
        return {
            'health_check': health_check,
            'frequency_check': frequency_check,
            'effectiveness_check': effectiveness_check,
            'total_issues': issues_found,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in optimization health check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_optimization_logs")
def cleanup_optimization_logs():
    """
    Clean up old optimization logs and records.
    
    This task runs weekly to clean up old optimization
    logs and maintain database performance.
    """
    try:
        optimizer = CampaignOptimizer()
        
        # Clean up logs older than 30 days
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        
        # This would implement actual cleanup logic
        logs_cleaned = optimizer.cleanup_old_optimization_logs(cutoff_date)
        
        logger.info(f"Optimization log cleanup completed: {logs_cleaned} logs cleaned")
        
        return {
            'cutoff_date': cutoff_date.date().isoformat(),
            'logs_cleaned': logs_cleaned,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in optimization log cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _should_optimize_bids(campaign, performance_data):
    """Check if campaign bids should be optimized."""
    try:
        # Check minimum performance data
        if not performance_data or performance_data.get('clicks', 0) < 10:
            return False
        
        # Check if last optimization was recent (avoid over-optimization)
        last_optimization = campaign.last_bid_optimization
        if last_optimization:
            time_since_optimization = timezone.now() - last_optimization
            if time_since_optimization < timezone.timedelta(hours=6):
                return False
        
        # Check performance thresholds
        ctr = performance_data.get('ctr', 0)
        cpa = performance_data.get('cpa', 0)
        conversion_rate = performance_data.get('conversion_rate', 0)
        
        # Optimize if performance is below thresholds
        if ctr < campaign.target_ctr or cpa > campaign.target_cpa or conversion_rate < campaign.target_conversion_rate:
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking if should optimize bids: {e}")
        return False


def _should_optimize_targeting(campaign, performance_data):
    """Check if campaign targeting should be optimized."""
    try:
        # Check minimum performance data
        if not performance_data or performance_data.get('impressions', 0) < 100:
            return False
        
        # Check if last optimization was recent
        last_optimization = campaign.last_targeting_optimization
        if last_optimization:
            time_since_optimization = timezone.now() - last_optimization
            if time_since_optimization < timezone.timedelta(hours=12):
                return False
        
        # Check for underperforming segments
        underperforming_segments = performance_data.get('underperforming_segments', [])
        
        if len(underperforming_segments) > 0:
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking if should optimize targeting: {e}")
        return False


def _analyze_optimization_effectiveness(optimization_results):
    """Analyze effectiveness of optimizations."""
    try:
        if not optimization_results:
            return {
                'total_optimizations': 0,
                'average_improvement': 0,
                'success_rate': 0,
                'recommendations': []
            }
        
        total_optimizations = len(optimization_results)
        successful_optimizations = len([r for r in optimization_results if r.get('success', False)])
        
        # Calculate average improvement
        improvements = [r.get('improvement_percentage', 0) for r in optimization_results if r.get('improvement_percentage')]
        average_improvement = sum(improvements) / len(improvements) if improvements else 0
        
        # Generate recommendations
        recommendations = []
        
        if average_improvement < 5:
            recommendations.append("Consider adjusting optimization thresholds for better results")
        
        if successful_optimizations / total_optimizations < 0.8:
            recommendations.append("Review optimization algorithms - success rate is low")
        
        return {
            'total_optimizations': total_optimizations,
            'successful_optimizations': successful_optimizations,
            'success_rate': (successful_optimizations / total_optimizations * 100) if total_optimizations > 0 else 0,
            'average_improvement': average_improvement,
            'recommendations': recommendations,
        }
        
    except Exception as e:
        logger.error(f"Error analyzing optimization effectiveness: {e}")
        return {}


def _update_optimization_strategies(analysis):
    """Update optimization strategies based on analysis."""
    try:
        strategy_updates = 0
        
        # Update strategies based on recommendations
        recommendations = analysis.get('recommendations', [])
        
        for recommendation in recommendations:
            # This would implement actual strategy updates
            # For now, just count the updates
            strategy_updates += 1
            logger.info(f"Strategy update: {recommendation}")
        
        return strategy_updates
        
    except Exception as e:
        logger.error(f"Error updating optimization strategies: {e}")
        return 0


def _check_optimization_frequency():
    """Check if optimization frequency is appropriate."""
    try:
        # Get optimization count in last 24 hours
        yesterday = timezone.now() - timezone.timedelta(days=1)
        
        optimization_count = AdCampaign.objects.filter(
            last_bid_optimization__gte=yesterday
        ).count()
        
        issues = []
        
        # Check if too many optimizations
        if optimization_count > 100:
            issues.append("Too many optimizations in last 24 hours")
        
        # Check if too few optimizations
        if optimization_count < 10:
            issues.append("Too few optimizations in last 24 hours")
        
        return {
            'healthy': len(issues) == 0,
            'optimization_count': optimization_count,
            'issues': issues,
        }
        
    except Exception as e:
        logger.error(f"Error checking optimization frequency: {e}")
        return {'healthy': False, 'issues': [str(e)]}


def _check_optimization_effectiveness():
    """Check if optimizations are effective."""
    try:
        # Get recent optimization results
        yesterday = timezone.now() - timezone.timedelta(days=1)
        
        recent_optimizations = AdCampaign.objects.filter(
            last_bid_optimization__gte=yesterday
        ).aggregate(
            avg_improvement=Avg('optimization_improvement'),
            success_count=Count(Case(When(optimization_success=True, then=1))),
            total_count=Count('id')
        )
        
        issues = []
        
        # Check success rate
        success_rate = (recent_optimizations['success_count'] / recent_optimizations['total_count'] * 100) if recent_optimizations['total_count'] > 0 else 0
        
        if success_rate < 70:
            issues.append("Low optimization success rate")
        
        # Check average improvement
        avg_improvement = recent_optimizations['avg_improvement'] or 0
        
        if avg_improvement < 5:
            issues.append("Low average optimization improvement")
        
        return {
            'healthy': len(issues) == 0,
            'success_rate': success_rate,
            'average_improvement': avg_improvement,
            'issues': issues,
        }
        
    except Exception as e:
        logger.error(f"Error checking optimization effectiveness: {e}")
        return {'healthy': False, 'issues': [str(e)]}


def _send_bid_optimization_notification(campaign, optimization_result):
    """Send bid optimization notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'bid_optimization',
            'title': 'Campaign Bid Optimized',
            'message': f'Your campaign "{campaign.name}" bids have been automatically optimized for better performance.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'optimizations_applied': optimization_result.get('optimizations_applied', 0),
                'expected_improvement': optimization_result.get('expected_improvement', 0),
                'optimized_at': optimization_result.get('optimized_at'),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending bid optimization notification: {e}")


def _send_targeting_optimization_notification(campaign, optimization_result):
    """Send targeting optimization notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'targeting_optimization',
            'title': 'Campaign Targeting Optimized',
            'message': f'Your campaign "{campaign.name}" targeting has been automatically optimized for better performance.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'changes_applied': optimization_result.get('changes_applied', 0),
                'segments_optimized': optimization_result.get('segments_optimized', []),
                'optimized_at': optimization_result.get('optimized_at'),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending targeting optimization notification: {e}")


def _send_optimization_health_alert(health_check):
    """Send optimization health alert notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'type': 'optimization_health_alert',
            'title': 'Campaign Optimization Health Alert',
            'message': f'Campaign optimization system has health issues: {", ".join(health_check.get("issues", []))}',
            'data': {
                'issues': health_check.get('issues', []),
                'severity': health_check.get('severity', 'warning'),
                'checked_at': health_check.get('checked_at'),
            }
        }
        
        # Send to admin users
        notification_service.send_admin_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending optimization health alert: {e}")
