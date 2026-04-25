"""Payload Parser Service

This module provides payload normalization for different webhook gateway formats.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from django.utils import timezone

from ...constants import InboundSource

logger = logging.getLogger(__name__)


class PayloadParser:
    """Service for normalizing webhook payloads from different gateway formats."""
    
    def __init__(self):
        """Initialize the payload parser service."""
        self.logger = logger
    
    def parse_payload(self, source: str, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize webhook payload based on source.
        
        Args:
            source: The webhook source (bKash, Nagad, Stripe, etc.)
            raw_payload: The raw webhook payload
            
        Returns:
            Normalized payload dictionary
        """
        try:
            if source == InboundSource.BKASH:
                return self._parse_bkash_payload(raw_payload)
            elif source == InboundSource.NAGAD:
                return self._parse_nagad_payload(raw_payload)
            elif source == InboundSource.STRIPE:
                return self._parse_stripe_payload(raw_payload)
            elif source == InboundSource.PAYPAL:
                return self._parse_paypal_payload(raw_payload)
            else:
                # Return payload as-is for unknown sources
                return raw_payload
                
        except Exception as e:
            logger.error(f"Error parsing payload for {source}: {str(e)}")
            return raw_payload
    
    def _parse_bkash_payload(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse bKash webhook payload.
        
        Args:
            raw_payload: The raw bKash payload
            
        Returns:
            Normalized payload dictionary
        """
        try:
            # Extract common fields from bKash payload
            normalized = {
                'source': InboundSource.BKASH,
                'event_type': raw_payload.get('eventType', 'unknown'),
                'transaction_id': raw_payload.get('paymentID'),
                'amount': raw_payload.get('amount'),
                'currency': raw_payload.get('currency', 'BDT'),
                'status': raw_payload.get('status'),
                'timestamp': raw_payload.get('createTime'),
                'merchant_account': raw_payload.get('merchantInvoiceNumber'),
                'customer_account': raw_payload.get('customerMsisdn'),
                'raw_payload': raw_payload
            }
            
            # Add additional fields if available
            if 'transactionDetails' in raw_payload:
                details = raw_payload['transactionDetails']
                normalized.update({
                    'transaction_details': details,
                    'reference': details.get('reference'),
                    'sender': details.get('sender')
                })
            
            # Determine standardized event type
            event_type = self._determine_bkash_event_type(raw_payload)
            normalized['standardized_event_type'] = event_type
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error parsing bKash payload: {str(e)}")
            return {
                'source': InboundSource.BKASH,
                'event_type': 'unknown',
                'raw_payload': raw_payload,
                'error': str(e)
            }
    
    def _parse_nagad_payload(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Nagad webhook payload.
        
        Args:
            raw_payload: The raw Nagad payload
            
        Returns:
            Normalized payload dictionary
        """
        try:
            # Extract common fields from Nagad payload
            normalized = {
                'source': InboundSource.NAGAD,
                'event_type': raw_payload.get('status', 'unknown'),
                'transaction_id': raw_payload.get('orderId'),
                'amount': raw_payload.get('amount'),
                'currency': raw_payload.get('currency', 'BDT'),
                'status': raw_payload.get('status'),
                'timestamp': raw_payload.get('date_time'),
                'merchant_account': raw_payload.get('merchant_number'),
                'customer_account': raw_payload.get('mobile_no'),
                'raw_payload': raw_payload
            }
            
            # Add additional fields if available
            if 'payment_details' in raw_payload:
                details = raw_payload['payment_details']
                normalized.update({
                    'payment_details': details,
                    'reference': details.get('reference'),
                    'gateway': details.get('gateway')
                })
            
            # Determine standardized event type
            event_type = self._determine_nagad_event_type(raw_payload)
            normalized['standardized_event_type'] = event_type
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error parsing Nagad payload: {str(e)}")
            return {
                'source': InboundSource.NAGAD,
                'event_type': 'unknown',
                'raw_payload': raw_payload,
                'error': str(e)
            }
    
    def _parse_stripe_payload(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Stripe webhook payload.
        
        Args:
            raw_payload: The raw Stripe payload
            
        Returns:
            Normalized payload dictionary
        """
        try:
            # Extract common fields from Stripe payload
            event_type = raw_payload.get('type', 'unknown')
            event_data = raw_payload.get('data', {}).get('object', {})
            
            normalized = {
                'source': InboundSource.STRIPE,
                'event_type': event_type,
                'transaction_id': event_data.get('id'),
                'amount': event_data.get('amount'),
                'currency': event_data.get('currency', 'USD'),
                'status': event_data.get('status'),
                'timestamp': raw_payload.get('created'),
                'customer_id': event_data.get('customer'),
                'raw_payload': raw_payload
            }
            
            # Convert amount from cents to dollars
            if normalized['amount']:
                normalized['amount'] = normalized['amount'] / 100
            
            # Add additional fields based on event type
            if event_type.startswith('payment_intent.'):
                normalized.update({
                    'payment_method': event_data.get('payment_method'),
                    'receipt_email': event_data.get('receipt_email'),
                    'metadata': event_data.get('metadata', {})
                })
            elif event_type.startswith('charge.'):
                normalized.update({
                    'payment_method': event_data.get('payment_method'),
                    'receipt_url': event_data.get('receipt_url'),
                    'failure_code': event_data.get('failure_code'),
                    'failure_message': event_data.get('failure_message')
                })
            elif event_type.startswith('invoice.'):
                normalized.update({
                    'invoice_number': event_data.get('number'),
                    'customer_email': event_data.get('customer_email'),
                    'billing_reason': event_data.get('billing_reason')
                })
            
            # Determine standardized event type
            standardized_event_type = self._determine_stripe_event_type(event_type)
            normalized['standardized_event_type'] = standardized_event_type
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error parsing Stripe payload: {str(e)}")
            return {
                'source': InboundSource.STRIPE,
                'event_type': 'unknown',
                'raw_payload': raw_payload,
                'error': str(e)
            }
    
    def _parse_paypal_payload(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse PayPal webhook payload.
        
        Args:
            raw_payload: The raw PayPal payload
            
        Returns:
            Normalized payload dictionary
        """
        try:
            # Extract common fields from PayPal payload
            event_type = raw_payload.get('event_type', 'unknown')
            resource = raw_payload.get('resource', {})
            
            normalized = {
                'source': InboundSource.PAYPAL,
                'event_type': event_type,
                'transaction_id': resource.get('id'),
                'amount': resource.get('amount', {}).get('total'),
                'currency': resource.get('amount', {}).get('currency', 'USD'),
                'status': resource.get('state'),
                'timestamp': raw_payload.get('create_time'),
                'customer_id': resource.get('payer', {}).get('payer_id'),
                'raw_payload': raw_payload
            }
            
            # Add additional fields if available
            if 'amount' in resource:
                amount_info = resource['amount']
                normalized.update({
                    'amount_details': amount_info,
                    'subtotal': amount_info.get('details', {}).get('subtotal'),
                    'tax': amount_info.get('details', {}).get('tax'),
                    'shipping': amount_info.get('details', {}).get('shipping')
                })
            
            if 'payer' in resource:
                payer_info = resource['payer']
                normalized.update({
                    'payer_info': payer_info,
                    'payer_email': payer_info.get('email_address'),
                    'payer_name': payer_info.get('name', {}).get('full_name')
                })
            
            # Determine standardized event type
            standardized_event_type = self._determine_paypal_event_type(event_type)
            normalized['standardized_event_type'] = standardized_event_type
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error parsing PayPal payload: {str(e)}")
            return {
                'source': InboundSource.PAYPAL,
                'event_type': 'unknown',
                'raw_payload': raw_payload,
                'error': str(e)
            }
    
    def _determine_bkash_event_type(self, payload: Dict[str, Any]) -> str:
        """Determine standardized event type for bKash."""
        try:
            event_type = payload.get('eventType', '').lower()
            status = payload.get('status', '').lower()
            
            if 'payment' in event_type:
                if status == 'success':
                    return 'payment.success'
                elif status == 'failed':
                    return 'payment.failed'
                elif status == 'initiated':
                    return 'payment.initiated'
                elif status == 'cancelled':
                    return 'payment.cancelled'
            elif 'refund' in event_type:
                return 'payment.refunded'
            elif 'dispute' in event_type:
                return 'payment.disputed'
            
            return 'payment.unknown'
            
        except Exception:
            return 'payment.unknown'
    
    def _determine_nagad_event_type(self, payload: Dict[str, Any]) -> str:
        """Determine standardized event type for Nagad."""
        try:
            status = payload.get('status', '').lower()
            
            if status == 'success':
                return 'payment.success'
            elif status == 'failed':
                return 'payment.failed'
            elif status == 'initiated':
                return 'payment.initiated'
            elif status == 'cancelled':
                return 'payment.cancelled'
            elif status == 'refunded':
                return 'payment.refunded'
            
            return 'payment.unknown'
            
        except Exception:
            return 'payment.unknown'
    
    def _determine_stripe_event_type(self, event_type: str) -> str:
        """Determine standardized event type for Stripe."""
        try:
            if event_type.startswith('payment_intent.succeeded'):
                return 'payment.success'
            elif event_type.startswith('payment_intent.payment_failed'):
                return 'payment.failed'
            elif event_type.startswith('payment_intent.created'):
                return 'payment.initiated'
            elif event_type.startswith('payment_intent.canceled'):
                return 'payment.cancelled'
            elif event_type.startswith('charge.succeeded'):
                return 'payment.success'
            elif event_type.startswith('charge.failed'):
                return 'payment.failed'
            elif event_type.startswith('charge.dispute.created'):
                return 'payment.disputed'
            elif event_type.startswith('invoice.payment_succeeded'):
                return 'payment.success'
            elif event_type.startswith('invoice.payment_failed'):
                return 'payment.failed'
            
            return 'payment.unknown'
            
        except Exception:
            return 'payment.unknown'
    
    def _determine_paypal_event_type(self, event_type: str) -> str:
        """Determine standardized event type for PayPal."""
        try:
            if event_type == 'PAYMENT.SALE.COMPLETED':
                return 'payment.success'
            elif event_type == 'PAYMENT.SALE.DENIED':
                return 'payment.failed'
            elif event_type == 'PAYMENT.SALE.REFUNDED':
                return 'payment.refunded'
            elif event_type == 'PAYMENT.SALE.REVERSED':
                return 'payment.disputed'
            elif event_type == 'PAYMENT.CAPTURE.COMPLETED':
                return 'payment.success'
            elif event_type == 'PAYMENT.CAPTURE.DENIED':
                return 'payment.failed'
            elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
                return 'payment.refunded'
            
            return 'payment.unknown'
            
        except Exception:
            return 'payment.unknown'
    
    def get_payload_schema(self, source: str) -> Dict[str, Any]:
        """
        Get expected payload schema for a source.
        
        Args:
            source: The webhook source
            
        Returns:
            Dictionary with payload schema
        """
        try:
            schema = {
                'source': source,
                'required_fields': [],
                'optional_fields': [],
                'examples': {}
            }
            
            if source == InboundSource.BKASH:
                schema.update({
                    'required_fields': ['eventType', 'paymentID', 'amount', 'status'],
                    'optional_fields': ['currency', 'createTime', 'merchantInvoiceNumber', 'customerMsisdn'],
                    'examples': {
                        'payment_success': {
                            'eventType': 'PAYMENT_SUCCESS',
                            'paymentID': 'TRX123456789',
                            'amount': '100.00',
                            'currency': 'BDT',
                            'status': 'success',
                            'createTime': '2023-01-01T12:00:00Z'
                        }
                    }
                })
            elif source == InboundSource.NAGAD:
                schema.update({
                    'required_fields': ['orderId', 'amount', 'status'],
                    'optional_fields': ['currency', 'date_time', 'merchant_number', 'mobile_no'],
                    'examples': {
                        'payment_success': {
                            'orderId': 'ORDER123456',
                            'amount': '100.00',
                            'currency': 'BDT',
                            'status': 'success',
                            'date_time': '2023-01-01T12:00:00Z'
                        }
                    }
                })
            elif source == InboundSource.STRIPE:
                schema.update({
                    'required_fields': ['type', 'data'],
                    'optional_fields': ['created', 'id'],
                    'examples': {
                        'payment_success': {
                            'type': 'payment_intent.succeeded',
                            'data': {
                                'object': {
                                    'id': 'pi_123456789',
                                    'amount': 10000,
                                    'currency': 'usd',
                                    'status': 'succeeded'
                                }
                            }
                        }
                    }
                })
            elif source == InboundSource.PAYPAL:
                schema.update({
                    'required_fields': ['event_type', 'resource'],
                    'optional_fields': ['create_time', 'id'],
                    'examples': {
                        'payment_success': {
                            'event_type': 'PAYMENT.SALE.COMPLETED',
                            'resource': {
                                'id': 'SALE123456',
                                'amount': {
                                    'total': '100.00',
                                    'currency': 'USD'
                                },
                                'state': 'completed'
                            }
                        }
                    }
                })
            
            return schema
            
        except Exception as e:
            logger.error(f"Error getting payload schema for {source}: {str(e)}")
            return {
                'source': source,
                'error': str(e)
            }
    
    def validate_payload_structure(self, source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate payload structure for a source.
        
        Args:
            source: The webhook source
            payload: The payload to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            validation_result = {
                'source': source,
                'valid': True,
                'errors': [],
                'warnings': []
            }
            
            schema = self.get_payload_schema(source)
            required_fields = schema.get('required_fields', [])
            
            # Check required fields
            for field in required_fields:
                if field not in payload:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Missing required field: {field}')
            
            # Check for unexpected fields (warnings)
            all_fields = required_fields + schema.get('optional_fields', [])
            for field in payload:
                if field not in all_fields:
                    validation_result['warnings'].append(f'Unexpected field: {field}')
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating payload structure for {source}: {str(e)}")
            return {
                'source': source,
                'valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def get_supported_sources(self) -> List[str]:
        """
        Get list of supported webhook sources.
        
        Returns:
            List of supported source names
        """
        return [
            InboundSource.BKASH,
            InboundSource.NAGAD,
            InboundSource.STRIPE,
            InboundSource.PAYPAL
        ]
    
    def is_source_supported(self, source: str) -> bool:
        """
        Check if a source is supported.
        
        Args:
            source: The webhook source
            
        Returns:
            True if source is supported, False otherwise
        """
        return source in self.get_supported_sources()
    
    def create_sample_payload(self, source: str, event_type: str = 'payment.success') -> Dict[str, Any]:
        """
        Create a sample payload for testing.
        
        Args:
            source: The webhook source
            event_type: The event type to create
            
        Returns:
            Sample payload dictionary
        """
        try:
            if source == InboundSource.BKASH:
                return {
                    'eventType': 'PAYMENT_SUCCESS',
                    'paymentID': f'TRX{timezone.now().timestamp()}',
                    'amount': '100.00',
                    'currency': 'BDT',
                    'status': 'success',
                    'createTime': timezone.now().isoformat(),
                    'merchantInvoiceNumber': f'INV{timezone.now().timestamp()}',
                    'customerMsisdn': '01812345678'
                }
            elif source == InboundSource.NAGAD:
                return {
                    'orderId': f'ORDER{timezone.now().timestamp()}',
                    'amount': '100.00',
                    'currency': 'BDT',
                    'status': 'success',
                    'date_time': timezone.now().isoformat(),
                    'merchant_number': '01812345678',
                    'mobile_no': '01898765432'
                }
            elif source == InboundSource.STRIPE:
                return {
                    'type': 'payment_intent.succeeded',
                    'created': int(timezone.now().timestamp()),
                    'data': {
                        'object': {
                            'id': f'pi_{timezone.now().timestamp()}',
                            'amount': 10000,
                            'currency': 'usd',
                            'status': 'succeeded',
                            'customer': f'cus_{timezone.now().timestamp()}',
                            'payment_method': f'pm_{timezone.now().timestamp()}',
                            'receipt_email': 'test@example.com'
                        }
                    }
                }
            elif source == InboundSource.PAYPAL:
                return {
                    'event_type': 'PAYMENT.SALE.COMPLETED',
                    'create_time': timezone.now().isoformat(),
                    'id': f'WH-{timezone.now().timestamp()}',
                    'resource': {
                        'id': f'SALE{timezone.now().timestamp()}',
                        'amount': {
                            'total': '100.00',
                            'currency': 'USD',
                            'details': {
                                'subtotal': '90.00',
                                'tax': '10.00'
                            }
                        },
                        'state': 'completed',
                        'payer': {
                            'payer_id': f'PAYER{timezone.now().timestamp()}',
                            'email_address': 'test@example.com',
                            'name': {
                                'full_name': 'Test User'
                            }
                        }
                    }
                }
            else:
                return {
                    'source': source,
                    'event_type': event_type,
                    'timestamp': timezone.now().isoformat(),
                    'test': True
                }
                
        except Exception as e:
            logger.error(f"Error creating sample payload for {source}: {str(e)}")
            return {
                'source': source,
                'event_type': event_type,
                'error': str(e)
            }
