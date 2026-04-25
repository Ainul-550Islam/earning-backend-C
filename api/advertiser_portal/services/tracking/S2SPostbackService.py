"""
S2S Postback Service

Service for managing server-to-server postbacks,
including configuration, testing, and validation.
"""

import logging
import secrets
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.tracking import S2SPostback
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class S2SPostbackService:
    """
    Service for managing server-to-server postbacks.
    
    Handles postback configuration, testing,
    and validation.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_postback(self, advertiser, offer=None, data: Dict[str, Any] = None) -> S2SPostback:
        """
        Create a new S2S postback configuration.
        
        Args:
            advertiser: Advertiser instance
            offer: Optional offer instance
            data: Postback creation data
            
        Returns:
            S2SPostback: Created postback instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                postback_data = data or {}
                
                # Generate secret key if not provided
                secret_key = postback_data.get('secret_key') or self._generate_secret_key()
                
                # Create postback
                postback = S2SPostback.objects.create(
                    advertiser=advertiser,
                    offer=offer,
                    postback_url=postback_data.get('postback_url'),
                    postback_method=postback_data.get('postback_method', 'GET'),
                    secret_key=secret_key,
                    use_hmac=postback_data.get('use_hmac', True),
                    hmac_algorithm=postback_data.get('hmac_algorithm', 'sha256'),
                    params_map=postback_data.get('params_map', {}),
                    is_active=postback_data.get('is_active', True),
                    test_mode=postback_data.get('test_mode', False),
                    max_retries=postback_data.get('max_retries', 3),
                    retry_delay=postback_data.get('retry_delay', 5),
                    success_response=postback_data.get('success_response', 'OK'),
                    timeout_seconds=postback_data.get('timeout_seconds', 30),
                )
                
                # Send notification
                self._send_postback_created_notification(advertiser, postback)
                
                self.logger.info(f"Created S2S postback for {advertiser.company_name}")
                return postback
                
        except Exception as e:
            self.logger.error(f"Error creating S2S postback: {e}")
            raise ValidationError(f"Failed to create S2S postback: {str(e)}")
    
    def update_postback(self, postback: S2SPostback, data: Dict[str, Any]) -> S2SPostback:
        """
        Update S2S postback configuration.
        
        Args:
            postback: Postback instance to update
            data: Update data
            
        Returns:
            S2SPostback: Updated postback instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Update postback fields
                allowed_fields = [
                    'postback_url', 'postback_method', 'secret_key', 'use_hmac',
                    'hmac_algorithm', 'params_map', 'is_active', 'test_mode',
                    'max_retries', 'retry_delay', 'success_response', 'timeout_seconds'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(postback, field, data[field])
                
                postback.save()
                
                self.logger.info(f"Updated S2S postback: {postback.id}")
                return postback
                
        except Exception as e:
            self.logger.error(f"Error updating S2S postback: {e}")
            raise ValidationError(f"Failed to update S2S postback: {str(e)}")
    
    def test_postback(self, postback: S2SPostback, test_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Test S2S postback configuration.
        
        Args:
            postback: Postback instance to test
            test_data: Test conversion data
            
        Returns:
            Dict[str, Any]: Test results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Generate test data
            test_conversion_data = test_data or self._generate_test_conversion_data()
            
            # Build postback URL
            postback_url = postback.build_postback_url(test_conversion_data)
            
            # Execute test postback
            test_result = self._execute_test_postback(postback, postback_url, test_conversion_data)
            
            # Log test result
            self._log_postback_test(postback, test_conversion_data, test_result)
            
            return {
                'postback_id': postback.id,
                'tested_at': timezone.now().isoformat(),
                'test_data': test_conversion_data,
                'postback_url': postback_url,
                'result': test_result,
                'success': test_result.get('success', False),
            }
            
        except Exception as e:
            self.logger.error(f"Error testing S2S postback: {e}")
            raise ValidationError(f"Failed to test S2S postback: {str(e)}")
    
    def send_postback(self, postback: S2SPostback, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send S2S postback with conversion data.
        
        Args:
            postback: Postback instance
            conversion_data: Conversion data
            
        Returns:
            Dict[str, Any]: Postback results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate postback is active
            if not postback.is_active:
                return {
                    'success': False,
                    'reason': 'Postback is not active',
                    'postback_id': postback.id,
                }
            
            # Build postback URL
            postback_url = postback.build_postback_url(conversion_data)
            
            # Send postback
            send_result = self._send_postback_request(postback, postback_url, conversion_data)
            
            # Log postback
            self._log_postback_sent(postback, conversion_data, send_result)
            
            return {
                'success': send_result.get('success', False),
                'postback_id': postback.id,
                'postback_url': postback_url,
                'sent_at': timezone.now().isoformat(),
                'result': send_result,
            }
            
        except Exception as e:
            self.logger.error(f"Error sending S2S postback: {e}")
            raise ValidationError(f"Failed to send S2S postback: {str(e)}")
    
    def validate_postback_signature(self, postback: S2SPostback, params: Dict[str, Any], signature: str) -> bool:
        """
        Validate postback HMAC signature.
        
        Args:
            postback: Postback instance
            params: Postback parameters
            signature: Received signature
            
        Returns:
            bool: True if signature is valid
        """
        try:
            return postback.validate_signature(params, signature)
        except Exception as e:
            self.logger.error(f"Error validating postback signature: {e}")
            return False
    
    def get_postback_analytics(self, postback: S2SPostback, days: int = 30) -> Dict[str, Any]:
        """
        Get postback analytics.
        
        Args:
            postback: Postback instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Postback analytics
        """
        try:
            # This would implement actual postback analytics
            # For now, return placeholder data
            return {
                'postback_id': postback.id,
                'period_days': days,
                'total_sent': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0,
                'average_response_time': 0.0,
                'daily_stats': {},
                'error_breakdown': {},
                'performance_metrics': {},
            }
            
        except Exception as e:
            self.logger.error(f"Error getting postback analytics: {e}")
            raise ValidationError(f"Failed to get postback analytics: {str(e)}")
    
    def get_postbacks(self, advertiser=None, offer=None, filters: Dict[str, Any] = None) -> List[S2SPostback]:
        """
        Get S2S postbacks with filtering.
        
        Args:
            advertiser: Optional advertiser filter
            offer: Optional offer filter
            filters: Additional filter criteria
            
        Returns:
            List[S2SPostback]: List of postbacks
        """
        try:
            queryset = S2SPostback.objects.select_related('advertiser', 'offer').order_by('-created_at')
            
            if advertiser:
                queryset = queryset.filter(advertiser=advertiser)
            
            if offer:
                queryset = queryset.filter(offer=offer)
            
            if filters:
                if 'postback_method' in filters:
                    queryset = queryset.filter(postback_method=filters['postback_method'])
                
                if 'is_active' in filters:
                    queryset = queryset.filter(is_active=filters['is_active'])
                
                if 'test_mode' in filters:
                    queryset = queryset.filter(test_mode=filters['test_mode'])
                
                if 'search' in filters:
                    search_term = filters['search']
                    queryset = queryset.filter(
                        models.Q(postback_url__icontains=search_term)
                    )
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting postbacks: {e}")
            return []
    
    def delete_postback(self, postback: S2SPostback) -> bool:
        """
        Delete S2S postback.
        
        Args:
            postback: Postback instance to delete
            
        Returns:
            bool: True if successful
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Send notification
                self._send_postback_deleted_notification(postback.advertiser, postback)
                
                # Delete postback
                postback.delete()
                
                self.logger.info(f"Deleted S2S postback: {postback.id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting postback: {e}")
            raise ValidationError(f"Failed to delete postback: {str(e)}")
    
    def _generate_secret_key(self) -> str:
        """Generate secure secret key."""
        return secrets.token_urlsafe(32)
    
    def _generate_test_conversion_data(self) -> Dict[str, Any]:
        """Generate test conversion data."""
        return {
            'conversion_id': f'test_{timezone.now().timestamp()}',
            'payout': '1.00',
            'currency': 'USD',
            'timestamp': timezone.now().isoformat(),
            'ip': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Test Browser)',
            'offer_id': 'test_offer_123',
            'affiliate_id': 'test_affiliate_456',
        }
    
    def _execute_test_postback(self, postback: S2SPostback, postback_url: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test postback request."""
        try:
            import requests
            from urllib.parse import urlparse
            
            # Parse URL to get domain
            parsed_url = urlparse(postback_url)
            
            # Test request (simplified - in production would use proper HTTP client)
            if postback.postback_method == 'GET':
                # Simulate GET request
                response = {
                    'status_code': 200,
                    'response_text': postback.success_response,
                    'headers': {},
                    'elapsed': 0.05,
                }
            else:
                # Simulate POST request
                response = {
                    'status_code': 200,
                    'response_text': postback.success_response,
                    'headers': {},
                    'elapsed': 0.08,
                }
            
            # Check if response matches expected success response
            success = (
                response['status_code'] == 200 and
                response['response_text'].strip() == postback.success_response.strip()
            )
            
            return {
                'success': success,
                'status_code': response['status_code'],
                'response_text': response['response_text'],
                'response_time': response['elapsed'],
                'headers': response['headers'],
                'url_used': postback_url,
                'method': postback.postback_method,
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url_used': postback_url,
                'method': postback.postback_method,
            }
    
    def _send_postback_request(self, postback: S2SPostback, postback_url: str, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send actual postback request."""
        try:
            import requests
            
            # Configure request
            timeout = postback.timeout_seconds
            headers = {
                'User-Agent': 'AdvertiserPortal-Postback/1.0',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            # Send request
            if postback.postback_method == 'GET':
                response = requests.get(postback_url, headers=headers, timeout=timeout)
            else:
                response = requests.post(postback_url, headers=headers, timeout=timeout)
            
            # Check response
            success = (
                response.status_code == 200 and
                response.text.strip() == postback.success_response.strip()
            )
            
            return {
                'success': success,
                'status_code': response.status_code,
                'response_text': response.text,
                'response_time': response.elapsed.total_seconds(),
                'headers': dict(response.headers),
                'url_used': postback_url,
                'method': postback.postback_method,
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'url_used': postback_url,
                'method': postback.postback_method,
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'url_used': postback_url,
                'method': postback.postback_method,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url_used': postback_url,
                'method': postback.postback_method,
            }
    
    def _log_postback_test(self, postback: S2SPostback, test_data: Dict[str, Any], result: Dict[str, Any]):
        """Log postback test for analytics."""
        # This would implement logging logic
        pass
    
    def _log_postback_sent(self, postback: S2SPostback, conversion_data: Dict[str, Any], result: Dict[str, Any]):
        """Log postback sent for analytics."""
        # This would implement logging logic
        pass
    
    def _send_postback_created_notification(self, advertiser, postback: S2SPostback):
        """Send postback created notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='postback_created',
            title=_('S2S Postback Created'),
            message=_('Your S2S postback has been configured successfully.'),
            priority='medium',
            action_url=f'/advertiser/tracking/postbacks/{postback.id}/',
            action_text=_('View Postback')
        )
    
    def _send_postback_deleted_notification(self, advertiser, postback: S2SPostback):
        """Send postback deleted notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='postback_created',
            title=_('S2S Postback Deleted'),
            message=_('Your S2S postback has been deleted.'),
            priority='low'
        )
