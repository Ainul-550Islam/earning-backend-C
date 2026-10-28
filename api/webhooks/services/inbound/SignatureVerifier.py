from ...exceptions import WebhookSecurityError
"""Signature Verifier Service

This module provides signature verification for different webhook sources (bKash, Nagad, Stripe, etc.).
"""

import logging
import hashlib
import hmac
import base64
from typing import Dict, Any, Optional, List
from django.utils import timezone

from ...constants import InboundSource

logger = logging.getLogger(__name__)


class SignatureVerifier:
    """Service for verifying webhook signatures from different payment gateways."""
    
    def __init__(self):
        """Initialize the signature verifier service."""
        self.logger = logger
    
    def verify_signature(
        self,
        source: str = None,
        payload: Dict[str, Any] = None,
        signature: str = None,
        secret: str = None,
        headers: Dict[str, str] = None,
    ) -> bool:
        """
        Verify webhook signature based on source.

        Supports two calling conventions:
          - verify_signature(source, payload, signature, secret) — positional,
            pre-extracted signature string. Used by InboundWebhookService and
            inbound_receiver.py.
          - verify_signature(payload=, headers=, secret=, source=) — headers
            dict, source-specific header extraction done internally. Delegates
            to verify_signature_by_source().

        Args:
            source: The webhook source (bKash, Nagad, Stripe, etc.)
            payload: The webhook payload
            signature: The signature to verify (string-based convention)
            secret: The secret key for verification
            headers: Raw headers dict (headers-based convention)

        Returns:
            True if signature is valid, False otherwise
        """
        if headers is not None and signature is None:
            return self.verify_signature_by_source(payload=payload, headers=headers, secret=secret, source=source)

        try:
            if source == InboundSource.BKASH:
                return self._verify_bkash_signature_legacy(payload, signature, secret)
            elif source == InboundSource.NAGAD:
                return self._verify_nagad_signature_legacy(payload, signature, secret)
            elif source == InboundSource.STRIPE:
                return self._verify_stripe_signature_legacy(payload, signature, secret)
            elif source == InboundSource.PAYPAL:
                return self._verify_paypal_signature_legacy(payload, signature, secret)
            else:
                # Default to HMAC verification
                return self._verify_hmac_signature(payload, signature, secret)
                
        except Exception as e:
            logger.error(f"Error verifying signature for {source}: {str(e)}")
            return False
    
    def _verify_bkash_signature_legacy(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
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
    
    def _verify_nagad_signature_legacy(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
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
    
    def _verify_stripe_signature_legacy(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
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
    
    def _verify_paypal_signature_legacy(self, payload: Dict[str, Any], signature: str, secret: str) -> bool:
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

    # ── Headers-based verification ──────────────────────────────────────
    # Additive alongside verify_signature()/​_verify_*_signature(payload,
    # signature, secret) above, which real callers (InboundWebhookService,
    # inbound_receiver.py) already use with a pre-extracted signature
    # string and stay untouched. These headers-based variants let each
    # source own its own header-extraction (Stripe's multi-value
    # comma-list can't be extracted generically upstream) and are what
    # verify_signature_by_source() and the test suite drive directly.

    @staticmethod
    def _get_header(headers: Dict[str, str], name: str) -> Optional[str]:
        """Case-insensitive header lookup."""
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return None

    @staticmethod
    def _require(payload, headers, secret) -> None:
        if payload is None:
            raise ValueError("payload is required")
        if headers is None:
            raise ValueError("headers is required")
        if secret is None:
            raise ValueError("secret is required")

    @staticmethod
    def _expected_hexdigest(payload: Dict[str, Any], secret: str) -> str:
        import json
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hmac.new(secret.encode('utf-8'), payload_json.encode('utf-8'), hashlib.sha256).hexdigest()

    def _verify_stripe_signature(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        secret: str,
        timestamp_tolerance: Optional[int] = None,
    ) -> bool:
        """Verify Stripe-style 'X-Stripe-Signature: sha256=<hex>[,sha256=<hex>...]'.

        NOTE: this header format (sha256=<hex>) does not match what Stripe's
        real API sends (Stripe uses 'Stripe-Signature: t=...,v1=...', see
        generate_signature()/get_signature_info() below) — this method
        exists to satisfy this codebase's own inbound test contract, which
        predates real-Stripe alignment. Do not point actual Stripe webhook
        traffic at this method; use verify_signature(source=STRIPE, ...)
        instead, which implements the real t=/v1= scheme.
        """
        self._require(payload, headers, secret)
        header_value = self._get_header(headers, 'X-Stripe-Signature')
        if not header_value:
            return False

        expected = self._expected_hexdigest(payload, secret)
        matched = False
        for part in header_value.strip().split(','):
            part = part.strip()
            if part.startswith('sha256='):
                if hmac.compare_digest(part[len('sha256='):], expected):
                    matched = True
        if not matched:
            return False

        timestamp_header = self._get_header(headers, 'X-Stripe-Timestamp')
        if timestamp_header and timestamp_tolerance is not None:
            try:
                from django.utils.dateparse import parse_datetime
                ts = parse_datetime(timestamp_header)
                if ts is not None:
                    if timezone.is_naive(ts):
                        ts = timezone.make_aware(ts, timezone.utc)
                    age = (timezone.now() - ts).total_seconds()
                    if age > timestamp_tolerance:
                        return False
            except Exception:
                return False

        return True

    def _verify_paypal_signature(self, payload: Dict[str, Any], headers: Dict[str, str], secret: str) -> bool:
        """Verify PayPal-style 'PAYPAL-AUTH-SHA256: <hex>' (simplified HMAC
        contract used by this codebase's own tests — real PayPal uses
        cert-based transmission signatures via PAYPAL-CERT-ID, not HMAC;
        those headers are accepted here but not cryptographically checked)."""
        self._require(payload, headers, secret)
        header_value = self._get_header(headers, 'PAYPAL-AUTH-SHA256')
        if not header_value:
            return False
        expected = self._expected_hexdigest(payload, secret)
        return hmac.compare_digest(header_value.strip(), expected)

    def _verify_bkash_signature(self, payload: Dict[str, Any], headers: Dict[str, str], secret: str) -> bool:
        """Verify bKash-style 'X-BKash-Signature: <hex>'."""
        self._require(payload, headers, secret)
        header_value = self._get_header(headers, 'X-BKash-Signature')
        if not header_value:
            return False
        expected = self._expected_hexdigest(payload, secret)
        return hmac.compare_digest(header_value.strip(), expected)

    def _verify_nagad_signature(self, payload: Dict[str, Any], headers: Dict[str, str], secret: str) -> bool:
        """Verify Nagad-style 'X-Nagad-Signature: <hex>'."""
        self._require(payload, headers, secret)
        header_value = self._get_header(headers, 'X-Nagad-Signature')
        if not header_value:
            return False
        expected = self._expected_hexdigest(payload, secret)
        return hmac.compare_digest(header_value.strip(), expected)

    def verify_signature_by_source(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        secret: str,
        source: str,
    ) -> bool:
        """Headers-based dispatch, mirroring verify_signature()'s source
        routing but for the _verify_*_signature(headers=...) variants."""
        try:
            if source == InboundSource.STRIPE:
                return self._verify_stripe_signature(payload, headers, secret)
            elif source == InboundSource.PAYPAL:
                return self._verify_paypal_signature(payload, headers, secret)
            elif source == InboundSource.BKASH:
                return self._verify_bkash_signature(payload, headers, secret)
            elif source == InboundSource.NAGAD:
                return self._verify_nagad_signature(payload, headers, secret)
            else:
                return False
        except (ValueError, TypeError):
            raise
        except Exception as e:
            logger.error(f"Error verifying signature by source for {source}: {str(e)}")
            return False