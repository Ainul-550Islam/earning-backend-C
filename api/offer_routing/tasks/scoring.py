"""
Scoring Tasks for Offer Routing System

This module contains background tasks for offer scoring,
ranking, and score optimization operations.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.scoring import scoring_service, ranker_service
from ..services.optimizer import routing_optimizer
from ..constants import SCORE_UPDATE_INTERVAL_HOURS, SCORE_CACHE_TIMEOUT

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.scoring.update_all_offer_scores')
def update_all_offer_scores(self):
    """
    Update scores for all offers in the system.
    
    This task recalculates scores for all offers based on
    recent performance data and updates the cache.
    """
    try:
        logger.info("Starting offer score update")
        
        if not scoring_service:
            logger.warning("Scoring service not available")
            return {'success': False, 'error': 'Scoring service not available'}
        
        # Get all offers
        from ..models import OfferRoute
        offers = OfferRoute.objects.filter(is_active=True)
        
        updated_count = 0
        failed_count = 0
        
        for offer in offers:
            try:
                # Update score for this offer
                scoring_service.update_offer_score(offer)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update score for offer {offer.id}: {e}")
                failed_count += 1
        
        logger.info(f"Offer score update completed: {updated_count} updated, {failed_count} failed")
        return {
            'success': True,
            'updated_offers': updated_count,
            'failed_offers': failed_count,
            'total_offers': offers.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Offer score update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.update_global_rankings')
def update_global_rankings(self):
    """
    Update global offer rankings based on current scores.
    
    This task recalculates global rankings for all offers
    and updates the ranking cache.
    """
    try:
        logger.info("Starting global rankings update")
        
        if not ranker_service:
            logger.warning("Ranker service not available")
            return {'success': False, 'error': 'Ranker service not available'}
        
        # Update global rankings
        updated_count = ranker_service.update_global_rankings()
        
        logger.info(f"Global rankings update completed: {updated_count} offers ranked")
        return {
            'success': True,
            'ranked_offers': updated_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Global rankings update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.optimize_score_weights')
def optimize_score_weights(self):
    """
    Optimize scoring weights based on performance data.
    
    This task analyzes recent performance data and optimizes
    scoring weights for better performance.
    """
    try:
        logger.info("Starting score weight optimization")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        total_optimized = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                optimization_result = routing_optimizer.optimize_score_weights(tenant_id=tenant.id)
                if optimization_result.get('optimized_configs', 0) > 0:
                    total_optimized += optimization_result['optimized_configs']
            except Exception as e:
                logger.error(f"Failed to optimize scores for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Score weight optimization completed: {total_optimized} configs optimized")
        return {
            'success': True,
            'optimized_configs': total_optimized,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Score weight optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.calculate_user_affinity_scores')
def calculate_user_affinity_scores(self):
    """
    Calculate affinity scores for all users.
    
    This task updates affinity scores for all users based on
    their recent interaction history.
    """
    try:
        logger.info("Starting user affinity score calculation")
        
        from ..services.personalization import affinity_service
        
        if not affinity_service:
            logger.warning("Affinity service not available")
            return {'success': False, 'error': 'Affinity service not available'}
        
        # Get all users
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        users = User.objects.all()  # This would be filtered to actual users
        
        updated_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Update affinity scores for this user
                affinity_service.update_user_affinity_scores(user.id)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update affinity scores for user {user.id}: {e}")
                failed_count += 1
        
        logger.info(f"User affinity score calculation completed: {updated_count} updated, {failed_count} failed")
        return {
            'success': True,
            'updated_users': updated_count,
            'failed_users': failed_count,
            'total_users': users.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"User affinity score calculation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.update_user_offer_history')
def update_user_offer_history(self):
    """
    Update user offer history and interaction data.
    
    This task processes recent user interactions and updates
    the user offer history for scoring purposes.
    """
    try:
        logger.info("Starting user offer history update")
        
        # Get recent interactions
        from ..models import UserOfferHistory
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_interactions = UserOfferHistory.objects.filter(
            created_at__gte=cutoff_date
        )
        
        updated_count = 0
        
        for interaction in recent_interactions:
            try:
                # Update user preference vectors based on interaction
                from ..services.personalization import personalization_service
                
                if personalization_service:
                    interaction_data = {
                        'offer_id': interaction.offer.id,
                        'interaction_type': 'view',
                        'timestamp': interaction.created_at.isoformat(),
                        'value': 1.0
                    }
                    
                    if interaction.clicked_at:
                        interaction_data['interaction_type'] = 'click'
                        interaction_data['value'] = 2.0
                    
                    if interaction.completed_at:
                        interaction_data['interaction_type'] = 'conversion'
                        interaction_data['value'] = 5.0
                    
                    personalization_service.update_user_preferences(
                        user=interaction.user,
                        interaction_data=[interaction_data]
                    )
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update user offer history for interaction {interaction.id}: {e}")
        
        logger.info(f"User offer history update completed: {updated_count} interactions processed")
        return {
            'success': True,
            'processed_interactions': updated_count,
            'total_recent_interactions': recent_interactions.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"User offer history update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.refresh_score_cache')
def refresh_score_cache(self):
    """
    Refresh the scoring cache with updated data.
    
    This task updates the cache with fresh scoring data
    to ensure accurate and up-to-date scores.
    """
    try:
        logger.info("Starting score cache refresh")
        
        if not scoring_service:
            logger.warning("Scoring service not available")
            return {'success': False, 'error': 'Scoring service not available'}
        
        # Refresh score cache
        refreshed_count = scoring_service.refresh_score_cache()
        
        logger.info(f"Score cache refresh completed: {refreshed_count} entries refreshed")
        return {
            'success': True,
            'refreshed_entries': refreshed_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Score cache refresh failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.analyze_score_performance')
def analyze_score_performance(self):
    """
    Analyze scoring performance and generate insights.
    
    This task analyzes scoring performance metrics and
    generates insights for optimization.
    """
    try:
        logger.info("Starting score performance analysis")
        
        from datetime import timedelta
        from ..models import OfferScore, RoutePerformanceStat
        
        # Get recent performance data
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Analyze score distribution
        score_stats = OfferScore.objects.filter(
            created_at__gte=cutoff_date
        ).aggregate(
            avg_score=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
            total_scores=Count('id')
        )
        
        # Analyze correlation between scores and performance
        performance_stats = RoutePerformanceStat.objects.filter(
            date__gte=cutoff_date.date()
        ).aggregate(
            avg_conversion_rate=Avg('conversion_rate'),
            avg_click_through_rate=Avg('click_through_rate'),
            total_impressions=Sum('impressions'),
            total_conversions=Sum('conversions')
        )
        
        # Generate insights
        insights = []
        
        if score_stats['avg_score'] and performance_stats['avg_conversion_rate']:
            # Check if higher scores correlate with better performance
            correlation = score_stats['avg_score'] / performance_stats['avg_conversion_rate'] if performance_stats['avg_conversion_rate'] > 0 else 0
            
            if correlation > 100:
                insights.append({
                    'type': 'score_correlation',
                    'message': 'High scores correlate well with conversion rates',
                    'correlation': correlation
                })
            else:
                insights.append({
                    'type': 'score_correlation',
                    'message': 'Score correlation with performance could be improved',
                    'correlation': correlation
                })
        
        # Check score distribution
        if score_stats['avg_score'] and score_stats['max_score']:
            score_range = score_stats['max_score'] - score_stats['min_score']
            if score_range < 20:
                insights.append({
                    'type': 'score_distribution',
                    'message': 'Score range is narrow, consider adjusting scoring weights',
                    'score_range': score_range
                })
        
        logger.info(f"Score performance analysis completed: {len(insights)} insights generated")
        return {
            'success': True,
            'score_stats': score_stats,
            'performance_stats': performance_stats,
            'insights': insights,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Score performance analysis failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.update_epc_data')
def update_epc_data(self):
    """
    Update earnings per click (EPC) data for offers.
    
    This task calculates and updates EPC values for all offers
    based on recent revenue and click data.
    """
    try:
        logger.info("Starting EPC data update")
        
        from ..models import OfferScore, RoutePerformanceStat
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Get all offers
        from ..models import OfferRoute
        offers = OfferRoute.objects.filter(is_active=True)
        
        updated_count = 0
        failed_count = 0
        
        for offer in offers:
            try:
                # Get performance data for this offer
                performance_data = RoutePerformanceStat.objects.filter(
                    offer=offer,
                    date__gte=cutoff_date.date()
                ).aggregate(
                    total_revenue=Sum('revenue'),
                    total_clicks=Sum('clicks')
                )
                
                total_revenue = performance_data['total_revenue'] or 0
                total_clicks = performance_data['total_clicks'] or 0
                
                # Calculate EPC
                epc = total_revenue / total_clicks if total_clicks > 0 else 0
                
                # Update score records with EPC
                score_records = OfferScore.objects.filter(
                    offer=offer,
                    created_at__gte=cutoff_date
                ).update(epc=epc)
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update EPC data for offer {offer.id}: {e}")
                failed_count += 1
        
        logger.info(f"EPC data update completed: {updated_count} updated, {failed_count} failed")
        return {
            'success': True,
            'updated_offers': updated_count,
            'failed_offers': failed_count,
            'total_offers': offers.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"EPC data update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.scoring.calculate_conversion_rates')
def calculate_conversion_rates(self):
    """
    Calculate conversion rates for offers and update scoring data.
    
    This task calculates conversion rates for all offers
    and updates the scoring data accordingly.
    """
    try:
        logger.info("Starting conversion rate calculation")
        
        from ..models import OfferScore, RoutePerformanceStat
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Get all offers
        from ..models import OfferRoute
        offers = OfferRoute.objects.filter(is_active=True)
        
        updated_count = 0
        failed_count = 0
        
        for offer in offers:
            try:
                # Get performance data for this offer
                performance_data = RoutePerformanceStat.objects.filter(
                    offer=offer,
                    date__gte=cutoff_date.date()
                ).aggregate(
                    total_conversions=Sum('conversions'),
                    total_impressions=Sum('impressions')
                )
                
                total_conversions = performance_data['total_conversions'] or 0
                total_impressions = performance_data['total_impressions'] or 0
                
                # Calculate conversion rate
                cr = (total_conversions / total_impressions * 100) if total_impressions > 0 else 0
                
                # Update score records with CR
                score_records = OfferScore.objects.filter(
                    offer=offer,
                    created_at__gte=cutoff_date
                ).update(cr=cr)
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to calculate conversion rate for offer {offer.id}: {e}")
                failed_count += 1
        
        logger.info(f"Conversion rate calculation completed: {updated_count} updated, {failed_count} failed")
        return {
            'success': True,
            'updated_offers': updated_count,
            'failed_offers': failed_count,
            'total_offers': offers.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Conversion rate calculation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
