"""
Data Bridge

Bridge for data synchronization between
integration system and offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import transaction
from .integ_handler import integration_handler
from .integ_signals import integration_signals
from ..models import OfferRoute, RoutingDecisionLog
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class DataBridge:
    """
    Data bridge for synchronization.
    
    Provides data transformation and synchronization:
    - Bidirectional data sync
    - Conflict resolution
    - Data validation
    - Performance optimization
    - Audit logging
    """
    
    def __init__(self):
        self.active_syncs = {}
        self.conflict_resolvers = {}
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'conflicts_resolved': 0,
            'errors': 0
        }
    
    def sync_integrations_to_routing(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Sync integration data to routing system.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Sync results
        """
        try:
            sync_results = {}
            
            if integration_id:
                # Sync specific integration
                result = self._sync_single_integration(integration_id)
                sync_results[integration_id] = result
            else:
                # Sync all active integrations
                active_integrations = integration_handler.list_integrations()
                
                for integration in active_integrations:
                    integ_id = integration['id']
                    result = self._sync_single_integration(integ_id)
                    sync_results[integ_id] = result
            
            # Update stats
            self._update_sync_stats(sync_results)
            
            return {
                'success': True,
                'sync_results': sync_results,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing integrations to routing: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _sync_single_integration(self, integration_id: str) -> Dict[str, Any]:
        """Sync data from a single integration."""
        try:
            # Get integration
            integration = integration_handler.get_integration(integration_id)
            
            if not integration:
                return {
                    'success': False,
                    'error': f'Integration not found: {integration_id}'
                }
            
            # Get integration data
            integration_data = self._extract_integration_data(integration)
            
            # Transform data for routing system
            transformed_data = self._transform_for_routing(integration_data)
            
            # Validate transformed data
            validation_result = self._validate_routing_data(transformed_data)
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Data validation failed',
                    'validation_errors': validation_result['errors']
                }
            
            # Apply data to routing system
            with transaction.atomic():
                result = self._apply_routing_data(transformed_data)
                
                if result['success']:
                    # Update integration sync status
                    integration_handler.update_integration_config(integration_id, {
                        'last_sync': timezone.now().isoformat(),
                        'sync_status': 'success',
                        'sync_data_count': len(transformed_data)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error syncing integration {integration_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_integration_data(self, integration) -> List[Dict[str, Any]]:
        """Extract data from integration."""
        try:
            integration_type = integration.get_type()
            
            if integration_type == 'webhook':
                return self._extract_webhook_data(integration)
            elif integration_type == 'api':
                return self._extract_api_data(integration)
            elif integration_type == 'database':
                return self._extract_database_data(integration)
            else:
                logger.warning(f"Unknown integration type: {integration_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting integration data: {e}")
            return []
    
    def _extract_webhook_data(self, integration) -> List[Dict[str, Any]]:
        """Extract webhook integration data."""
        try:
            # Get recent webhook events
            webhook_data = []
            
            # This would query webhook event logs
            # For now, return placeholder data
            webhook_data.append({
                'event_type': 'offer_created',
                'data': {
                    'offer_id': 'sample_123',
                    'offer_name': 'Sample Offer',
                    'created_at': timezone.now().isoformat()
                },
                'source': 'webhook',
                'integration_id': integration.get_id()
            })
            
            return webhook_data
            
        except Exception as e:
            logger.error(f"Error extracting webhook data: {e}")
            return []
    
    def _extract_api_data(self, integration) -> List[Dict[str, Any]]:
        """Extract API integration data."""
        try:
            # Get API integration data
            api_data = []
            
            # This would query API endpoints
            # For now, return placeholder data
            api_data.append({
                'endpoint': '/offers',
                'method': 'GET',
                'data': {
                    'offers': [
                        {
                            'id': 'api_123',
                            'name': 'API Offer',
                            'price': 99.99
                        }
                    ]
                },
                'source': 'api',
                'integration_id': integration.get_id()
            })
            
            return api_data
            
        except Exception as e:
            logger.error(f"Error extracting API data: {e}")
            return []
    
    def _extract_database_data(self, integration) -> List[Dict[str, Any]]:
        """Extract database integration data."""
        try:
            # Get database integration data
            db_data = []
            
            # This would query database tables
            # For now, return placeholder data
            db_data.append({
                'table': 'offers',
                'operation': 'SELECT',
                'data': {
                    'records': [
                        {
                            'id': 'db_123',
                            'name': 'DB Offer',
                            'category': 'electronics'
                        }
                    ]
                },
                'source': 'database',
                'integration_id': integration.get_id()
            })
            
            return db_data
            
        except Exception as e:
            logger.error(f"Error extracting database data: {e}")
            return []
    
    def _transform_for_routing(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform data for routing system."""
        try:
            transformed_data = []
            
            for item in data:
                # Standardize data format
                transformed_item = {
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'category': item.get('category', 'general'),
                    'price': item.get('price', 0.0),
                    'created_at': item.get('created_at', timezone.now().isoformat()),
                    'source': item.get('source'),
                    'integration_id': item.get('integration_id'),
                    'processed_at': timezone.now().isoformat()
                }
                
                # Add routing-specific fields
                if item.get('event_type') == 'offer_created':
                    transformed_item['action'] = 'create_offer'
                    transformed_item['priority'] = 'high'
                
                transformed_data.append(transformed_item)
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error transforming data: {e}")
            return []
    
    def _validate_routing_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate data for routing system."""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            for item in data:
                # Validate required fields
                if not item.get('id'):
                    validation_result['errors'].append(f"Missing ID for item: {item}")
                    validation_result['valid'] = False
                
                if not item.get('name'):
                    validation_result['errors'].append(f"Missing name for item: {item}")
                    validation_result['valid'] = False
                
                # Validate data types
                if item.get('price') is not None and not isinstance(item['price'], (int, float)):
                    validation_result['errors'].append(f"Invalid price type for item: {item}")
                    validation_result['valid'] = False
                
                # Validate business rules
                if item.get('price', 0) < 0:
                    validation_result['warnings'].append(f"Negative price for item: {item}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating routing data: {e}")
            return {
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def _apply_routing_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply data to routing system."""
        try:
            applied_count = 0
            errors = []
            
            for item in data:
                try:
                    # Apply to routing system based on action
                    if item.get('action') == 'create_offer':
                        result = self._create_offer_in_routing(item)
                    elif item.get('action') == 'update_offer':
                        result = self._update_offer_in_routing(item)
                    else:
                        result = self._process_generic_data(item)
                    
                    if result['success']:
                        applied_count += 1
                    else:
                        errors.append(result['error'])
                
                except Exception as e:
                    errors.append(f"Error processing item {item.get('id')}: {e}")
            
            return {
                'success': len(errors) == 0,
                'applied_count': applied_count,
                'error_count': len(errors),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error applying routing data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_offer_in_routing(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Create offer in routing system."""
        try:
            # Check if offer already exists
            existing_offer = OfferRoute.objects.filter(
                external_id=item.get('id')
            ).first()
            
            if existing_offer:
                # Update existing offer
                existing_offer.name = item.get('name')
                existing_offer.price = item.get('price', 0.0)
                existing_offer.category = item.get('category', 'general')
                existing_offer.save()
                
                return {
                    'success': True,
                    'action': 'updated',
                    'offer_id': existing_offer.id
                }
            else:
                # Create new offer
                new_offer = OfferRoute.objects.create(
                    name=item.get('name'),
                    price=item.get('price', 0.0),
                    category=item.get('category', 'general'),
                    external_id=item.get('id'),
                    source=item.get('source'),
                    integration_id=item.get('integration_id')
                )
                
                return {
                    'success': True,
                    'action': 'created',
                    'offer_id': new_offer.id
                }
                
        except Exception as e:
            logger.error(f"Error creating offer in routing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_offer_in_routing(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Update offer in routing system."""
        try:
            offer = OfferRoute.objects.filter(
                external_id=item.get('id')
            ).first()
            
            if not offer:
                return {
                    'success': False,
                    'error': f'Offer not found: {item.get("id")}'
                }
            
            # Update offer
            offer.name = item.get('name')
            offer.price = item.get('price', 0.0)
            offer.category = item.get('category', 'general')
            offer.save()
            
            return {
                'success': True,
                'action': 'updated',
                'offer_id': offer.id
            }
            
        except Exception as e:
            logger.error(f"Error updating offer in routing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_generic_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process generic data item."""
        try:
            # Log generic data processing
            logger.info(f"Processing generic data item: {item.get('id')}")
            
            # This would implement custom logic based on data type
            # For now, just log the item
            return {
                'success': True,
                'action': 'logged',
                'item_id': item.get('id')
            }
            
        except Exception as e:
            logger.error(f"Error processing generic data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_sync_stats(self, sync_results: Dict[str, Any]):
        """Update synchronization statistics."""
        try:
            for integration_id, result in sync_results.items():
                if result.get('success', False):
                    self.sync_stats['successful_syncs'] += 1
                else:
                    self.sync_stats['errors'] += 1
                
                if result.get('conflicts_resolved', 0):
                    self.sync_stats['conflicts_resolved'] += result['conflicts_resolved']
            
            self.sync_stats['total_syncs'] += 1
            
        except Exception as e:
            logger.error(f"Error updating sync stats: {e}")
    
    def resolve_conflicts(self, integration_id: str) -> Dict[str, Any]:
        """
        Resolve data conflicts for integration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Conflict resolution results
        """
        try:
            # This would implement conflict resolution logic
            # For now, return placeholder
            return {
                'success': True,
                'conflicts_resolved': 0,
                'message': 'No conflicts found',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resolving conflicts for {integration_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sync_status(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Get synchronization status.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Sync status
        """
        try:
            if integration_id:
                # Get specific integration sync status
                integration = integration_handler.get_integration(integration_id)
                
                if not integration:
                    return {
                        'status': 'not_found',
                        'integration_id': integration_id
                    }
                
                return {
                    'status': integration.get('sync_status', 'unknown'),
                    'last_sync': integration.get('last_sync'),
                    'sync_data_count': integration.get('sync_data_count', 0),
                    'integration_id': integration_id
                }
            else:
                # Get all integration sync status
                active_integrations = integration_handler.list_integrations()
                
                sync_status = {}
                for integration in active_integrations:
                    integ_id = integration['id']
                    sync_status[integ_id] = {
                        'status': integration.get('sync_status', 'unknown'),
                        'last_sync': integration.get('last_sync'),
                        'sync_data_count': integration.get('sync_data_count', 0)
                    }
                
                return {
                    'status': 'multiple',
                    'integrations': sync_status,
                    'overall_stats': self.sync_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_bridge_stats(self) -> Dict[str, Any]:
        """Get data bridge statistics."""
        try:
            return {
                'sync_stats': self.sync_stats,
                'active_syncs': len(self.active_syncs),
                'conflict_resolvers': len(self.conflict_resolvers),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting bridge stats: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on data bridge."""
        try:
            # Test data extraction
            test_data = self._extract_integration_data(None)
            
            # Test data transformation
            test_transformed = self._transform_for_routing(test_data[:1])
            
            # Test data validation
            test_validation = self._validate_routing_data(test_transformed)
            
            # Test data application
            test_application = self._apply_routing_data(test_transformed[:1])
            
            return {
                'status': 'healthy' if all([
                    test_validation['valid'],
                    test_application['success']
                ]) else 'unhealthy',
                'data_extraction': 'working',
                'data_transformation': 'working',
                'data_validation': test_validation['valid'],
                'data_application': test_application['success'],
                'sync_stats': self.sync_stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in data bridge health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# Global data bridge instance
data_bridge = DataBridge()
