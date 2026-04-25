"""
api/ad_networks/webhooks.py
Webhook handling for ad networks module
SaaS-ready with tenant support
"""

import logging
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, AdNetworkWebhookLog, NetworkAPILog
)
from .choices import ConversionStatus, RewardStatus
from .services import ConversionService, RewardService
from .validators import SecurityValidator
from .constants import WEBHOOK_TIMEOUT, WEBHOOK_RETRY_LIMIT

logger = logging.getLogger(__name__)
User = get_user_model()


class WebhookEventType(Enum):
    """Webhook event types"""
    
    # Conversion events
    CONVERSION_APPROVED = "conversion.approved"
    CONVERSION_REJECTED = "conversion.rejected"
    CONVERSION_PENDING = "conversion.pending"
    CONVERSION_CHARGEBACK = "conversion.chargeback"
    
    # Offer events
    OFFER_CREATED = "offer.created"
    OFFER_UPDATED = "offer.updated"
    OFFER_EXPIRED = "offer.expired"
    OFFER_PAUSED = "offer.paused"
    OFFER_RESUMED = "offer.resumed"
    
    # Network events
    NETWORK_HEALTH_CHECK = "network.health_check"
    NETWORK_SYNC_COMPLETED = "network.sync_completed"
    NETWORK_SYNC_FAILED = "network.sync_failed"
    NETWORK_STATUS_CHANGED = "network.status_changed"
    
    # User events
    USER_ENGAGEMENT_STARTED = "user.engagement.started"
    USER_ENGAGEMENT_COMPLETED = "user.engagement.completed"
    USER_REWARD_EARNED = "user.reward.earned"
    USER_REWARD_PAID = "user.reward.paid"
    
    # System events
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_BACKUP_COMPLETED = "system.backup_completed"
    SYSTEM_ERROR = "system.error"


class WebhookProcessor:
    """Base webhook processor"""
    
    def __init__(self, network: AdNetwork):
        self.network = network
        self.tenant_id = network.tenant_id
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        try:
            secret = self.network.webhook_secret
            if not secret:
                logger.warning(f"No webhook secret configured for network {self.network.id}")
                return False
            
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def process_webhook(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook data"""
        try:
            # Log webhook
            self._log_webhook(event_type, data, 'received')
            
            # Route to appropriate handler
            handler = self._get_handler(event_type)
            if handler:
                result = handler(data)
                self._log_webhook(event_type, data, 'processed', result)
                return result
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                return {'success': False, 'error': 'No handler found'}
                
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            self._log_webhook(event_type, data, 'error', {'error': str(e)})
            return {'success': False, 'error': str(e)}
    
    def _get_handler(self, event_type: str) -> Optional[Callable]:
        """Get handler for event type"""
        handlers = {
            WebhookEventType.CONVERSION_APPROVED.value: self._handle_conversion_approved,
            WebhookEventType.CONVERSION_REJECTED.value: self._handle_conversion_rejected,
            WebhookEventType.CONVERSION_PENDING.value: self._handle_conversion_pending,
            WebhookEventType.CONVERSION_CHARGEBACK.value: self._handle_conversion_chargeback,
            WebhookEventType.OFFER_CREATED.value: self._handle_offer_created,
            WebhookEventType.OFFER_UPDATED.value: self._handle_offer_updated,
            WebhookEventType.OFFER_EXPIRED.value: self._handle_offer_expired,
            WebhookEventType.OFFER_PAUSED.value: self._handle_offer_paused,
            WebhookEventType.OFFER_RESUMED.value: self._handle_offer_resumed,
            WebhookEventType.NETWORK_HEALTH_CHECK.value: self._handle_network_health_check,
            WebhookEventType.NETWORK_SYNC_COMPLETED.value: self._handle_network_sync_completed,
            WebhookEventType.NETWORK_SYNC_FAILED.value: self._handle_network_sync_failed,
            WebhookEventType.NETWORK_STATUS_CHANGED.value: self._handle_network_status_changed,
            WebhookEventType.USER_ENGAGEMENT_STARTED.value: self._handle_user_engagement_started,
            WebhookEventType.USER_ENGAGEMENT_COMPLETED.value: self._handle_user_engagement_completed,
            WebhookEventType.USER_REWARD_EARNED.value: self._handle_user_reward_earned,
            WebhookEventType.USER_REWARD_PAID.value: self._handle_user_reward_paid,
        }
        
        return handlers.get(event_type)
    
    def _log_webhook(self, event_type: str, data: Dict[str, Any], 
                     status: str, result: Dict[str, Any] = None):
        """Log webhook event"""
        try:
            AdNetworkWebhookLog.objects.create(
                network=self.network,
                event_type=event_type,
                payload=data,
                status=status,
                response_data=result,
                processed_at=timezone.now(),
                tenant_id=self.tenant_id
            )
        except Exception as e:
            logger.error(f"Error logging webhook: {str(e)}")
    
    # Conversion handlers
    def _handle_conversion_approved(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversion approval"""
        try:
            conversion_id = data.get('conversion_id')
            payout = data.get('payout', 0)
            currency = data.get('currency', 'USD')
            
            if not conversion_id:
                return {'success': False, 'error': 'Missing conversion_id'}
            
            # Find conversion
            try:
                conversion = OfferConversion.objects.get(
                    external_id=conversion_id,
                    engagement__offer__ad_network=self.network,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                return {'success': False, 'error': 'Conversion not found'}
            
            # Update conversion
            conversion.conversion_status = ConversionStatus.APPROVED
            conversion.payout = payout
            conversion.currency = currency
            conversion.approved_at = timezone.now()
            conversion.save(update_fields=[
                'conversion_status', 'payout', 'currency', 'approved_at'
            ])
            
            # Create reward
            service = RewardService(tenant_id=self.tenant_id)
            reward_result = service.credit_reward(
                conversion.engagement,
                payout,
                currency,
                'Conversion approved via webhook'
            )
            
            return {
                'success': True,
                'conversion_id': conversion.id,
                'reward_id': reward_result.get('reward_id')
            }
            
        except Exception as e:
            logger.error(f"Error handling conversion approval: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_conversion_rejected(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversion rejection"""
        try:
            conversion_id = data.get('conversion_id')
            reason = data.get('reason', 'Rejected via webhook')
            
            if not conversion_id:
                return {'success': False, 'error': 'Missing conversion_id'}
            
            # Find conversion
            try:
                conversion = OfferConversion.objects.get(
                    external_id=conversion_id,
                    engagement__offer__ad_network=self.network,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                return {'success': False, 'error': 'Conversion not found'}
            
            # Update conversion
            conversion.conversion_status = ConversionStatus.REJECTED
            conversion.rejected_at = timezone.now()
            conversion.rejection_reason = reason
            conversion.save(update_fields=[
                'conversion_status', 'rejected_at', 'rejection_reason'
            ])
            
            return {
                'success': True,
                'conversion_id': conversion.id
            }
            
        except Exception as e:
            logger.error(f"Error handling conversion rejection: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_conversion_pending(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversion pending"""
        try:
            conversion_id = data.get('conversion_id')
            payout = data.get('payout', 0)
            currency = data.get('currency', 'USD')
            
            if not conversion_id:
                return {'success': False, 'error': 'Missing conversion_id'}
            
            # Find conversion
            try:
                conversion = OfferConversion.objects.get(
                    external_id=conversion_id,
                    engagement__offer__ad_network=self.network,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                return {'success': False, 'error': 'Conversion not found'}
            
            # Update conversion
            conversion.conversion_status = ConversionStatus.PENDING
            conversion.payout = payout
            conversion.currency = currency
            conversion.save(update_fields=['conversion_status', 'payout', 'currency'])
            
            return {
                'success': True,
                'conversion_id': conversion.id
            }
            
        except Exception as e:
            logger.error(f"Error handling conversion pending: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_conversion_chargeback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversion chargeback"""
        try:
            conversion_id = data.get('conversion_id')
            reason = data.get('reason', 'Chargeback via webhook')
            
            if not conversion_id:
                return {'success': False, 'error': 'Missing conversion_id'}
            
            # Find conversion
            try:
                conversion = OfferConversion.objects.get(
                    external_id=conversion_id,
                    engagement__offer__ad_network=self.network,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                return {'success': False, 'error': 'Conversion not found'}
            
            # Update conversion
            conversion.conversion_status = ConversionStatus.CHARGEBACK
            conversion.chargeback_at = timezone.now()
            conversion.save(update_fields=['conversion_status', 'chargeback_at'])
            
            # Reverse reward if exists
            try:
                reward = OfferReward.objects.get(
                    engagement=conversion.engagement,
                    tenant_id=self.tenant_id
                )
                service = RewardService(tenant_id=self.tenant_id)
                service.reverse_reward(reward.id, reason)
            except OfferReward.DoesNotExist:
                pass
            
            return {
                'success': True,
                'conversion_id': conversion.id
            }
            
        except Exception as e:
            logger.error(f"Error handling conversion chargeback: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Offer handlers
    def _handle_offer_created(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offer creation"""
        try:
            # This would create or update an offer based on webhook data
            # For now, just log
            logger.info(f"Offer created via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling offer creation: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_offer_updated(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offer update"""
        try:
            # This would update an offer based on webhook data
            # For now, just log
            logger.info(f"Offer updated via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling offer update: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_offer_expired(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offer expiration"""
        try:
            offer_id = data.get('offer_id')
            
            if not offer_id:
                return {'success': False, 'error': 'Missing offer_id'}
            
            # Find and expire offer
            try:
                offer = Offer.objects.get(
                    external_id=offer_id,
                    ad_network=self.network,
                    tenant_id=self.tenant_id
                )
                offer.status = 'expired'
                offer.save(update_fields=['status'])
                
                return {'success': True, 'offer_id': offer.id}
                
            except Offer.DoesNotExist:
                return {'success': False, 'error': 'Offer not found'}
                
        except Exception as e:
            logger.error(f"Error handling offer expiration: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_offer_paused(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offer pause"""
        try:
            offer_id = data.get('offer_id')
            
            if not offer_id:
                return {'success': False, 'error': 'Missing offer_id'}
            
            # Find and pause offer
            try:
                offer = Offer.objects.get(
                    external_id=offer_id,
                    ad_network=self.network,
                    tenant_id=self.tenant_id
                )
                offer.status = 'paused'
                offer.save(update_fields=['status'])
                
                return {'success': True, 'offer_id': offer.id}
                
            except Offer.DoesNotExist:
                return {'success': False, 'error': 'Offer not found'}
                
        except Exception as e:
            logger.error(f"Error handling offer pause: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_offer_resumed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle offer resume"""
        try:
            offer_id = data.get('offer_id')
            
            if not offer_id:
                return {'success': False, 'error': 'Missing offer_id'}
            
            # Find and resume offer
            try:
                offer = Offer.objects.get(
                    external_id=offer_id,
                    ad_network=self.network,
                    tenant_id=self.tenant_id
                )
                offer.status = 'active'
                offer.save(update_fields=['status'])
                
                return {'success': True, 'offer_id': offer.id}
                
            except Offer.DoesNotExist:
                return {'success': False, 'error': 'Offer not found'}
                
        except Exception as e:
            logger.error(f"Error handling offer resume: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # Network handlers
    def _handle_network_health_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network health check"""
        try:
            is_healthy = data.get('is_healthy', False)
            response_time = data.get('response_time_ms', 0)
            error = data.get('error', '')
            
            # Update network health
            self.network.is_healthy = is_healthy
            self.network.last_health_check = timezone.now()
            self.network.save(update_fields=['is_healthy', 'last_health_check'])
            
            return {
                'success': True,
                'is_healthy': is_healthy,
                'response_time_ms': response_time
            }
            
        except Exception as e:
            logger.error(f"Error handling network health check: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_network_sync_completed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network sync completion"""
        try:
            offers_synced = data.get('offers_synced', 0)
            sync_time = data.get('sync_time_seconds', 0)
            
            # Update network sync status
            self.network.last_sync = timezone.now()
            self.network.save(update_fields=['last_sync'])
            
            return {
                'success': True,
                'offers_synced': offers_synced,
                'sync_time_seconds': sync_time
            }
            
        except Exception as e:
            logger.error(f"Error handling network sync completion: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_network_sync_failed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network sync failure"""
        try:
            error = data.get('error', 'Unknown error')
            
            # Log sync failure
            logger.error(f"Network sync failed for {self.network.name}: {error}")
            
            return {'success': True, 'error': error}
            
        except Exception as e:
            logger.error(f"Error handling network sync failure: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_network_status_changed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network status change"""
        try:
            new_status = data.get('status')
            
            if not new_status:
                return {'success': False, 'error': 'Missing status'}
            
            # Update network status
            self.network.status = new_status
            self.network.save(update_fields=['status'])
            
            return {
                'success': True,
                'new_status': new_status
            }
            
        except Exception as e:
            logger.error(f"Error handling network status change: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    # User handlers
    def _handle_user_engagement_started(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user engagement start"""
        try:
            # This would handle user engagement start
            # For now, just log
            logger.info(f"User engagement started via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling user engagement start: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_user_engagement_completed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user engagement completion"""
        try:
            # This would handle user engagement completion
            # For now, just log
            logger.info(f"User engagement completed via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling user engagement completion: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_user_reward_earned(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user reward earned"""
        try:
            # This would handle user reward earned
            # For now, just log
            logger.info(f"User reward earned via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling user reward earned: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_user_reward_paid(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user reward paid"""
        try:
            # This would handle user reward paid
            # For now, just log
            logger.info(f"User reward paid via webhook: {data}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error handling user reward paid: {str(e)}")
            return {'success': False, 'error': str(e)}


class WebhookManager:
    """Manager for webhook processing"""
    
    def __init__(self):
        self.processors: Dict[int, WebhookProcessor] = {}
        self.retry_queue = []
    
    def get_processor(self, network_id: int) -> Optional[WebhookProcessor]:
        """Get webhook processor for network"""
        if network_id not in self.processors:
            try:
                network = AdNetwork.objects.get(id=network_id)
                self.processors[network_id] = WebhookProcessor(network)
            except AdNetwork.DoesNotExist:
                return None
        
        return self.processors.get(network_id)
    
    def process_webhook(self, network_id: int, event_type: str, 
                        payload: bytes, signature: str) -> Dict[str, Any]:
        """Process webhook for network"""
        try:
            processor = self.get_processor(network_id)
            if not processor:
                return {'success': False, 'error': 'Network not found'}
            
            # Verify signature
            if not processor.verify_signature(payload, signature):
                return {'success': False, 'error': 'Invalid signature'}
            
            # Parse payload
            try:
                data = json.loads(payload.decode('utf-8'))
            except json.JSONDecodeError:
                return {'success': False, 'error': 'Invalid JSON payload'}
            
            # Process webhook
            result = processor.process_webhook(event_type, data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def add_to_retry_queue(self, network_id: int, event_type: str,
                          payload: bytes, signature: str, retry_count: int = 0):
        """Add webhook to retry queue"""
        if retry_count < WEBHOOK_RETRY_LIMIT:
            self.retry_queue.append({
                'network_id': network_id,
                'event_type': event_type,
                'payload': payload,
                'signature': signature,
                'retry_count': retry_count,
                'next_retry': timezone.now() + timedelta(minutes=2 ** retry_count)
            })
    
    def process_retry_queue(self):
        """Process webhook retry queue"""
        now = timezone.now()
        remaining = []
        
        for webhook_data in self.retry_queue:
            if webhook_data['next_retry'] <= now:
                try:
                    result = self.process_webhook(
                        webhook_data['network_id'],
                        webhook_data['event_type'],
                        webhook_data['payload'],
                        webhook_data['signature']
                    )
                    
                    if not result['success']:
                        # Add back to queue with increased retry count
                        self.add_to_retry_queue(
                            webhook_data['network_id'],
                            webhook_data['event_type'],
                            webhook_data['payload'],
                            webhook_data['signature'],
                            webhook_data['retry_count'] + 1
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing webhook retry: {str(e)}")
                    # Add back to queue with increased retry count
                    self.add_to_retry_queue(
                        webhook_data['network_id'],
                        webhook_data['event_type'],
                        webhook_data['payload'],
                        webhook_data['signature'],
                        webhook_data['retry_count'] + 1
                    )
            else:
                remaining.append(webhook_data)
        
        self.retry_queue = remaining


# Global webhook manager instance
webhook_manager = WebhookManager()


# Webhook view functions
@csrf_exempt
@require_http_methods(["POST"])
def webhook_receiver(request, network_id: int):
    """Receive webhook for a specific network"""
    try:
        # Get network
        try:
            network = AdNetwork.objects.get(id=network_id)
        except AdNetwork.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Network not found'},
                status=404
            )
        
        # Check if webhooks are enabled
        if not network.supports_webhook:
            return JsonResponse(
                {'success': False, 'error': 'Webhooks not supported'},
                status=400
            )
        
        # Get event type from headers
        event_type = request.META.get('HTTP_X_EVENT_TYPE')
        if not event_type:
            return JsonResponse(
                {'success': False, 'error': 'Missing event type'},
                status=400
            )
        
        # Get signature
        signature = request.META.get('HTTP_X_SIGNATURE')
        if not signature:
            return JsonResponse(
                {'success': False, 'error': 'Missing signature'},
                status=400
            )
        
        # Get payload
        payload = request.body
        
        # Process webhook
        result = webhook_manager.process_webhook(
            network_id, event_type, payload, signature
        )
        
        if result['success']:
            return JsonResponse(result, status=200)
        else:
            # Add to retry queue
            webhook_manager.add_to_retry_queue(
                network_id, event_type, payload, signature
            )
            return JsonResponse(result, status=500)
            
    except Exception as e:
        logger.error(f"Error in webhook receiver: {str(e)}")
        return JsonResponse(
            {'success': False, 'error': 'Internal server error'},
            status=500
        )


@csrf_exempt
@require_http_methods(["GET"])
def webhook_status(request, network_id: int):
    """Get webhook status for a network"""
    try:
        # Get network
        try:
            network = AdNetwork.objects.get(id=network_id)
        except AdNetwork.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Network not found'},
                status=404
            )
        
        # Get recent webhook logs
        recent_logs = AdNetworkWebhookLog.objects.filter(
            network=network,
            processed_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-processed_at')[:10]
        
        # Calculate stats
        total_logs = AdNetworkWebhookLog.objects.filter(
            network=network,
            processed_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        successful_logs = AdNetworkWebhookLog.objects.filter(
            network=network,
            status='processed',
            processed_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        success_rate = (successful_logs / total_logs * 100) if total_logs > 0 else 0
        
        return JsonResponse({
            'success': True,
            'webhook_configured': bool(network.webhook_secret),
            'webhook_enabled': network.supports_webhook,
            'stats': {
                'total_logs_24h': total_logs,
                'successful_logs_24h': successful_logs,
                'success_rate_24h': round(success_rate, 2)
            },
            'recent_logs': [
                {
                    'event_type': log.event_type,
                    'status': log.status,
                    'processed_at': log.processed_at.isoformat()
                }
                for log in recent_logs
            ]
        })
        
    except Exception as e:
        logger.error(f"Error in webhook status: {str(e)}")
        return JsonResponse(
            {'success': False, 'error': 'Internal server error'},
            status=500
        )


# Export all classes and functions
__all__ = [
    # Enums
    'WebhookEventType',
    
    # Classes
    'WebhookProcessor',
    'WebhookManager',
    
    # Global instance
    'webhook_manager',
    
    # View functions
    'webhook_receiver',
    'webhook_status'
]
