"""
Personalization Tasks for Offer Routing System

This module contains background tasks for personalization,
including preference updates, affinity calculations, and model training.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.personalization import (
    personalization_service, collaborative_service, 
    content_based_service, affinity_service
)
from ..services.optimizer import routing_optimizer
from ..constants import PERSONALIZATION_UPDATE_INTERVAL_HOURS

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.personalization.update_user_preferences')
def update_user_preferences(self):
    """
    Update user preferences based on recent interactions.
    
    This task processes recent user interactions and updates
    preference vectors for better personalization.
    """
    try:
        logger.info("Starting user preference update")
        
        if not personalization_service:
            logger.warning("Personalization service not available")
            return {'success': False, 'error': 'Personalization service not available'}
        
        # Get recent user interactions
        from ..models import UserOfferHistory
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_interactions = UserOfferHistory.objects.filter(
            created_at__gte=cutoff_date
        ).select_related('user', 'offer')
        
        updated_users = set()
        failed_interactions = 0
        
        for interaction in recent_interactions:
            try:
                # Prepare interaction data
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
                    if interaction.conversion_value:
                        interaction_data['conversion_value'] = float(interaction.conversion_value)
                
                # Update user preferences
                personalization_service.update_user_preferences(
                    user=interaction.user,
                    interaction_data=[interaction_data]
                )
                
                updated_users.add(interaction.user.id)
                
            except Exception as e:
                logger.error(f"Failed to update preferences for interaction {interaction.id}: {e}")
                failed_interactions += 1
        
        logger.info(f"User preference update completed: {len(updated_users)} users updated, {failed_interactions} failed")
        return {
            'success': True,
            'updated_users': len(updated_users),
            'failed_interactions': failed_interactions,
            'total_interactions': recent_interactions.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"User preference update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.update_affinity_scores')
def update_affinity_scores(self):
    """
    Update user-category affinity scores.
    
    This task recalculates affinity scores for all users
    based on their recent interaction history.
    """
    try:
        logger.info("Starting affinity score update")
        
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
        
        logger.info(f"Affinity score update completed: {updated_count} updated, {failed_count} failed")
        return {
            'success': True,
            'updated_users': updated_count,
            'failed_users': failed_count,
            'total_users': users.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Affinity score update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.update_collaborative_filtering')
def update_collaborative_filtering(self):
    """
    Update collaborative filtering models.
    
    This task updates user similarity matrices and
    collaborative filtering recommendations.
    """
    try:
        logger.info("Starting collaborative filtering update")
        
        if not collaborative_service:
            logger.warning("Collaborative service not available")
            return {'success': False, 'error': 'Collaborative service not available'}
        
        # Update user similarity matrix
        updated_users = collaborative_service.update_user_similarity_matrix()
        
        # Update collaborative recommendations
        updated_recommendations = collaborative_service.update_collaborative_recommendations()
        
        logger.info(f"Collaborative filtering update completed: {updated_users} users, {updated_recommendations} recommendations")
        return {
            'success': True,
            'updated_users': updated_users,
            'updated_recommendations': updated_recommendations,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Collaborative filtering update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.update_content_based_filtering')
def update_content_based_filtering(self):
    """
    Update content-based filtering models.
    
    This task updates offer content analysis and
    content-based recommendations.
    """
    try:
        logger.info("Starting content-based filtering update")
        
        if not content_based_service:
            logger.warning("Content-based service not available")
            return {'success': False, 'error': 'Content-based service not available'}
        
        # Update offer content analysis
        analyzed_offers = content_based_service.analyze_offer_content()
        
        # Update content-based recommendations
        updated_recommendations = content_based_service.update_content_based_recommendations()
        
        # Rebuild preference vectors
        rebuilt_vectors = content_based_service.rebuild_preference_vectors()
        
        logger.info(f"Content-based filtering update completed: {analyzed_offers} offers, {updated_recommendations} recommendations, {rebuilt_vectors} vectors")
        return {
            'success': True,
            'analyzed_offers': analyzed_offers,
            'updated_recommendations': updated_recommendations,
            'rebuilt_vectors': rebuilt_vectors,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Content-based filtering update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.optimize_personalization_configs')
def optimize_personalization_configs(self):
    """
    Optimize personalization configurations for all tenants.
    
    This task analyzes personalization performance and
    optimizes configurations for better results.
    """
    try:
        logger.info("Starting personalization configuration optimization")
        
        # Get all tenants
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        tenants = User.objects.all()  # This would be filtered to actual tenants
        
        total_optimized = 0
        failed_tenants = []
        
        for tenant in tenants:
            try:
                optimization_result = routing_optimizer.optimize_personalization_config(tenant_id=tenant.id)
                if optimization_result.get('optimized_configs', 0) > 0:
                    total_optimized += optimization_result['optimized_configs']
            except Exception as e:
                logger.error(f"Failed to optimize personalization for tenant {tenant.id}: {e}")
                failed_tenants.append(tenant.id)
        
        logger.info(f"Personalization configuration optimization completed: {total_optimized} configs optimized")
        return {
            'success': True,
            'optimized_configs': total_optimized,
            'failed_tenants': failed_tenants,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Personalization configuration optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.process_contextual_signals')
def process_contextual_signals(self):
    """
    Process and update contextual signals.
    
    This task processes recent contextual signals and
    updates personalization models accordingly.
    """
    try:
        logger.info("Starting contextual signal processing")
        
        # Get recent contextual signals
        from ..models import ContextualSignal
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_signals = ContextualSignal.objects.filter(
            created_at__gte=cutoff_date
        ).select_related('user')
        
        processed_signals = 0
        failed_signals = 0
        
        for signal in recent_signals:
            try:
                # Process contextual signal
                if personalization_service:
                    personalization_service.process_contextual_signal(signal)
                    processed_signals += 1
                else:
                    failed_signals += 1
                    
            except Exception as e:
                logger.error(f"Failed to process contextual signal {signal.id}: {e}")
                failed_signals += 1
        
        logger.info(f"Contextual signal processing completed: {processed_signals} processed, {failed_signals} failed")
        return {
            'success': True,
            'processed_signals': processed_signals,
            'failed_signals': failed_signals,
            'total_signals': recent_signals.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Contextual signal processing failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.cleanup_expired_signals')
def cleanup_expired_signals(self):
    """
    Clean up expired contextual signals.
    
    This task removes expired contextual signals
    to maintain system performance.
    """
    try:
        logger.info("Starting contextual signal cleanup")
        
        from ..models import ContextualSignal
        
        # Delete expired signals
        deleted_count = ContextualSignal.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        logger.info(f"Contextual signal cleanup completed: {deleted_count} signals deleted")
        return {
            'success': True,
            'deleted_signals': deleted_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Contextual signal cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.calculate_personalization_metrics')
def calculate_personalization_metrics(self):
    """
    Calculate personalization performance metrics.
    
    This task calculates metrics for personalization effectiveness
    and generates insights for optimization.
    """
    try:
        logger.info("Starting personalization metrics calculation")
        
        from datetime import timedelta
        
        # Get recent personalization data
        from ..models import UserPreferenceVector, RoutingDecisionLog
        
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Calculate preference vector metrics
        preference_metrics = UserPreferenceVector.objects.filter(
            last_updated__gte=cutoff_date
        ).aggregate(
            total_vectors=Count('id'),
            avg_accuracy=Avg('accuracy_score'),
            avg_version=Avg('version')
        )
        
        # Calculate personalization rate
        personalization_rate = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        ).aggregate(
            total_decisions=Count('id'),
            personalized_decisions=Count('id', filter=Q(personalization_applied=True))
        )
        
        total_decisions = personalization_rate['total_decisions'] or 0
        personalized_decisions = personalization_rate['personalized_decisions'] or 0
        personalization_rate_percent = (personalized_decisions / total_decisions * 100) if total_decisions > 0 else 0
        
        # Generate insights
        insights = []
        
        if preference_metrics['avg_accuracy'] and preference_metrics['avg_accuracy'] < 0.7:
            insights.append({
                'type': 'accuracy_low',
                'message': 'Preference vector accuracy is low',
                'avg_accuracy': preference_metrics['avg_accuracy']
            })
        
        if personalization_rate_percent < 50:
            insights.append({
                'type': 'personalization_rate_low',
                'message': 'Personalization rate is low',
                'personalization_rate': personalization_rate_percent
            })
        
        logger.info(f"Personalization metrics calculation completed: {len(insights)} insights generated")
        return {
            'success': True,
            'preference_metrics': preference_metrics,
            'personalization_rate': personalization_rate_percent,
            'insights': insights,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Personalization metrics calculation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.train_ml_models')
def train_ml_models(self):
    """
    Train machine learning models for personalization.
    
    This task trains ML models for advanced personalization
    if machine learning is enabled.
    """
    try:
        logger.info("Starting ML model training")
        
        # Check if ML is enabled for any users
        from ..models import PersonalizationConfig
        
        ml_configs = PersonalizationConfig.objects.filter(
            machine_learning_enabled=True,
            is_active=True
        )
        
        if not ml_configs.exists():
            logger.info("No ML-enabled personalization configs found")
            return {
                'success': True,
                'message': 'No ML-enabled configs found',
                'completed_at': timezone.now().isoformat()
            }
        
        trained_models = 0
        failed_models = 0
        
        for config in ml_configs:
            try:
                # Train ML model for this user
                if personalization_service:
                    success = personalization_service.train_ml_model(config.user.id)
                    if success:
                        trained_models += 1
                    else:
                        failed_models += 1
                else:
                    failed_models += 1
                    
            except Exception as e:
                logger.error(f"Failed to train ML model for user {config.user.id}: {e}")
                failed_models += 1
        
        logger.info(f"ML model training completed: {trained_models} trained, {failed_models} failed")
        return {
            'success': True,
            'trained_models': trained_models,
            'failed_models': failed_models,
            'total_configs': ml_configs.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"ML model training failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.personalization.update_real_time_personalization')
def update_real_time_personalization(self):
    """
    Update real-time personalization data.
    
    This task processes real-time signals and updates
    personalization data for immediate use.
    """
    try:
        logger.info("Starting real-time personalization update")
        
        # Get users with real-time personalization enabled
        from ..models import PersonalizationConfig
        
        real_time_configs = PersonalizationConfig.objects.filter(
            real_time_enabled=True,
            is_active=True
        )
        
        updated_users = 0
        failed_users = 0
        
        for config in real_time_configs:
            try:
                # Update real-time personalization for this user
                if personalization_service:
                    personalization_service.update_real_time_personalization(config.user.id)
                    updated_users += 1
                else:
                    failed_users += 1
                    
            except Exception as e:
                logger.error(f"Failed to update real-time personalization for user {config.user.id}: {e}")
                failed_users += 1
        
        logger.info(f"Real-time personalization update completed: {updated_users} updated, {failed_users} failed")
        return {
            'success': True,
            'updated_users': updated_users,
            'failed_users': failed_users,
            'total_configs': real_time_configs.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Real-time personalization update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
