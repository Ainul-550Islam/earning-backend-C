"""Inbound Webhook Service

This module provides inbound webhook processing with verification and routing.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction

from ...models import InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError
from ...constants import InboundSource, ErrorType
from ...exceptions import WebhookDispatchError

logger = logging.getLogger(__name__)


class InboundWebhookService:
    """Service for processing inbound webhooks with verification and routing."""
    
    def __init__(self):
        """Initialize the inbound webhook service."""
        self.logger = logger
    
    def process_inbound_webhook(self, inbound: InboundWebhook, payload, headers: Dict[str, Any], signature: str = None, ip_address: str = None, max_age_seconds: int = None, allowed_ips: List[str] = None) -> Dict[str, Any]:
        """
        Process an inbound webhook request.
        
        Args:
            inbound: The inbound webhook configuration
            payload: The webhook payload (dict, or a raw JSON string)
            headers: HTTP headers from the request
            signature: Optional pre-extracted signature. If not given, it's
                extracted from `headers` using inbound.source's header name.
            ip_address: Optional IP address of the sender
            max_age_seconds: Optional freshness window checked against a
                source-specific timestamp header, independent of signature
                validity (distinct 'Timestamp too old' error).
            allowed_ips: Optional explicit IP allowlist for this call.
            
        Returns:
            Dictionary with processing results
        """
        try:
            if not inbound.is_active:
                return {'success': False, 'error': 'Webhook is inactive'}

            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (ValueError, TypeError):
                    return {'success': False, 'error': 'Invalid JSON payload'}

            headers = headers or {}

            if allowed_ips and ip_address:
                if not self._check_ip_whitelist_list(ip_address, allowed_ips):
                    return {'success': False, 'error': 'IP address not allowed'}

            if signature is None:
                signature = self._extract_signature_from_headers(inbound.source, headers)
                signature_was_extracted = True
            else:
                signature_was_extracted = False
            if not signature:
                return {'success': False, 'error': 'Missing signature'}

            signature_valid = True
            if inbound.secret:
                if signature_was_extracted:
                    # Self-extracted via _extract_signature_from_headers:
                    # verify with the headers-based (sha256=) convention.
                    signature_valid = self._verify_signature_headers(inbound, payload, headers)
                else:
                    # Caller-supplied signature (e.g. inbound_receiver.py
                    # extracting real Stripe's t=/v1= header for genuine
                    # provider traffic): verify with the original convention.
                    signature_valid = self._verify_signature(inbound, payload, signature)

            log = InboundWebhookLog.objects.create(
                inbound=inbound,
                raw_payload=payload,
                headers=headers,
                ip_address=ip_address,
                signature_valid=signature_valid,
                processed=False,
            )

            if not signature_valid:
                InboundWebhookError.objects.create(
                    log=log,
                    error_type=ErrorType.AUTHENTICATION_ERROR,
                    error_message='Invalid signature',
                )
                return {'success': False, 'log_id': str(log.id), 'processed': False, 'error': 'Invalid signature'}

            if max_age_seconds is not None:
                if not self._timestamp_fresh(inbound.source, headers, max_age_seconds):
                    InboundWebhookError.objects.create(
                        log=log,
                        error_type=ErrorType.AUTHENTICATION_ERROR,
                        error_message='Timestamp too old',
                    )
                    return {'success': False, 'log_id': str(log.id), 'processed': False, 'error': 'Timestamp too old'}

            idempotency_key = self._extract_idempotency_key(headers)
            if idempotency_key:
                is_duplicate = any(
                    self._extract_idempotency_key(prior.headers) == idempotency_key
                    for prior in InboundWebhookLog.objects.filter(inbound=inbound, processed=True).exclude(pk=log.pk).only('headers')
                )
                if is_duplicate:
                    InboundWebhookError.objects.create(
                        log=log,
                        error_type=ErrorType.VALIDATION_ERROR,
                        error_message='Duplicate event',
                    )
                    return {'success': False, 'log_id': str(log.id), 'processed': False, 'error': 'Duplicate event'}

            try:
                event_type = self._extract_event_type(inbound.source, payload)
            except ValueError:
                InboundWebhookError.objects.create(
                    log=log,
                    error_type=ErrorType.VALIDATION_ERROR,
                    error_message='Missing event type',
                )
                return {'success': False, 'log_id': str(log.id), 'processed': False, 'error': 'Missing event type'}

            routing_results = self._route_webhook(inbound, payload, headers, log, event_type)

            if not routing_results:
                InboundWebhookError.objects.create(
                    log=log,
                    error_type=ErrorType.VALIDATION_ERROR,
                    error_message='No matching route found',
                )
                return {'success': False, 'log_id': str(log.id), 'processed': False, 'error': 'No matching route found'}

            log.processed = True
            log.processed_at = timezone.now()
            log.save()

            return {
                'success': True,
                'log_id': str(log.id),
                'processed': True,
                'event_type': event_type,
                'routing_results': routing_results,
            }
            
        except Exception as e:
            logger.error(f"Error processing inbound webhook: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    _SOURCE_SIGNATURE_HEADERS = {
        InboundSource.STRIPE: 'X-Stripe-Signature',
        InboundSource.PAYPAL: 'PAYPAL-AUTH-SHA256',
        InboundSource.BKASH: 'X-BKash-Signature',
        InboundSource.NAGAD: 'X-Nagad-Signature',
    }

    def _extract_signature_from_headers(self, source: str, headers: Dict[str, Any]) -> Optional[str]:
        """Case-insensitive lookup of the source-specific signature header."""
        header_name = self._SOURCE_SIGNATURE_HEADERS.get(source, 'X-Webhook-Signature')
        target = header_name.lower()
        for key, value in (headers or {}).items():
            if key.lower() == target:
                return value
        return None

    def _timestamp_fresh(self, source: str, headers: Dict[str, Any], max_age_seconds: int) -> bool:
        """Check a source-specific timestamp header against max_age_seconds."""
        timestamp_header = {
            InboundSource.STRIPE: 'X-Stripe-Timestamp',
        }.get(source, 'X-Webhook-Timestamp')
        target = timestamp_header.lower()
        raw_value = None
        for key, value in (headers or {}).items():
            if key.lower() == target:
                raw_value = value
                break
        if not raw_value:
            return True  # no timestamp header supplied: nothing to check
        try:
            from django.utils.dateparse import parse_datetime
            ts = parse_datetime(raw_value)
            if ts is None:
                return True
            if timezone.is_naive(ts):
                ts = timezone.make_aware(ts, timezone.utc)
            age = (timezone.now() - ts).total_seconds()
            return age <= max_age_seconds
        except Exception:
            return True

    @staticmethod
    def _extract_idempotency_key(headers: Dict[str, Any]) -> Optional[str]:
        """Find any header whose name contains 'idempotency', case-insensitive."""
        for key, value in (headers or {}).items():
            if 'idempotency' in key.lower():
                return value
        return None

    def _extract_event_type(self, source: str, payload: Dict[str, Any]) -> str:
        """Extract event_type from the generic {'event': {'type':}} /
        {'event_type':} envelope, raising ValueError if absent."""
        from .PayloadParser import PayloadParser
        return PayloadParser().extract_event_type(payload, source)

    @staticmethod
    def _check_ip_whitelist_list(ip_address: str, allowed_ips: List[str]) -> bool:
        try:
            import ipaddress
            ip_obj = ipaddress.ip_address(ip_address)
        except ValueError:
            return False
        for allowed_ip in allowed_ips:
            try:
                if ip_obj in ipaddress.ip_network(allowed_ip, strict=False):
                    return True
            except ValueError:
                continue
        return False
    
    def _verify_signature_headers(self, inbound: InboundWebhook, payload: Dict[str, Any], headers: Dict[str, Any]) -> bool:
        """Verify using the newer headers-based convention (sha256=... etc),
        for signatures this service extracted itself via
        _extract_signature_from_headers."""
        try:
            from ..inbound.SignatureVerifier import SignatureVerifier
            verifier = SignatureVerifier()
            return verifier.verify_signature_by_source(payload=payload, headers=headers, secret=inbound.secret, source=inbound.source)
        except Exception as e:
            logger.error(f"Error verifying signature (headers): {str(e)}")
            return False

    def _verify_signature(self, inbound: InboundWebhook, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            inbound: The inbound webhook configuration
            payload: The webhook payload
            signature: The signature to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            from ..inbound.SignatureVerifier import SignatureVerifier
            
            verifier = SignatureVerifier()
            return verifier.verify_signature(inbound.source, payload, signature, inbound.secret)
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return False
    
    def _check_ip_whitelist(self, inbound: InboundWebhook, ip_address: str) -> bool:
        """
        Check if IP address is in whitelist.
        
        Args:
            inbound: The inbound webhook configuration
            ip_address: The IP address to check
            
        Returns:
            True if IP is allowed, False otherwise
        """
        try:
            import ipaddress
            
            # Parse the IP address
            try:
                ip_obj = ipaddress.ip_address(ip_address)
            except ValueError:
                return False
            
            # Check against whitelist
            for allowed_ip in inbound.ip_whitelist:
                try:
                    # Try to parse as network (CIDR)
                    network = ipaddress.ip_network(allowed_ip, strict=False)
                    if ip_obj in network:
                        return True
                except ValueError:
                    # Try to parse as single IP
                    try:
                        allowed_ip_obj = ipaddress.ip_address(allowed_ip)
                        if ip_obj == allowed_ip_obj:
                            return True
                    except ValueError:
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking IP whitelist: {str(e)}")
            return False
    
    def _check_origin(self, inbound: InboundWebhook, headers: Dict[str, Any]) -> bool:
        """
        Check if request origin is allowed.
        
        Args:
            inbound: The inbound webhook configuration
            headers: HTTP headers from the request
            
        Returns:
            True if origin is allowed, False otherwise
        """
        try:
            origin = headers.get('Origin') or headers.get('origin')
            if not origin:
                return True  # No origin header, allow by default
            
            # Check against allowed origins
            for allowed_origin in inbound.allowed_origins:
                if origin == allowed_origin:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking origin: {str(e)}")
            return False
    
    def _route_webhook(self, inbound: InboundWebhook, payload: Dict[str, Any], headers: Dict[str, Any], log: InboundWebhookLog, event_type: str = None):
        """
        Route webhook to appropriate handlers.
        
        Args:
            inbound: The inbound webhook configuration
            payload: The webhook payload
            headers: HTTP headers from the request
            log: The inbound webhook log
            event_type: Pre-extracted event type, used to build event_data
                for the new-convention router.
            
        Returns:
            Truthy routing result if a handler matched, falsy otherwise
        """
        try:
            from ..inbound.InboundEventRouter import InboundEventRouter
            
            router = InboundEventRouter()
            event_data = {'event_type': event_type, 'data': payload}
            return router.route_event(event_data)
            
        except Exception as e:
            logger.error(f"Error routing webhook: {str(e)}")
            
            # Create error record
            InboundWebhookError.objects.create(
                log=log,
                error_type=ErrorType.SERVER_ERROR,
                error_message=str(e)
            )
            
            return False
    
    def get_inbound_statistics(self, inbound_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get statistics for inbound webhooks.
        
        Args:
            inbound_id: Optional inbound webhook ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count, Q
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for logs
            logs = InboundWebhookLog.objects.filter(created_at__gte=since)
            if inbound_id:
                logs = logs.filter(inbound_id=inbound_id)
            
            # Get overall statistics
            total_logs = logs.count()
            processed_logs = logs.filter(processed=True).count()
            signature_valid_logs = logs.filter(signature_valid=True).count()
            
            processing_rate = (processed_logs / total_logs * 100) if total_logs > 0 else 0
            signature_validity_rate = (signature_valid_logs / total_logs * 100) if total_logs > 0 else 0
            
            # Get error statistics
            error_logs = InboundWebhookError.objects.filter(
                log__created_at__gte=since
            )
            if inbound_id:
                error_logs = error_logs.filter(log__inbound_id=inbound_id)
            
            error_stats = error_logs.values('error_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'total_logs': total_logs,
                'processed_logs': processed_logs,
                'signature_valid_logs': signature_valid_logs,
                'processing_rate': round(processing_rate, 2),
                'signature_validity_rate': round(signature_validity_rate, 2),
                'error_breakdown': list(error_stats),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting inbound statistics: {str(e)}")
            return {
                'total_logs': 0,
                'processed_logs': 0,
                'signature_valid_logs': 0,
                'processing_rate': 0,
                'signature_validity_rate': 0,
                'error_breakdown': [],
                'period_days': days,
                'error': str(e)
            }
    
    def get_inbound_health_status(self, inbound_id: str) -> Dict[str, Any]:
        """
        Get health status for an inbound webhook.
        
        Args:
            inbound_id: The inbound webhook ID
            
        Returns:
            Dictionary with health status
        """
        try:
            from datetime import timedelta
            
            inbound = InboundWebhook.objects.get(id=inbound_id)
            
            # Get recent logs
            recent_logs = inbound.logs.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            total_recent = recent_logs.count()
            processed_recent = recent_logs.filter(processed=True).count()
            signature_valid_recent = recent_logs.filter(signature_valid=True).count()
            
            # Calculate health metrics
            processing_rate = (processed_recent / total_recent * 100) if total_recent > 0 else 0
            signature_validity_rate = (signature_valid_recent / total_recent * 100) if total_recent > 0 else 0
            
            # Get last processed time
            last_processed = recent_logs.filter(processed=True).order_by('-created_at').first()
            
            # Determine health status
            health_status = 'healthy'
            if processing_rate < 80:
                health_status = 'unhealthy'
            elif processing_rate < 95:
                health_status = 'degraded'
            
            return {
                'inbound_id': str(inbound.id),
                'source': inbound.source,
                'url_token': inbound.url_token,
                'is_active': inbound.is_active,
                'health_status': health_status,
                'total_recent_24h': total_recent,
                'processed_recent_24h': processed_recent,
                'signature_valid_recent_24h': signature_valid_recent,
                'processing_rate_24h': round(processing_rate, 2),
                'signature_validity_rate_24h': round(signature_validity_rate, 2),
                'last_processed_at': last_processed.created_at.isoformat() if last_processed else None,
                'created_at': inbound.created_at.isoformat(),
                'updated_at': inbound.updated_at.isoformat()
            }
            
        except InboundWebhook.DoesNotExist:
            return {
                'error': 'Inbound webhook not found'
            }
        except Exception as e:
            logger.error(f"Error getting inbound health status: {str(e)}")
            return {
                'error': str(e)
            }
    
    def cleanup_old_logs(self, days: int = 30) -> Dict[str, Any]:
        """
        Clean up old inbound webhook logs.
        
        Args:
            days: Number of days to keep logs
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete old logs
            deleted_logs = InboundWebhookLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            # Delete old errors
            deleted_errors = InboundWebhookError.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            return {
                'deleted_logs': deleted_logs,
                'deleted_errors': deleted_errors,
                'cutoff_date': cutoff_date.isoformat(),
                'days': days
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {str(e)}")
            return {
                'error': str(e),
                'days': days
            }
    
    def get_source_statistics(self, source: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get statistics for inbound webhooks by source.
        
        Args:
            source: Optional source to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with source statistics
        """
        try:
            from datetime import timedelta
            from django.db.models import Count
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for inbound webhooks
            inbound_webhooks = InboundWebhook.objects.filter(created_at__gte=since)
            if source:
                inbound_webhooks = inbound_webhooks.filter(source=source)
            
            # Get source breakdown
            source_stats = inbound_webhooks.values('source').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get log statistics
            logs = InboundWebhookLog.objects.filter(
                inbound__in=inbound_webhooks,
                created_at__gte=since
            )
            
            total_logs = logs.count()
            processed_logs = logs.filter(processed=True).count()
            
            return {
                'total_inbound_webhooks': inbound_webhooks.count(),
                'total_logs': total_logs,
                'processed_logs': processed_logs,
                'processing_rate': round((processed_logs / total_logs * 100) if total_logs > 0 else 0, 2),
                'source_breakdown': list(source_stats),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting source statistics: {str(e)}")
            return {
                'error': str(e),
                'period_days': days
            }
    
    def test_inbound_webhook(self, inbound_id: str) -> Dict[str, Any]:
        """
        Test an inbound webhook configuration.
        
        Args:
            inbound_id: The inbound webhook ID to test
            
        Returns:
            Dictionary with test results
        """
        try:
            inbound = InboundWebhook.objects.get(id=inbound_id)
            
            # Create test payload
            test_payload = {
                'event': {
                    'type': 'webhook.test',
                    'data': {
                        'test': True,
                        'timestamp': timezone.now().isoformat(),
                        'source': inbound.source
                    }
                }
            }
            
            # Create test headers
            test_headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Source': inbound.source,
                'X-Webhook-Timestamp': timezone.now().isoformat()
            }
            
            # Generate test signature
            from ..inbound.SignatureVerifier import SignatureVerifier
            verifier = SignatureVerifier()
            test_signature = verifier.generate_signature(inbound.source, test_payload, inbound.secret)
            test_headers['X-Webhook-Signature'] = test_signature
            
            # Process test webhook
            result = self.process_inbound_webhook(
                inbound=inbound,
                payload=test_payload,
                headers=test_headers,
                signature=test_signature,
                ip_address='127.0.0.1'
            )
            
            return {
                'inbound_id': str(inbound.id),
                'source': inbound.source,
                'url_token': inbound.url_token,
                'test_payload': test_payload,
                'test_headers': test_headers,
                'test_signature': test_signature,
                'result': result
            }
            
        except InboundWebhook.DoesNotExist:
            return {
                'error': 'Inbound webhook not found'
            }
        except Exception as e:
            logger.error(f"Error testing inbound webhook: {str(e)}")
            return {
                'error': str(e)
            }