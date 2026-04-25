"""
Configuration Viewsets for Offer Routing System

This module contains viewsets for managing routing configurations,
feature flags, and personalization settings.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ..models import RoutingConfig, PersonalizationConfig
from ..services.config import config_service
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, ConfigurationError

User = get_user_model()


class RoutingConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing routing configurations.
    
    Provides CRUD operations for routing configurations
    with validation and management capabilities.
    """
    
    queryset = RoutingConfig.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter configs by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('key')
    
    @action(detail=False, methods=['get'])
    def current_config(self, request):
        """Get current routing configuration."""
        try:
            config = config_service.get_routing_config(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'config': config
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_config_value(self, request):
        """Update a specific configuration value."""
        try:
            key = request.data.get('key')
            value = request.data.get('value')
            
            if not key or value is None:
                return Response({
                    'success': False,
                    'error': 'key and value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success = config_service.update_config_value(
                tenant_id=request.user.id,
                key=key,
                value=value
            )
            
            if success:
                return Response({
                    'success': True,
                    'key': key,
                    'value': value,
                    'updated_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to update configuration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def feature_flags(self, request):
        """Get feature flags for the tenant."""
        try:
            feature_flags = config_service.get_feature_flags(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'feature_flags': feature_flags
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def toggle_feature(self, request):
        """Toggle a feature flag."""
        try:
            feature = request.data.get('feature')
            enabled = request.data.get('enabled')
            
            if not feature or enabled is None:
                return Response({
                    'success': False,
                    'error': 'feature and enabled are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update feature flag
            success = config_service.update_config_value(
                tenant_id=request.user.id,
                key=feature,
                value=enabled
            )
            
            if success:
                return Response({
                    'success': True,
                    'feature': feature,
                    'enabled': enabled,
                    'updated_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to toggle feature'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_config(self, request):
        """Validate configuration data."""
        try:
            config_data = request.data.get('config', {})
            
            if not config_data:
                return Response({
                    'success': False,
                    'error': 'config data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validation_result = config_service.validate_configuration(config_data)
            
            return Response({
                'success': True,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_configuration(self, request):
        """Optimize routing configuration."""
        try:
            optimization_results = config_service.optimize_configuration(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'optimization_results': optimization_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def export_config(self, request):
        """Export current configuration."""
        try:
            export_data = config_service.export_configuration(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'export_data': export_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def import_config(self, request):
        """Import configuration data."""
        try:
            config_data = request.data.get('config', {})
            
            if not config_data:
                return Response({
                    'success': False,
                    'error': 'config data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success = config_service.import_configuration(
                tenant_id=request.user.id,
                import_data=config_data
            )
            
            if success:
                return Response({
                    'success': True,
                    'imported_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to import configuration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def reset_config(self, request):
        """Reset configuration to defaults."""
        try:
            success = config_service.reset_configuration(tenant_id=request.user.id)
            
            if success:
                return Response({
                    'success': True,
                    'reset_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to reset configuration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def config_history(self, request):
        """Get configuration change history."""
        try:
            days = int(request.query_params.get('days', 30))
            
            history = config_service.get_configuration_history(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'period_days': days,
                'history': history
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def backup_config(self, request):
        """Backup current configuration."""
        try:
            success = config_service.backup_configuration(tenant_id=request.user.id)
            
            if success:
                return Response({
                    'success': True,
                    'backed_up_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to backup configuration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def restore_config(self, request):
        """Restore configuration from backup."""
        try:
            backup_data = request.data.get('backup_data')
            
            if not backup_data:
                return Response({
                    'success': False,
                    'error': 'backup_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success = config_service.restore_configuration(
                tenant_id=request.user.id,
                backup_data=backup_data
            )
            
            if success:
                return Response({
                    'success': True,
                    'restored_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to restore configuration'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PersonalizationConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing personalization configurations.
    
    Provides CRUD operations for personalization configurations
    with validation and management capabilities.
    """
    
    queryset = PersonalizationConfig.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter configs by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def user_config(self, request):
        """Get personalization config for a specific user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            config = config_service.get_personalization_config(user_id)
            
            if config:
                return Response({
                    'success': True,
                    'config': {
                        'user_id': config.user.id,
                        'algorithm': config.algorithm,
                        'collaborative_weight': float(config.collaborative_weight),
                        'content_based_weight': float(config.content_based_weight),
                        'hybrid_weight': float(config.hybrid_weight),
                        'min_affinity_score': float(config.min_affinity_score),
                        'max_offers_per_user': config.max_offers_per_user,
                        'diversity_factor': float(config.diversity_factor),
                        'freshness_weight': float(config.freshness_weight),
                        'new_user_days': config.new_user_days,
                        'active_user_days': config.active_user_days,
                        'premium_user_multiplier': float(config.premium_user_multiplier),
                        'real_time_enabled': config.real_time_enabled,
                        'context_signals_enabled': config.context_signals_enabled,
                        'real_time_weight': float(config.real_time_weight),
                        'machine_learning_enabled': config.machine_learning_enabled,
                        'ml_model_path': config.ml_model_path,
                        'ml_update_frequency': config.ml_update_frequency,
                        'is_active': config.is_active,
                        'created_at': config.created_at.isoformat(),
                        'updated_at': config.updated_at.isoformat()
                    }
                })
            else:
                return Response({
                    'success': False,
                    'error': 'No personalization config found for this user'
                }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_user_config(self, request):
        """Update personalization config for a user."""
        try:
            user_id = request.data.get('user_id')
            config_data = request.data.get('config', {})
            
            if not user_id or not config_data:
                return Response({
                    'success': False,
                    'error': 'user_id and config are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            success = config_service.update_personalization_config(
                user_id=user_id,
                config_data=config_data
            )
            
            if success:
                return Response({
                    'success': True,
                    'user_id': user_id,
                    'updated_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to update personalization config'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_default_config(self, request):
        """Create default personalization config for a user."""
        try:
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            config_data = {
                'algorithm': 'hybrid',
                'collaborative_weight': 0.4,
                'content_based_weight': 0.3,
                'hybrid_weight': 0.3,
                'min_affinity_score': 0.1,
                'max_offers_per_user': 50,
                'diversity_factor': 0.2,
                'freshness_weight': 0.1,
                'new_user_days': 7,
                'active_user_days': 30,
                'premium_user_multiplier': 1.5,
                'real_time_enabled': True,
                'context_signals_enabled': True,
                'real_time_weight': 0.5,
                'machine_learning_enabled': False,
                'ml_update_frequency': 24
            }
            
            success = config_service.update_personalization_config(
                user_id=user_id,
                config_data=config_data
            )
            
            if success:
                return Response({
                    'success': True,
                    'user_id': user_id,
                    'config_data': config_data,
                    'created_at': timezone.now().isoformat()
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to create default config'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def config_analytics(self, request):
        """Get analytics for personalization configurations."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get config statistics
            configs = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_configs=Count('id'),
                active_configs=Count('id', filter=Q(is_active=True)),
                ml_enabled_configs=Count('id', filter=Q(machine_learning_enabled=True)),
                real_time_configs=Count('id', filter=Q(real_time_enabled=True))
            )
            
            # Get algorithm distribution
            algorithm_distribution = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).values('algorithm').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'config_stats': configs,
                'algorithm_distribution': list(algorithm_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_algorithms(self, request):
        """Get supported personalization algorithms."""
        try:
            algorithms = [
                {
                    'value': 'collaborative',
                    'label': 'Collaborative Filtering',
                    'description': 'Uses user similarity to recommend offers'
                },
                {
                    'value': 'content_based',
                    'label': 'Content-Based Filtering',
                    'description': 'Uses offer characteristics to recommend offers'
                },
                {
                    'value': 'hybrid',
                    'label': 'Hybrid Approach',
                    'description': 'Combines collaborative and content-based methods'
                },
                {
                    'value': 'rule_based',
                    'label': 'Rule-Based',
                    'description': 'Uses predefined rules for recommendations'
                }
            ]
            
            return Response({
                'success': True,
                'algorithms': algorithms
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_create_configs(self, request):
        """Create default configs for multiple users."""
        try:
            user_ids = request.data.get('user_ids', [])
            
            if not user_ids:
                return Response({
                    'success': False,
                    'error': 'user_ids is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            created_count = 0
            failed_users = []
            
            for user_id in user_ids:
                try:
                    # Verify user belongs to tenant
                    user = User.objects.get(id=user_id)
                    if user.tenant != request.user:
                        failed_users.append({'user_id': user_id, 'error': 'User not in tenant'})
                        continue
                    
                    # Create default config
                    config_data = {
                        'algorithm': 'hybrid',
                        'collaborative_weight': 0.4,
                        'content_based_weight': 0.3,
                        'hybrid_weight': 0.3,
                        'min_affinity_score': 0.1,
                        'max_offers_per_user': 50,
                        'diversity_factor': 0.2,
                        'freshness_weight': 0.1,
                        'new_user_days': 7,
                        'active_user_days': 30,
                        'premium_user_multiplier': 1.5,
                        'real_time_enabled': True,
                        'context_signals_enabled': True,
                        'real_time_weight': 0.5,
                        'machine_learning_enabled': False,
                        'ml_update_frequency': 24
                    }
                    
                    success = config_service.update_personalization_config(
                        user_id=user_id,
                        config_data=config_data
                    )
                    
                    if success:
                        created_count += 1
                    else:
                        failed_users.append({'user_id': user_id, 'error': 'Failed to create config'})
                        
                except User.DoesNotExist:
                    failed_users.append({'user_id': user_id, 'error': 'User not found'})
                except Exception as e:
                    failed_users.append({'user_id': user_id, 'error': str(e)})
            
            return Response({
                'success': True,
                'total_users': len(user_ids),
                'created_count': created_count,
                'failed_users': failed_users
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
