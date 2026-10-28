# =============================================================================
# fraud_detection/webhooks.py
# =============================================================================
"""
Webhooks Integration Layer for Fraud Detection System.

Provides integration with third-party fraud databases, threat intelligence
feeds, and external fraud detection services via webhooks.
"""

from __future__ import annotations

import json
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.fraud_detection.encryption import encrypt_sensitive_data, generate_integrity_hash
from api.fraud_detection.exceptions import WebhookError, IntegrationError
from api.fraud_detection.constants import CACHE_TTL


logger = logging.getLogger(__name__)


class WebhookClient:
    """
    Base webhook client for third-party integrations.
    
    Provides secure webhook communication with retry logic,
    authentication, and error handling.
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None,
                 webhook_secret: Optional[str] = None, timeout: int = 30):
        """
        Initialize webhook client.
        
        Args:
            base_url: Base URL for webhook endpoints
            api_key: API key for authentication
            webhook_secret: Secret for webhook signature verification
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        
        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f'FraudDetectionSystem/1.0 (Webhook Client)'
        })
        
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}'
            })
    
    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """
        Generate HMAC signature for webhook payload.
        
        Args:
            payload: Payload to sign
            
        Returns:
            HMAC hex signature
        """
        if not self.webhook_secret:
            return ''
        
        payload_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _verify_signature(self, payload: Dict[str, Any], 
                         received_signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Received payload
            received_signature: Signature from webhook
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return True  # No verification if no secret configured
        
        expected_signature = self._generate_signature(payload)
        return hmac.compare_digest(expected_signature, received_signature)
    
    def send_webhook(self, endpoint: str, payload: Dict[str, Any],
                    method: str = 'POST') -> Dict[str, Any]:
        """
        Send webhook request to third-party service.
        
        Args:
            endpoint: Webhook endpoint
            payload: Request payload
            method: HTTP method
            
        Returns:
            Response data
            
        Raises:
            WebhookError: If webhook request fails
        """
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            
            # Add signature header if secret is configured
            headers = {}
            if self.webhook_secret:
                signature = self._generate_signature(payload)
                headers['X-Webhook-Signature'] = f"sha256={signature}"
            
            # Log request (without sensitive data)
            logger.info("Sending webhook to %s with method %s", url, method)
            
            # Send request
            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            # Check response
            response.raise_for_status()
            
            # Parse response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'status': 'success', 'response': response.text}
            
            logger.info("Webhook request successful: %s", url)
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error("Webhook request failed: %s", e, exc_info=True)
            raise WebhookError(f"Webhook request failed: {e}")
        except Exception as e:
            logger.error("Unexpected error in webhook request: %s", e, exc_info=True)
            raise WebhookError(f"Unexpected error: {e}")
    
    def receive_webhook(self, payload: Dict[str, Any], 
                       signature: Optional[str] = None) -> bool:
        """
        Receive and verify webhook from third-party service.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature for verification
            
        Returns:
            True if webhook is verified and processed
            
        Raises:
            WebhookError: If webhook verification fails
        """
        try:
            # Verify signature if provided
            if signature and not self._verify_signature(payload, signature):
                raise WebhookError("Webhook signature verification failed")
            
            # Process webhook payload
            self._process_webhook_payload(payload)
            
            logger.info("Webhook received and processed successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to process webhook: %s", e, exc_info=True)
            raise WebhookError(f"Failed to process webhook: {e}")
    
    def _process_webhook_payload(self, payload: Dict[str, Any]):
        """
        Process webhook payload.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _process_webhook_payload")


class FraudDatabaseWebhookClient(WebhookClient):
    """
    Webhook client for fraud database integrations.
    
    Integrates with external fraud databases, threat intelligence
    feeds, and fraud scoring services.
    """
    
    def __init__(self, database_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize fraud database webhook client.
        
        Args:
            database_name: Name of the fraud database
            config: Configuration for the database
        """
        self.database_name = database_name
        self.config = config or {}
        
        # Get configuration from settings
        db_configs = getattr(settings, 'FRAUD_DATABASE_CONFIGS', {})
        db_config = db_configs.get(database_name.lower(), {})
        
        base_url = db_config.get('base_url', '')
        api_key = db_config.get('api_key', '')
        webhook_secret = db_config.get('webhook_secret', '')
        timeout = db_config.get('timeout', 30)
        
        if not base_url:
            raise ImproperlyConfigured(f"No base_url configured for fraud database: {database_name}")
        
        super().__init__(base_url, api_key, webhook_secret, timeout)
        
        # Database-specific configuration
        self.supported_endpoints = db_config.get('supported_endpoints', [])
        self.rate_limit = db_config.get('rate_limit', 100)  # requests per minute
        self.last_request_time = None
    
    def check_ip_reputation(self, ip_address: str, 
                           additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check IP reputation against fraud database.
        
        Args:
            ip_address: IP address to check
            additional_data: Additional context data
            
        Returns:
            IP reputation data
        """
        if 'ip_reputation' not in self.supported_endpoints:
            raise IntegrationError(f"IP reputation check not supported by {self.database_name}")
        
        payload = {
            'ip_address': ip_address,
            'query_type': 'ip_reputation',
            'timestamp': timezone.now().isoformat()
        }
        
        if additional_data:
            payload.update(additional_data)
        
        return self.send_webhook('ip/reputation', payload)
    
    def check_email_reputation(self, email_address: str, 
                              additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check email reputation against fraud database.
        
        Args:
            email_address: Email address to check
            additional_data: Additional context data
            
        Returns:
            Email reputation data
        """
        if 'email_reputation' not in self.supported_endpoints:
            raise IntegrationError(f"Email reputation check not supported by {self.database_name}")
        
        payload = {
            'email_address': email_address,
            'query_type': 'email_reputation',
            'timestamp': timezone.now().isoformat()
        }
        
        if additional_data:
            payload.update(additional_data)
        
        return self.send_webhook('email/reputation', payload)
    
    def check_device_fingerprint(self, device_fingerprint: str, 
                               additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check device fingerprint against fraud database.
        
        Args:
            device_fingerprint: Device fingerprint to check
            additional_data: Additional context data
            
        Returns:
            Device fingerprint data
        """
        if 'device_fingerprint' not in self.supported_endpoints:
            raise IntegrationError(f"Device fingerprint check not supported by {self.database_name}")
        
        payload = {
            'device_fingerprint': device_fingerprint,
            'query_type': 'device_fingerprint',
            'timestamp': timezone.now().isoformat()
        }
        
        if additional_data:
            payload.update(additional_data)
        
        return self.send_webhook('device/fingerprint', payload)
    
    def submit_fraud_report(self, fraud_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit fraud report to external database.
        
        Args:
            fraud_data: Fraud incident data
            
        Returns:
            Submission response
        """
        if 'submit_fraud' not in self.supported_endpoints:
            raise IntegrationError(f"Fraud report submission not supported by {self.database_name}")
        
        payload = {
            'fraud_data': fraud_data,
            'submission_type': 'fraud_report',
            'timestamp': timezone.now().isoformat(),
            'source': 'fraud_detection_system'
        }
        
        return self.send_webhook('fraud/submit', payload)
    
    def get_threat_intelligence(self, query_type: str, 
                              query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get threat intelligence data.
        
        Args:
            query_type: Type of threat intelligence query
            query_params: Query parameters
            
        Returns:
            Threat intelligence data
        """
        if 'threat_intelligence' not in self.supported_endpoints:
            raise IntegrationError(f"Threat intelligence not supported by {self.database_name}")
        
        payload = {
            'query_type': query_type,
            'query_params': query_params,
            'timestamp': timezone.now().isoformat()
        }
        
        return self.send_webhook('threat/intelligence', payload)
    
    def _process_webhook_payload(self, payload: Dict[str, Any]):
        """Process incoming webhook payload from fraud database."""
        webhook_type = payload.get('webhook_type', '')
        
        if webhook_type == 'fraud_alert':
            self._handle_fraud_alert(payload)
        elif webhook_type == 'threat_update':
            self._handle_threat_update(payload)
        elif webhook_type == 'database_update':
            self._handle_database_update(payload)
        else:
            logger.warning("Unknown webhook type: %s", webhook_type)
    
    def _handle_fraud_alert(self, payload: Dict[str, Any]):
        """Handle fraud alert webhook."""
        alert_data = payload.get('alert_data', {})
        
        # Process fraud alert
        logger.info("Received fraud alert: %s", alert_data.get('alert_id', 'unknown'))
        
        # In practice, this would trigger internal fraud detection workflows
        # For now, just log the alert
        logger.info("Fraud alert details: %s", alert_data)
    
    def _handle_threat_update(self, payload: Dict[str, Any]):
        """Handle threat intelligence update webhook."""
        threat_data = payload.get('threat_data', {})
        
        # Process threat intelligence update
        logger.info("Received threat update: %s", threat_data.get('threat_id', 'unknown'))
        
        # In practice, this would update internal threat intelligence databases
        logger.info("Threat update details: %s", threat_data)
    
    def _handle_database_update(self, payload: Dict[str, Any]):
        """Handle database update webhook."""
        update_data = payload.get('update_data', {})
        
        # Process database update
        logger.info("Received database update: %s", update_data.get('update_id', 'unknown'))
        
        # In practice, this would sync with external database changes
        logger.info("Database update details: %s", update_data)


class ThreatIntelligenceAggregator:
    """
    Aggregator for multiple threat intelligence sources.
    
    Combines data from multiple fraud databases and
    threat intelligence feeds to provide comprehensive analysis.
    """
    
    def __init__(self):
        """Initialize threat intelligence aggregator."""
        self.clients = self._initialize_clients()
        self.aggregation_rules = self._load_aggregation_rules()
    
    def _initialize_clients(self) -> Dict[str, FraudDatabaseWebhookClient]:
        """Initialize webhook clients for configured databases."""
        clients = {}
        
        db_configs = getattr(settings, 'FRAUD_DATABASE_CONFIGS', {})
        
        for db_name, config in db_configs.items():
            if config.get('enabled', False):
                try:
                    client = FraudDatabaseWebhookClient(db_name, config)
                    clients[db_name] = client
                    logger.info("Initialized fraud database client: %s", db_name)
                except Exception as e:
                    logger.error("Failed to initialize client for %s: %s", db_name, e, exc_info=True)
        
        return clients
    
    def _load_aggregation_rules(self) -> Dict[str, Any]:
        """Load aggregation rules for combining threat intelligence."""
        default_rules = {
            'ip_reputation': {
                'weight_high': 0.8,
                'weight_medium': 0.6,
                'weight_low': 0.4,
                'consensus_threshold': 0.6
            },
            'email_reputation': {
                'weight_high': 0.7,
                'weight_medium': 0.5,
                'weight_low': 0.3,
                'consensus_threshold': 0.5
            },
            'device_fingerprint': {
                'weight_high': 0.9,
                'weight_medium': 0.7,
                'weight_low': 0.5,
                'consensus_threshold': 0.7
            }
        }
        
        return getattr(settings, 'THREAT_INTELLIGENCE_AGGREGATION_RULES', default_rules)
    
    def aggregate_ip_reputation(self, ip_address: str, 
                              additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Aggregate IP reputation from multiple sources.
        
        Args:
            ip_address: IP address to analyze
            additional_data: Additional context data
            
        Returns:
            Aggregated IP reputation data
        """
        results = []
        
        # Query all available clients
        for client_name, client in self.clients.items():
            try:
                if 'ip_reputation' in client.supported_endpoints:
                    result = client.check_ip_reputation(ip_address, additional_data)
                    results.append({
                        'source': client_name,
                        'data': result,
                        'timestamp': timezone.now().isoformat()
                    })
            except Exception as e:
                logger.error("Failed to get IP reputation from %s: %s", client_name, e, exc_info=True)
        
        # Aggregate results
        aggregated = self._aggregate_reputation_results(results, 'ip_reputation')
        
        return {
            'ip_address': ip_address,
            'aggregated_reputation': aggregated,
            'source_results': results,
            'aggregation_timestamp': timezone.now().isoformat()
        }
    
    def aggregate_email_reputation(self, email_address: str, 
                                  additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Aggregate email reputation from multiple sources.
        
        Args:
            email_address: Email address to analyze
            additional_data: Additional context data
            
        Returns:
            Aggregated email reputation data
        """
        results = []
        
        # Query all available clients
        for client_name, client in self.clients.items():
            try:
                if 'email_reputation' in client.supported_endpoints:
                    result = client.check_email_reputation(email_address, additional_data)
                    results.append({
                        'source': client_name,
                        'data': result,
                        'timestamp': timezone.now().isoformat()
                    })
            except Exception as e:
                logger.error("Failed to get email reputation from %s: %s", client_name, e, exc_info=True)
        
        # Aggregate results
        aggregated = self._aggregate_reputation_results(results, 'email_reputation')
        
        return {
            'email_address': email_address,
            'aggregated_reputation': aggregated,
            'source_results': results,
            'aggregation_timestamp': timezone.now().isoformat()
        }
    
    def aggregate_device_fingerprint(self, device_fingerprint: str, 
                                   additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Aggregate device fingerprint data from multiple sources.
        
        Args:
            device_fingerprint: Device fingerprint to analyze
            additional_data: Additional context data
            
        Returns:
            Aggregated device fingerprint data
        """
        results = []
        
        # Query all available clients
        for client_name, client in self.clients.items():
            try:
                if 'device_fingerprint' in client.supported_endpoints:
                    result = client.check_device_fingerprint(device_fingerprint, additional_data)
                    results.append({
                        'source': client_name,
                        'data': result,
                        'timestamp': timezone.now().isoformat()
                    })
            except Exception as e:
                logger.error("Failed to get device fingerprint from %s: %s", client_name, e, exc_info=True)
        
        # Aggregate results
        aggregated = self._aggregate_reputation_results(results, 'device_fingerprint')
        
        return {
            'device_fingerprint': device_fingerprint,
            'aggregated_reputation': aggregated,
            'source_results': results,
            'aggregation_timestamp': timezone.now().isoformat()
        }
    
    def submit_fraud_reports(self, fraud_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit fraud reports to multiple databases.
        
        Args:
            fraud_data: Fraud incident data
            
        Returns:
            Submission results from all databases
        """
        submission_results = []
        
        # Submit to all available clients
        for client_name, client in self.clients.items():
            try:
                if 'submit_fraud' in client.supported_endpoints:
                    result = client.submit_fraud_report(fraud_data)
                    submission_results.append({
                        'source': client_name,
                        'result': result,
                        'timestamp': timezone.now().isoformat()
                    })
            except Exception as e:
                logger.error("Failed to submit fraud report to %s: %s", client_name, e, exc_info=True)
        
        return {
            'fraud_data_id': fraud_data.get('incident_id', 'unknown'),
            'submission_results': submission_results,
            'submission_timestamp': timezone.now().isoformat()
        }
    
    def _aggregate_reputation_results(self, results: List[Dict[str, Any]], 
                                   result_type: str) -> Dict[str, Any]:
        """Aggregate reputation results from multiple sources."""
        if not results:
            return {
                'overall_score': 0,
                'risk_level': 'low',
                'confidence': 0,
                'source_count': 0
            }
        
        rules = self.aggregation_rules.get(result_type, {})
        
        # Extract scores from results
        scores = []
        for result in results:
            data = result.get('data', {})
            score = data.get('risk_score', 0)
            if isinstance(score, (int, float)):
                scores.append(score)
        
        if not scores:
            return {
                'overall_score': 0,
                'risk_level': 'low',
                'confidence': 0,
                'source_count': len(results)
            }
        
        # Calculate weighted average
        weights = []
        for score in scores:
            if score >= 70:
                weights.append(rules.get('weight_high', 0.8))
            elif score >= 40:
                weights.append(rules.get('weight_medium', 0.6))
            else:
                weights.append(rules.get('weight_low', 0.4))
        
        if weights:
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            weighted_score = sum(scores) / len(scores)
        
        # Determine risk level
        if weighted_score >= 70:
            risk_level = 'high'
        elif weighted_score >= 40:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Calculate confidence based on source consensus
        consensus_threshold = rules.get('consensus_threshold', 0.6)
        high_risk_count = sum(1 for score in scores if score >= 70)
        consensus_ratio = high_risk_count / len(scores) if scores else 0
        
        confidence = min(consensus_ratio / consensus_threshold, 1.0) if consensus_threshold > 0 else 0.5
        
        return {
            'overall_score': int(weighted_score),
            'risk_level': risk_level,
            'confidence': confidence,
            'source_count': len(results),
            'individual_scores': scores,
            'average_score': int(sum(scores) / len(scores)) if scores else 0
        }


# Global instances for easy access
threat_intelligence_aggregator = ThreatIntelligenceAggregator()


def check_ip_reputation_external(ip_address: str, 
                                additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for external IP reputation checking.
    
    Args:
        ip_address: IP address to check
        additional_data: Additional context data
        
    Returns:
        Aggregated IP reputation data
    """
    return threat_intelligence_aggregator.aggregate_ip_reputation(ip_address, additional_data)


def check_email_reputation_external(email_address: str, 
                                  additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for external email reputation checking.
    
    Args:
        email_address: Email address to check
        additional_data: Additional context data
        
    Returns:
        Aggregated email reputation data
    """
    return threat_intelligence_aggregator.aggregate_email_reputation(email_address, additional_data)


def submit_fraud_to_external_databases(fraud_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for submitting fraud reports to external databases.
    
    Args:
        fraud_data: Fraud incident data
        
    Returns:
        Submission results
    """
    return threat_intelligence_aggregator.submit_fraud_reports(fraud_data)
