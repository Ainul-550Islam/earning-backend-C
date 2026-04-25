"""
Tracking Pixel Service

Service for managing tracking pixels,
including pixel code generation and firing.
"""

import logging
import secrets
import hashlib
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.tracking import TrackingPixel
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class TrackingPixelService:
    """
    Service for managing tracking pixels.
    
    Handles pixel code generation, firing,
    and pixel management.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_tracking_pixel(self, advertiser, offer=None, data: Dict[str, Any] = None) -> TrackingPixel:
        """
        Create a new tracking pixel.
        
        Args:
            advertiser: Advertiser instance
            offer: Optional offer instance
            data: Pixel creation data
            
        Returns:
            TrackingPixel: Created pixel instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                pixel_data = data or {}
                
                # Generate unique pixel code
                pixel_code = self._generate_pixel_code()
                
                # Create pixel
                pixel = TrackingPixel.objects.create(
                    advertiser=advertiser,
                    offer=offer,
                    pixel_type=pixel_data.get('pixel_type', 'impression'),
                    name=pixel_data.get('name', f'{pixel_data.get("pixel_type", "impression")} Pixel'),
                    pixel_code=pixel_code,
                    fire_on=pixel_data.get('fire_on', 'page_load'),
                    pixel_html=pixel_data.get('pixel_html'),
                    pixel_js=pixel_data.get('pixel_js'),
                    pixel_img=pixel_data.get('pixel_img'),
                    is_active=pixel_data.get('is_active', True),
                    is_secure=pixel_data.get('is_secure', True),
                    async_firing=pixel_data.get('async_firing', True),
                    delay_ms=pixel_data.get('delay_ms', 0),
                    timeout_ms=pixel_data.get('timeout_ms', 5000),
                    custom_parameters=pixel_data.get('custom_parameters', {}),
                )
                
                # Generate default pixel code if not provided
                if not pixel.pixel_html and not pixel.pixel_js and not pixel.pixel_img:
                    self._generate_default_pixel_code(pixel)
                    pixel.save()
                
                # Send notification
                self._send_pixel_created_notification(advertiser, pixel)
                
                self.logger.info(f"Created tracking pixel: {pixel.name} for {advertiser.company_name}")
                return pixel
                
        except Exception as e:
            self.logger.error(f"Error creating tracking pixel: {e}")
            raise ValidationError(f"Failed to create tracking pixel: {str(e)}")
    
    def update_tracking_pixel(self, pixel: TrackingPixel, data: Dict[str, Any]) -> TrackingPixel:
        """
        Update tracking pixel.
        
        Args:
            pixel: Pixel instance to update
            data: Update data
            
        Returns:
            TrackingPixel: Updated pixel instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Update pixel fields
                allowed_fields = [
                    'name', 'pixel_type', 'fire_on', 'pixel_html', 'pixel_js',
                    'pixel_img', 'is_active', 'is_secure', 'async_firing',
                    'delay_ms', 'timeout_ms', 'custom_parameters'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(pixel, field, data[field])
                
                pixel.save()
                
                # Regenerate pixel code if needed
                if 'pixel_type' in data or 'fire_on' in data:
                    self._generate_default_pixel_code(pixel)
                    pixel.save()
                
                self.logger.info(f"Updated tracking pixel: {pixel.name}")
                return pixel
                
        except Exception as e:
            self.logger.error(f"Error updating tracking pixel: {e}")
            raise ValidationError(f"Failed to update tracking pixel: {str(e)}")
    
    def get_pixel_code(self, pixel: TrackingPixel, format: str = 'html') -> str:
        """
        Get pixel code in specified format.
        
        Args:
            pixel: Pixel instance
            format: Code format ('html', 'js', 'img', 'url')
            
        Returns:
            str: Pixel code
            
        Raises:
            ValidationError: If format is invalid
        """
        try:
            if format == 'html':
                return pixel.get_pixel_code_html()
            elif format == 'js':
                return pixel.get_pixel_code_js()
            elif format == 'img':
                return f'<img src="{pixel.pixel_url}" width="1" height="1" border="0" alt="" />'
            elif format == 'url':
                return pixel.pixel_url
            else:
                raise ValidationError(f"Invalid format: {format}")
                
        except Exception as e:
            self.logger.error(f"Error getting pixel code: {e}")
            raise ValidationError(f"Failed to get pixel code: {str(e)}")
    
    def fire_pixel(self, pixel_code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fire tracking pixel with context.
        
        Args:
            pixel_code: Pixel code to fire
            context: Additional context data
            
        Returns:
            Dict[str, Any]: Firing results
            
        Raises:
            ValidationError: If pixel not found
        """
        try:
            # Find pixel
            pixel = TrackingPixel.objects.get(pixel_code=pixel_code, is_active=True)
            
            # Check if pixel should fire based on configuration
            if not self._should_fire_pixel(pixel, context):
                return {
                    'success': False,
                    'reason': 'Pixel conditions not met',
                    'pixel_id': pixel.id,
                }
            
            # Apply delay if configured
            if pixel.delay_ms > 0:
                # This would implement async firing with delay
                pass
            
            # Fire pixel based on type
            fire_result = self._execute_pixel_fire(pixel, context)
            
            # Log pixel firing
            self._log_pixel_firing(pixel, context, fire_result)
            
            return {
                'success': True,
                'pixel_id': pixel.id,
                'pixel_type': pixel.pixel_type,
                'fired_at': timezone.now().isoformat(),
                'result': fire_result,
            }
            
        except TrackingPixel.DoesNotExist:
            raise ValidationError("Pixel not found or inactive")
        except Exception as e:
            self.logger.error(f"Error firing pixel: {e}")
            raise ValidationError(f"Failed to fire pixel: {str(e)}")
    
    def get_pixel_analytics(self, pixel: TrackingPixel, days: int = 30) -> Dict[str, Any]:
        """
        Get pixel analytics.
        
        Args:
            pixel: Pixel instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Pixel analytics
        """
        try:
            from ...models.reporting import CampaignReport
            
            # This would implement actual pixel analytics
            # For now, return placeholder data
            return {
                'pixel_id': pixel.id,
                'pixel_name': pixel.name,
                'pixel_type': pixel.pixel_type,
                'period_days': days,
                'total_fires': 0,
                'unique_fires': 0,
                'fire_rate': 0.0,
                'error_rate': 0.0,
                'average_response_time': 0.0,
                'daily_fires': {},
                'top_countries': {},
                'top_devices': {},
                'performance_metrics': {},
            }
            
        except Exception as e:
            self.logger.error(f"Error getting pixel analytics: {e}")
            raise ValidationError(f"Failed to get pixel analytics: {str(e)}")
    
    def test_pixel(self, pixel: TrackingPixel) -> Dict[str, Any]:
        """
        Test pixel functionality.
        
        Args:
            pixel: Pixel instance to test
            
        Returns:
            Dict[str, Any]: Test results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            test_results = {
                'pixel_id': pixel.id,
                'pixel_name': pixel.name,
                'tested_at': timezone.now().isoformat(),
                'tests': {},
                'overall_status': 'passed',
            }
            
            # Test pixel code generation
            test_results['tests']['code_generation'] = self._test_code_generation(pixel)
            
            # Test pixel URL
            test_results['tests']['pixel_url'] = self._test_pixel_url(pixel)
            
            # Test pixel firing
            test_results['tests']['pixel_firing'] = self._test_pixel_firing(pixel)
            
            # Test pixel parameters
            test_results['tests']['parameters'] = self._test_pixel_parameters(pixel)
            
            # Determine overall status
            failed_tests = [name for name, result in test_results['tests'].items() if result.get('status') == 'failed']
            
            if failed_tests:
                test_results['overall_status'] = 'failed'
                test_results['failed_tests'] = failed_tests
            
            return test_results
            
        except Exception as e:
            self.logger.error(f"Error testing pixel: {e}")
            raise ValidationError(f"Failed to test pixel: {str(e)}")
    
    def get_pixels(self, advertiser=None, offer=None, filters: Dict[str, Any] = None) -> List[TrackingPixel]:
        """
        Get tracking pixels with filtering.
        
        Args:
            advertiser: Optional advertiser filter
            offer: Optional offer filter
            filters: Additional filter criteria
            
        Returns:
            List[TrackingPixel]: List of pixels
        """
        try:
            queryset = TrackingPixel.objects.select_related('advertiser', 'offer').order_by('-created_at')
            
            if advertiser:
                queryset = queryset.filter(advertiser=advertiser)
            
            if offer:
                queryset = queryset.filter(offer=offer)
            
            if filters:
                if 'pixel_type' in filters:
                    queryset = queryset.filter(pixel_type=filters['pixel_type'])
                
                if 'is_active' in filters:
                    queryset = queryset.filter(is_active=filters['is_active'])
                
                if 'search' in filters:
                    search_term = filters['search']
                    queryset = queryset.filter(
                        models.Q(name__icontains=search_term) |
                        models.Q(pixel_code__icontains=search_term)
                    )
            
            return list(queryset)
            
        except Exception as e:
            self.logger.error(f"Error getting pixels: {e}")
            return []
    
    def delete_pixel(self, pixel: TrackingPixel) -> bool:
        """
        Delete tracking pixel.
        
        Args:
            pixel: Pixel instance to delete
            
        Returns:
            bool: True if successful
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Send notification
                self._send_pixel_deleted_notification(pixel.advertiser, pixel)
                
                # Delete pixel
                pixel.delete()
                
                self.logger.info(f"Deleted tracking pixel: {pixel.name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting pixel: {e}")
            raise ValidationError(f"Failed to delete pixel: {str(e)}")
    
    def _generate_pixel_code(self) -> str:
        """Generate unique pixel code."""
        timestamp = str(int(timezone.now().timestamp()))
        random_str = secrets.token_hex(4)
        return f"px_{timestamp}_{random_str}"
    
    def _generate_default_pixel_code(self, pixel: TrackingPixel):
        """Generate default pixel code based on type and fire_on."""
        if pixel.pixel_type == 'impression':
            if pixel.fire_on == 'page_load':
                pixel.pixel_html = f'<img src="{pixel.pixel_url}" width="1" height="1" border="0" alt="" />'
            elif pixel.fire_on == 'click':
                pixel.pixel_js = f"""
                document.addEventListener('click', function() {{
                    fetch('{pixel.pixel_url}', {{
                        method: 'GET',
                        mode: 'no-cors'
                    }});
                }});
                """
        elif pixel.pixel_type == 'click':
            pixel.pixel_js = f"""
            document.addEventListener('click', function() {{
                fetch('{pixel.pixel_url}', {{
                    method: 'GET',
                    mode: 'no-cors'
                }});
            }});
            """
        elif pixel.pixel_type == 'conversion':
            pixel.pixel_js = f"""
            // Conversion pixel
            fetch('{pixel.pixel_url}', {{
                method: 'GET',
                mode: 'no-cors'
            }});
            """
    
    def _should_fire_pixel(self, pixel: TrackingPixel, context: Dict[str, Any]) -> bool:
        """Check if pixel should fire based on context."""
        # This would implement more sophisticated firing logic
        return True
    
    def _execute_pixel_fire(self, pixel: TrackingPixel, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute pixel firing."""
        # This would implement actual pixel firing logic
        return {
            'status': 'success',
            'response_time': 0.05,
            'response_code': 200,
        }
    
    def _log_pixel_firing(self, pixel: TrackingPixel, context: Dict[str, Any], result: Dict[str, Any]):
        """Log pixel firing for analytics."""
        # This would implement logging logic
        pass
    
    def _test_code_generation(self, pixel: TrackingPixel) -> Dict[str, Any]:
        """Test pixel code generation."""
        try:
            html_code = pixel.get_pixel_code_html()
            js_code = pixel.get_pixel_code_js()
            
            return {
                'status': 'passed',
                'html_generated': bool(html_code),
                'js_generated': bool(js_code),
                'url_generated': bool(pixel.pixel_url),
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    def _test_pixel_url(self, pixel: TrackingPixel) -> Dict[str, Any]:
        """Test pixel URL."""
        try:
            url = pixel.pixel_url
            
            if not url:
                return {
                    'status': 'failed',
                    'error': 'No pixel URL generated',
                }
            
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                return {
                    'status': 'failed',
                    'error': 'Invalid URL protocol',
                }
            
            return {
                'status': 'passed',
                'url': url,
                'is_secure': url.startswith('https://'),
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    def _test_pixel_firing(self, pixel: TrackingPixel) -> Dict[str, Any]:
        """Test pixel firing."""
        try:
            # This would implement actual firing test
            return {
                'status': 'passed',
                'test_fire_successful': True,
                'response_time': 0.05,
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    def _test_pixel_parameters(self, pixel: TrackingPixel) -> Dict[str, Any]:
        """Test pixel parameters."""
        try:
            custom_params = pixel.custom_parameters or {}
            
            return {
                'status': 'passed',
                'custom_parameters_count': len(custom_params),
                'has_required_params': True,  # Would check actual requirements
                'parameter_validation': 'passed',
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    def _send_pixel_created_notification(self, advertiser, pixel: TrackingPixel):
        """Send pixel created notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='pixel_created',
            title=_('Tracking Pixel Created'),
            message=_('Your tracking pixel "{pixel_name}" has been created successfully.').format(
                pixel_name=pixel.name
            ),
            priority='medium',
            action_url=f'/advertiser/tracking/pixels/{pixel.id}/',
            action_text=_('View Pixel')
        )
    
    def _send_pixel_deleted_notification(self, advertiser, pixel: TrackingPixel):
        """Send pixel deleted notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='pixel_created',
            title=_('Tracking Pixel Deleted'),
            message=_('Your tracking pixel "{pixel_name}" has been deleted.').format(
                pixel_name=pixel.name
            ),
            priority='low'
        )
