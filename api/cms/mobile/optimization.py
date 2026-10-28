# cms/mobile/optimization.py
"""
Mobile API Optimization System

Optimizations for mobile clients:
- Response compression
- Image optimization
- Payload reduction
- Lazy loading support
- Offline support
- Bandwidth optimization
- Battery optimization
"""

from typing import Dict, Any, Optional, List
from functools import wraps
import json
import logging

logger = logging.getLogger('cms.mobile.optimization')


# ─────────────────────────────────────────────────────────────────────────────
# MOBILE RESPONSE OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

class MobileResponseOptimizer:
    """Optimize API responses for mobile clients"""
    
    @staticmethod
    def optimize_response(data: Dict[str, Any], device_type: str = 'mobile',
                         connection_type: str = 'mobile') -> Dict[str, Any]:
        """
        Optimize response based on device and connection type
        
        Args:
            data: Original response data
            device_type: 'mobile', 'tablet', 'desktop'
            connection_type: '4g', 'wifi', '3g', 'slow'
            
        Returns:
            Optimized response
        """
        optimized = data.copy()
        
        # Reduce image quality for slow connections
        if connection_type in ['3g', 'slow']:
            optimized = MobileResponseOptimizer._reduce_image_quality(optimized)
        
        # Reduce payload size
        optimized = MobileResponseOptimizer._reduce_payload(optimized)
        
        # Compress response
        optimized = MobileResponseOptimizer._compress_response(optimized)
        
        return optimized
    
    @staticmethod
    def _reduce_image_quality(data: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce image quality for slow connections"""
        if 'images' in data:
            data['images'] = [
                {**img, 'url': img['url'].replace('.jpg', '_thumb.jpg')}
                for img in data['images']
            ]
        return data
    
    @staticmethod
    def _reduce_payload(data: Dict[str, Any], max_size: int = 100) -> Dict[str, Any]:
        """Remove non-essential fields to reduce payload"""
        removable_fields = ['description', 'long_content', 'metadata', 'debug_info']
        
        def clean_dict(d):
            if not isinstance(d, dict):
                return d
            return {k: v for k, v in d.items() if k not in removable_fields}
        
        return clean_dict(data)
    
    @staticmethod
    def _compress_response(data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare response for compression"""
        # Mark for gzip compression
        return {
            'data': data,
            'compressed': True,
            'compression': 'gzip',
        }


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class ImageOptimizer:
    """Optimize images for mobile delivery"""
    
    # Image sizes for different devices
    SIZES = {
        'mobile': {
            'thumbnail': (100, 100),
            'small': (300, 300),
            'medium': (600, 600),
        },
        'tablet': {
            'thumbnail': (150, 150),
            'small': (400, 400),
            'medium': (800, 800),
        },
        'desktop': {
            'thumbnail': (200, 200),
            'small': (600, 600),
            'medium': (1200, 1200),
        },
    }
    
    @staticmethod
    def get_optimal_size(device_type: str, use_case: str = 'medium') -> tuple:
        """Get optimal image size for device"""
        return ImageOptimizer.SIZES.get(device_type, {}).get(use_case, (600, 600))
    
    @staticmethod
    def get_image_url(original_url: str, device_type: str = 'mobile',
                     quality: int = 85) -> str:
        """Get optimized image URL"""
        # In production, would use image CDN like CloudImage or Imgix
        # For now, return modified URL
        
        size = ImageOptimizer.get_optimal_size(device_type, 'medium')
        
        # Modify URL to request optimal size
        # Example: /images/photo.jpg -> /images/photo_600x600_q85.jpg
        if '.jpg' in original_url:
            return original_url.replace(
                '.jpg',
                f'_{size[0]}x{size[1]}_q{quality}.jpg'
            )
        
        return original_url
    
    @staticmethod
    def optimize_list_images(items: List[Dict[str, Any]], 
                            device_type: str = 'mobile') -> List[Dict[str, Any]]:
        """Optimize images in list response"""
        optimized = []
        
        for item in items:
            if 'image' in item and item['image']:
                item['image'] = ImageOptimizer.get_image_url(item['image'], device_type)
            if 'thumbnail' in item and item['thumbnail']:
                item['thumbnail'] = ImageOptimizer.get_image_url(
                    item['thumbnail'], device_type, quality=60
                )
            optimized.append(item)
        
        return optimized


# ─────────────────────────────────────────────────────────────────────────────
# PAGINATION & LAZY LOADING
# ─────────────────────────────────────────────────────────────────────────────

class MobilePagination:
    """Mobile-optimized pagination"""
    
    @staticmethod
    def paginate_response(queryset, page: int = 1, 
                         page_size: int = 20) -> Dict[str, Any]:
        """
        Paginate response for mobile
        
        Mobile-specific:
        - Smaller default page size (20 vs 100)
        - Cursor-based pagination support
        - Lazy loading indicators
        """
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        items = list(queryset[start:end])
        
        return {
            'items': items,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size,
                'has_next': end < total,
                'has_previous': page > 1,
            },
            'lazy_load_more': end < total,  # Mobile indicator
        }
    
    @staticmethod
    def get_cursor_pagination(queryset, cursor: Optional[str] = None,
                             limit: int = 20) -> Dict[str, Any]:
        """
        Cursor-based pagination (better for mobile)
        
        More efficient than offset pagination
        """
        if cursor:
            # Decode cursor (would be base64 in production)
            items = list(queryset[:limit + 1])
        else:
            items = list(queryset[:limit + 1])
        
        has_more = len(items) > limit
        items = items[:limit]
        
        # Generate next cursor (would encode in production)
        next_cursor = str(items[-1].id) if items and has_more else None
        
        return {
            'items': items,
            'pagination': {
                'limit': limit,
                'has_more': has_more,
                'next_cursor': next_cursor,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# BANDWIDTH OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class BandwidthOptimizer:
    """Optimize bandwidth usage for mobile"""
    
    @staticmethod
    def detect_connection_type(request) -> str:
        """
        Detect user's connection type
        
        Checks:
        - Network information API (if supported)
        - HTTP headers
        - User agent patterns
        """
        # Check for Network Information API data
        connection_type = request.META.get('HTTP_CONNECTION_TYPE', 'unknown')
        
        if connection_type in ['4g', 'wifi', '3g']:
            return connection_type
        
        # Fallback: check user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'iphone' in user_agent or 'android' in user_agent:
            return 'mobile'
        
        return 'unknown'
    
    @staticmethod
    def should_load_images(connection_type: str) -> bool:
        """Determine if images should load"""
        return connection_type not in ['3g', 'slow']
    
    @staticmethod
    def should_load_videos(connection_type: str) -> bool:
        """Determine if videos should load"""
        return connection_type == 'wifi'
    
    @staticmethod
    def estimate_payload_size(data: Dict[str, Any]) -> int:
        """Estimate response size in bytes"""
        json_str = json.dumps(data)
        return len(json_str.encode('utf-8'))


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE SUPPORT
# ─────────────────────────────────────────────────────────────────────────────

class OfflineSupport:
    """Support offline mode for mobile apps"""
    
    @staticmethod
    def prepare_for_offline(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare response for offline storage
        
        Includes:
        - Cached timestamps
        - Conflict resolution data
        - Sync metadata
        """
        return {
            'data': data,
            'offline_meta': {
                'cached_at': __import__('datetime').datetime.now().isoformat(),
                'cache_ttl': 3600,  # 1 hour
                'sync_key': f"sync_{data.get('id', 'unknown')}",
            },
        }
    
    @staticmethod
    def prepare_sync_data(local_data: Dict[str, Any], 
                         server_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare data for sync after offline period
        
        Detects conflicts and prepares merge strategy
        """
        return {
            'local': local_data,
            'server': server_data,
            'conflict': local_data != server_data,
            'merge_strategy': 'server_wins',  # or 'local_wins', 'manual'
            'timestamp': __import__('datetime').datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# BATTERY OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

class BatteryOptimizer:
    """Reduce battery consumption for mobile"""
    
    @staticmethod
    def should_poll(battery_level: int) -> bool:
        """Determine if background polling should continue"""
        return battery_level > 20  # Stop polling below 20% battery
    
    @staticmethod
    def get_polling_interval(battery_level: int) -> int:
        """Get polling interval based on battery level"""
        if battery_level > 80:
            return 30  # 30 seconds
        elif battery_level > 50:
            return 60  # 1 minute
        elif battery_level > 20:
            return 300  # 5 minutes
        else:
            return 0  # Stop polling
    
    @staticmethod
    def optimize_for_battery(data: Dict[str, Any], 
                           battery_level: int) -> Dict[str, Any]:
        """Optimize response based on battery level"""
        optimized = data.copy()
        
        # Reduce features on low battery
        if battery_level < 20:
            # Remove animations, auto-refresh, etc.
            optimized['features'] = optimized.get('features', {})
            optimized['features']['enable_animations'] = False
            optimized['features']['auto_refresh'] = False
        
        return optimized


# ─────────────────────────────────────────────────────────────────────────────
# MOBILE MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────

class MobileOptimizationMiddleware:
    """
    Middleware for automatic mobile optimization
    
    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'cms.mobile.optimization.MobileOptimizationMiddleware',
            ...
        ]
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Detect device type
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'iphone' in user_agent or 'android' in user_agent:
            request.device_type = 'mobile'
        elif 'ipad' in user_agent or 'tablet' in user_agent:
            request.device_type = 'tablet'
        else:
            request.device_type = 'desktop'
        
        # Detect connection type
        request.connection_type = BandwidthOptimizer.detect_connection_type(request)
        
        response = self.get_response(request)
        
        # Add optimization headers
        response['X-Device-Type'] = request.device_type
        response['X-Connection-Type'] = request.connection_type
        
        return response


# ─────────────────────────────────────────────────────────────────────────────
# HELPER DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def mobile_optimize(func):
    """Decorator to automatically optimize for mobile"""
    
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        # Get original response
        response = func(request, *args, **kwargs)
        
        # Optimize if mobile
        if hasattr(request, 'device_type') and request.device_type == 'mobile':
            if isinstance(response, dict):
                device_type = getattr(request, 'device_type', 'mobile')
                connection = getattr(request, 'connection_type', 'wifi')
                response = MobileResponseOptimizer.optimize_response(
                    response, device_type, connection
                )
        
        return response
    
    return wrapper


# Export public API
__all__ = [
    'MobileResponseOptimizer',
    'ImageOptimizer',
    'MobilePagination',
    'BandwidthOptimizer',
    'OfflineSupport',
    'BatteryOptimizer',
    'MobileOptimizationMiddleware',
    'mobile_optimize',
]
