"""Signature Engine

This module provides HMAC signature generation and verification for webhooks.
"""

import hmac
import hashlib
import base64
from typing import Union, Dict, Any
from django.conf import settings
from django.utils import timezone


class SignatureEngine:
    """Engine for generating and verifying HMAC signatures for webhooks."""
    
    def __init__(self, algorithm: str = 'sha256', encoding: str = 'utf-8'):
        """
        Initialize the signature engine.
        
        Args:
            algorithm: HMAC algorithm to use (sha256, sha1, md5)
            encoding: Character encoding for signatures
        """
        self.algorithm = algorithm
        self.encoding = encoding
        self.digestmod = getattr(hashlib, algorithm.upper(), hashlib.sha256)
    
    def generate_signature(self, payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> str:
        """
        Generate HMAC signature for webhook payload.
        
        Args:
            payload: The payload to sign (string, bytes, or dict)
            secret: The secret key for signing
            
        Returns:
            Hex-encoded HMAC signature
        """
        try:
            # Convert payload to string if it's a dict
            if isinstance(payload, dict):
                import json
                payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            elif isinstance(payload, bytes):
                payload_str = payload.decode(self.encoding)
            else:
                payload_str = str(payload)
            
            # Create HMAC signature
            hmac_obj = hmac.new(
                secret.encode(self.encoding),
                payload_str.encode(self.encoding),
                self.digestmod
            )
            
            return hmac_obj.hexdigest()
            
        except Exception as e:
            raise ValueError(f"Failed to generate signature: {str(e)}")
    
    def verify_signature(self, signature: str, payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> bool:
        """
        Verify HMAC signature for webhook payload.
        
        Args:
            signature: The signature to verify
            payload: The payload that was signed
            secret: The secret key used for signing
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Generate expected signature
            expected_signature = self.generate_signature(payload, secret)
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            # If verification fails due to any error, return False
            return False
    
    def generate_base64_signature(self, payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> str:
        """
        Generate Base64-encoded HMAC signature.
        
        Args:
            payload: The payload to sign
            secret: The secret key for signing
            
        Returns:
            Base64-encoded HMAC signature
        """
        try:
            # Generate hex signature first
            hex_signature = self.generate_signature(payload, secret)
            
            # Convert to Base64
            signature_bytes = hex_signature.encode(self.encoding)
            base64_signature = base64.b64encode(signature_bytes).decode(self.encoding)
            
            return base64_signature
            
        except Exception as e:
            raise ValueError(f"Failed to generate Base64 signature: {str(e)}")
    
    def verify_base64_signature(self, signature: str, payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> bool:
        """
        Verify Base64-encoded HMAC signature.
        
        Args:
            signature: The Base64 signature to verify
            payload: The payload that was signed
            secret: The secret key used for signing
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Decode Base64 signature
            signature_bytes = base64.b64decode(signature.encode(self.encoding))
            hex_signature = signature_bytes.decode(self.encoding)
            
            # Verify hex signature
            return self.verify_signature(hex_signature, payload, secret)
            
        except Exception as e:
            # If verification fails due to any error, return False
            return False
    
    def generate_timestamped_signature(self, payload: Union[str, bytes, Dict[Any, Any]], secret: str, timestamp: int = None) -> Dict[str, str]:
        """
        Generate signature with timestamp for replay protection.
        
        Args:
            payload: The payload to sign
            secret: The secret key for signing
            timestamp: Unix timestamp (defaults to current time)
            
        Returns:
            Dictionary containing signature and timestamp
        """
        try:
            if timestamp is None:
                timestamp = int(timezone.now().timestamp())
            
            # Create timestamped payload
            if isinstance(payload, dict):
                timestamped_payload = payload.copy()
                timestamped_payload['timestamp'] = timestamp
            else:
                timestamped_payload = {
                    'payload': payload,
                    'timestamp': timestamp
                }
            
            # Generate signature
            signature = self.generate_signature(timestamped_payload, secret)
            
            return {
                'signature': signature,
                'timestamp': timestamp
            }
            
        except Exception as e:
            raise ValueError(f"Failed to generate timestamped signature: {str(e)}")
    
    def verify_timestamped_signature(self, signature: str, payload: Union[str, bytes, Dict[Any, Any]], secret: str, max_age: int = 300) -> bool:
        """
        Verify timestamped signature with replay protection.
        
        Args:
            signature: The signature to verify
            payload: The payload that was signed
            secret: The secret key used for signing
            max_age: Maximum age in seconds for valid signatures (default: 5 minutes)
            
        Returns:
            True if signature is valid and not expired, False otherwise
        """
        try:
            # Parse timestamped payload
            if isinstance(payload, dict):
                timestamp = payload.get('timestamp')
                if timestamp is None:
                    return False
            else:
                # For non-dict payloads, we can't verify timestamp
                return self.verify_signature(signature, payload, secret)
            
            # Check timestamp age
            current_time = int(timezone.now().timestamp())
            if current_time - timestamp > max_age:
                return False
            
            # Verify signature
            return self.verify_signature(signature, payload, secret)
            
        except Exception as e:
            # If verification fails due to any error, return False
            return False
    
    def generate_webhook_signature(self, payload: Union[str, bytes, Dict[Any, Any]], secret: str, timestamp: int = None, nonce: str = None) -> Dict[str, str]:
        """
        Generate comprehensive webhook signature with multiple security features.
        
        Args:
            payload: The payload to sign
            secret: The secret key for signing
            timestamp: Unix timestamp (defaults to current time)
            nonce: Unique nonce for replay protection
            
        Returns:
            Dictionary containing signature components
        """
        try:
            if timestamp is None:
                timestamp = int(timezone.now().timestamp())
            
            if nonce is None:
                import uuid
                nonce = str(uuid.uuid4())
            
            # Create webhook signature data
            signature_data = {
                'payload': payload,
                'timestamp': timestamp,
                'nonce': nonce
            }
            
            # Generate signature
            signature = self.generate_signature(signature_data, secret)
            
            return {
                'signature': signature,
                'timestamp': timestamp,
                'nonce': nonce,
                'algorithm': self.algorithm
            }
            
        except Exception as e:
            raise ValueError(f"Failed to generate webhook signature: {str(e)}")
    
    def verify_webhook_signature(self, signature_data: Dict[str, Any], payload: Union[str, bytes, Dict[Any, Any]], secret: str, max_age: int = 300) -> bool:
        """
        Verify comprehensive webhook signature.
        
        Args:
            signature_data: Dictionary containing signature components
            payload: The payload that was signed
            secret: The secret key used for signing
            max_age: Maximum age in seconds for valid signatures
            
        Returns:
            True if signature is valid and not expired, False otherwise
        """
        try:
            signature = signature_data.get('signature')
            timestamp = signature_data.get('timestamp')
            nonce = signature_data.get('nonce')
            algorithm = signature_data.get('algorithm', 'sha256')
            
            if not all([signature, timestamp, nonce]):
                return False
            
            # Check algorithm matches
            if algorithm != self.algorithm:
                return False
            
            # Check timestamp age
            current_time = int(timezone.now().timestamp())
            if current_time - timestamp > max_age:
                return False
            
            # Create verification data
            verification_data = {
                'payload': payload,
                'timestamp': timestamp,
                'nonce': nonce
            }
            
            # Verify signature
            return self.verify_signature(signature, verification_data, secret)
            
        except Exception as e:
            # If verification fails due to any error, return False
            return False
    
    def get_signature_headers(self, payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> Dict[str, str]:
        """
        Generate HTTP headers for webhook signature.
        
        Args:
            payload: The payload to sign
            secret: The secret key for signing
            
        Returns:
            Dictionary of HTTP headers
        """
        try:
            signature_data = self.generate_webhook_signature(payload, secret)
            
            return {
                'X-Webhook-Signature': signature_data['signature'],
                'X-Webhook-Timestamp': str(signature_data['timestamp']),
                'X-Webhook-Nonce': signature_data['nonce'],
                'X-Webhook-Algorithm': signature_data['algorithm']
            }
            
        except Exception as e:
            raise ValueError(f"Failed to generate signature headers: {str(e)}")
    
    def verify_signature_from_headers(self, headers: Dict[str, str], payload: Union[str, bytes, Dict[Any, Any]], secret: str) -> bool:
        """
        Verify signature from HTTP headers.
        
        Args:
            headers: HTTP headers containing signature information
            payload: The payload that was signed
            secret: The secret key used for signing
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            signature_data = {
                'signature': headers.get('X-Webhook-Signature'),
                'timestamp': headers.get('X-Webhook-Timestamp'),
                'nonce': headers.get('X-Webhook-Nonce'),
                'algorithm': headers.get('X-Webhook-Algorithm', 'sha256')
            }
            
            return self.verify_webhook_signature(signature_data, payload, secret)
            
        except Exception as e:
            # If verification fails due to any error, return False
            return False
    
    @staticmethod
    def get_supported_algorithms() -> list:
        """
        Get list of supported HMAC algorithms.
        
        Returns:
            List of supported algorithm names
        """
        return ['sha256', 'sha1', 'md5', 'sha384', 'sha512']
    
    @staticmethod
    def validate_algorithm(algorithm: str) -> bool:
        """
        Validate if algorithm is supported.
        
        Args:
            algorithm: Algorithm name to validate
            
        Returns:
            True if algorithm is supported, False otherwise
        """
        return algorithm.lower() in SignatureEngine.get_supported_algorithms()
    
    def set_algorithm(self, algorithm: str) -> None:
        """
        Set the HMAC algorithm.
        
        Args:
            algorithm: Algorithm name to use
        """
        if not self.validate_algorithm(algorithm):
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        self.algorithm = algorithm.lower()
        self.digestmod = getattr(hashlib, algorithm.upper(), hashlib.sha256)
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """
        Get information about the current algorithm.
        
        Returns:
            Dictionary with algorithm information
        """
        return {
            'algorithm': self.algorithm,
            'digestmod': self.digestmod.name,
            'encoding': self.encoding,
            'supported_algorithms': self.get_supported_algorithms()
        }
