"""Signature Verifier Service

This module provides signature verification for different webhook sources (bKash, Nagad, Stripe, etc.).
"""

import logging
import hashlib
import hmac
import base64
from typing import Dict, Any, Optional
from django.utils import timezone

from ...constants import InboundSource

logger = logging.getLogger(__name__)


class SignatureVerifier:
    """Service for verifying webhook signatures from different payment gateways."""
    
    def __init__(self):
        """Initialize the signature verifier service."""
        self.logger = logger
    
    def verify_signature(self, source: str, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify webhook signature based on source.
        
        Args:
            source: The webhook source (bKash, Nagad, Stripe, etc.)
            payload: The webhook payload
            signature: The signature to verify
            secret: The secret key for verification
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if source == InboundSource.BKASH:
                return self._verify_bkash_signature(payload, signature, secret)
            elif source == InboundSource.NAGAD:
                return self._verify_nagad_signature(payload, signature, secret)
            elif source == InboundSource.STRIPE:
                return self._verify_stripe_signature(payload, signature, secret)
            elif source == InboundSource.PAYPAL:
                return self._verify_paypal_signature(payload, signature, secret)
            else:
                # Default to HMAC verification
                return self._verify_hmac_signature(payload, signature, secret)
                
        except Exception as e:
            logger.error(f"Error verifying signature for {source}: {str(e)}")
            return False
    
    def _verify_bkash_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify bKash webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The signature to verify
            secret: The bKash secret key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # bKash uses HMAC-SHA256
            import json
            
            # Create the string to sign
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            # Generate HMAC-SHA256
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            expected_signature = hmac_obj.hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying bKash signature: {str(e)}")
            return False
    
    def _verify_nagad_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify Nagad webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The signature to verify
            secret: The Nagad secret key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Nagad uses HMAC-SHA256 with Base64 encoding
            import json
            
            # Create the string to sign
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            # Generate HMAC-SHA256
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            # Encode to Base64
            expected_signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying Nagad signature: {str(e)}")
            return False
    
    def _verify_stripe_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify Stripe webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The signature to verify
            secret: The Stripe webhook secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Stripe uses their own signature verification method
            # For simplicity, we'll implement a basic version
            # In production, use stripe.Webhook.construct_event
            
            import json
            
            # Extract timestamp from signature header
            # Format: t=timestamp,v1=signature
            parts = signature.split(',')
            timestamp = None
            received_signature = None
            
            for part in parts:
                if part.startswith('t='):
                    timestamp = part[2:]
                elif part.startswith('v1='):
                    received_signature = part[3:]
            
            if not timestamp or not received_signature:
                return False
            
            # Create the string to sign: timestamp + '.' + payload
            string_to_sign = f"{timestamp}.{json.dumps(payload, separators=(',', ':'), sort_keys=True)}"
            
            # Generate HMAC-SHA256
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            expected_signature = hmac_obj.hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(received_signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying Stripe signature: {str(e)}")
            return False
    
    def _verify_paypal_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify PayPal webhook signature.
        
        Args:
            payload: The webhook payload
            signature: The signature to verify
            secret: The PayPal webhook secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # PayPal uses HMAC-SHA256 with Base64 encoding
            import json
            
            # Create the string to sign
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            # Generate HMAC-SHA256
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            # Encode to Base64
            expected_signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying PayPal signature: {str(e)}")
            return False
    
    def _verify_hmac_signature(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
        """
        Verify generic HMAC signature.
        
        Args:
            payload: The webhook payload
            signature: The signature to verify
            secret: The secret key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            import json
            
            # Create the string to sign
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            # Generate HMAC-SHA256
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            expected_signature = hmac_obj.hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying HMAC signature: {str(e)}")
            return False
    
    def generate_signature(self, source: str, payload: Dict[str, Any], secret: str) -> str:
        """
        Generate signature for testing purposes.
        
        Args:
            source: The webhook source
            payload: The webhook payload
            secret: The secret key
            
        Returns:
            Generated signature
        """
        try:
            if source == InboundSource.BKASH:
                return self._generate_bkash_signature(payload, secret)
            elif source == InboundSource.NAGAD:
                return self._generate_nagad_signature(payload, secret)
            elif source == InboundSource.STRIPE:
                return self._generate_stripe_signature(payload, secret)
            elif source == InboundSource.PAYPAL:
                return self._generate_paypal_signature(payload, secret)
            else:
                # Default to HMAC signature
                return self._generate_hmac_signature(payload, secret)
                
        except Exception as e:
            logger.error(f"Error generating signature for {source}: {str(e)}")
            return ""
    
    def _generate_bkash_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate bKash signature."""
        try:
            import json
            
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            return hmac_obj.hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating bKash signature: {str(e)}")
            return ""
    
    def _generate_nagad_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate Nagad signature."""
        try:
            import json
            
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            return base64.b64encode(hmac_obj.digest()).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error generating Nagad signature: {str(e)}")
            return ""
    
    def _generate_stripe_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate Stripe signature."""
        try:
            import json
            
            timestamp = str(int(timezone.now().timestamp()))
            string_to_sign = f"{timestamp}.{json.dumps(payload, separators=(',', ':'), sort_keys=True)}"
            
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            signature = hmac_obj.hexdigest()
            return f"t={timestamp},v1={signature}"
            
        except Exception as e:
            logger.error(f"Error generating Stripe signature: {str(e)}")
            return ""
    
    def _generate_paypal_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate PayPal signature."""
        try:
            import json
            
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            return base64.b64encode(hmac_obj.digest()).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error generating PayPal signature: {str(e)}")
            return ""
    
    def _generate_hmac_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate generic HMAC signature."""
        try:
            import json
            
            string_to_sign = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            hmac_obj = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            )
            
            return hmac_obj.hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating HMAC signature: {str(e)}")
            return ""
    
    def get_signature_info(self, source: str) -> Dict[str, Any]:
        """
        Get information about signature requirements for a source.
        
        Args:
            source: The webhook source
            
        Returns:
            Dictionary with signature information
        """
        try:
            signature_info = {
                'source': source,
                'algorithm': 'HMAC-SHA256',
                'encoding': 'hex',
                'headers': ['X-Webhook-Signature']
            }
            
            if source == InboundSource.BKASH:
                signature_info.update({
                    'algorithm': 'HMAC-SHA256',
                    'encoding': 'hex',
                    'headers': ['X-BKash-Signature', 'X-Webhook-Signature']
                })
            elif source == InboundSource.NAGAD:
                signature_info.update({
                    'algorithm': 'HMAC-SHA256',
                    'encoding': 'base64',
                    'headers': ['X-Nagad-Signature', 'X-Webhook-Signature']
                })
            elif source == InboundSource.STRIPE:
                signature_info.update({
                    'algorithm': 'HMAC-SHA256',
                    'encoding': 'hex',
                    'headers': ['Stripe-Signature', 'X-Webhook-Signature'],
                    'format': 't=timestamp,v1=signature'
                })
            elif source == InboundSource.PAYPAL:
                signature_info.update({
                    'algorithm': 'HMAC-SHA256',
                    'encoding': 'base64',
                    'headers': ['PayPal-Auth-Algo', 'PayPal-Transmission-Sig', 'PayPal-Cert-Id', 'X-Webhook-Signature']
                })
            
            return signature_info
            
        except Exception as e:
            logger.error(f"Error getting signature info for {source}: {str(e)}")
            return {
                'source': source,
                'error': str(e)
            }
    
    def validate_signature_format(self, source: str, signature: str) -> Dict[str, Any]:
        """
        Validate signature format for a source.
        
        Args:
            source: The webhook source
            signature: The signature to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            validation_result = {
                'source': source,
                'signature': signature,
                'valid_format': True,
                'message': 'Signature format is valid'
            }
            
            if source == InboundSource.STRIPE:
                # Stripe format: t=timestamp,v1=signature
                parts = signature.split(',')
                if len(parts) < 2:
                    validation_result['valid_format'] = False
                    validation_result['message'] = 'Stripe signature must contain timestamp and signature'
                else:
                    timestamp_part = None
                    signature_part = None
                    for part in parts:
                        if part.startswith('t='):
                            timestamp_part = part
                        elif part.startswith('v1='):
                            signature_part = part
                    
                    if not timestamp_part or not signature_part:
                        validation_result['valid_format'] = False
                        validation_result['message'] = 'Stripe signature missing required parts'
            
            elif source in [InboundSource.NAGAD, InboundSource.PAYPAL]:
                # Base64 encoded signatures
                try:
                    base64.b64decode(signature.encode('utf-8'))
                except Exception:
                    validation_result['valid_format'] = False
                    validation_result['message'] = 'Signature must be Base64 encoded'
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating signature format for {source}: {str(e)}")
            return {
                'source': source,
                'signature': signature,
                'valid_format': False,
                'message': f'Validation error: {str(e)}'
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
            InboundSource.PAYPAL,
            'generic'
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
