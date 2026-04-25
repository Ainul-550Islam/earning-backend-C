"""
api/ad_networks/utils.py
Utility functions for ad networks module
SaaS-ready with tenant support
"""

import os
import uuid
import hashlib
import logging
import json
import magic
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import re

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import Offer, AdNetwork, OfferAttachment, UserOfferEngagement
from .constants import UPLOAD_SETTINGS, STORAGE_CONFIG

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== FILE UTILITIES ====================

def generate_secure_filename(original_filename: str) -> str:
    """
    Generate a secure filename to prevent path traversal and name conflicts
    """
    # Get file extension
    name, extension = os.path.splitext(original_filename)
    
    # Sanitize filename
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    safe_name = safe_name[:50]  # Limit length
    
    # Generate UUID for uniqueness
    unique_id = str(uuid.uuid4())[:8]
    
    # Combine with timestamp for additional uniqueness
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create secure filename
    secure_filename = f"{timestamp}_{unique_id}_{safe_name}{extension}"
    
    return secure_filename


def calculate_file_hash(file_obj) -> str:
    """
    Calculate SHA-256 hash of file for integrity verification
    """
    hash_sha256 = hashlib.sha256()
    
    # Reset file pointer
    file_obj.seek(0)
    
    # Read file in chunks
    for chunk in iter(lambda: file_obj.read(4096), b""):
        hash_sha256.update(chunk)
    
    # Reset file pointer
    file_obj.seek(0)
    
    return hash_sha256.hexdigest()


def get_file_metadata(file_obj) -> Dict[str, Any]:
    """
    Extract metadata from uploaded file
    """
    metadata = {}
    
    try:
        # Basic file info
        metadata['size'] = file_obj.size
        metadata['name'] = file_obj.name
        metadata['content_type'] = file_obj.content_type
        
        # MIME type detection
        try:
            file_content = file_obj.read(1024)
            file_obj.seek(0)
            metadata['detected_mime_type'] = magic.from_buffer(file_content, mime=True)
        except Exception:
            metadata['detected_mime_type'] = file_obj.content_type
        
        # Image specific metadata
        if metadata['detected_mime_type'].startswith('image/'):
            try:
                from PIL import Image
                image = Image.open(file_obj)
                metadata['width'] = image.width
                metadata['height'] = image.height
                metadata['format'] = image.format
                metadata['mode'] = image.mode
                
                # Reset file pointer
                file_obj.seek(0)
                
            except Exception as e:
                logger.warning(f"Could not extract image metadata: {str(e)}")
        
        # Document specific metadata
        elif metadata['detected_mime_type'] == 'application/pdf':
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(file_obj)
                metadata['pages'] = len(pdf_reader.pages)
                metadata['title'] = pdf_reader.metadata.get('/Title', '') if pdf_reader.metadata else ''
                metadata['author'] = pdf_reader.metadata.get('/Author', '') if pdf_reader.metadata else ''
                
                # Reset file pointer
                file_obj.seek(0)
                
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error extracting file metadata: {str(e)}")
    
    return metadata


def create_thumbnail(image_file, size=(300, 300)) -> Optional[ContentFile]:
    """
    Create thumbnail from image file
    """
    try:
        from PIL import Image, ImageOps
        
        # Open image
        image = Image.open(image_file)
        
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        
        # Create thumbnail
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Convert to ContentFile
        from io import BytesIO
        thumb_io = BytesIO()
        image.save(thumb_io, format='JPEG', quality=85)
        thumb_io.seek(0)
        
        return ContentFile(thumb_io.read(), name=f"thumb_{image_file.name}")
        
    except Exception as e:
        logger.error(f"Error creating thumbnail: {str(e)}")
        return None


def upload_file_securely(file_obj, upload_to=None, tenant_id='default') -> Dict[str, Any]:
    """
    Securely upload file with validation and metadata extraction
    """
    try:
        # Generate secure filename
        secure_filename = generate_secure_filename(file_obj.name)
        
        # Determine upload path
        if upload_to:
            upload_path = f"{upload_to}/{tenant_id}/{secure_filename}"
        else:
            upload_path = f"{STORAGE_CONFIG['UPLOAD_TO']}/{tenant_id}/{secure_filename}"
        
        # Calculate file hash
        file_hash = calculate_file_hash(file_obj)
        
        # Extract metadata
        metadata = get_file_metadata(file_obj)
        
        # Check for duplicate files
        existing_attachment = OfferAttachment.objects.filter(
            file_hash=file_hash,
            tenant_id=tenant_id
        ).first()
        
        if existing_attachment:
            return {
                'success': True,
                'attachment': existing_attachment,
                'is_duplicate': True,
                'message': 'File already exists'
            }
        
        # Upload file
        file_path = default_storage.save(upload_path, file_obj)
        
        # Create thumbnail for images
        thumbnail_path = None
        if metadata.get('detected_mime_type', '').startswith('image/'):
            thumbnail = create_thumbnail(file_obj)
            if thumbnail:
                thumbnail_filename = f"thumb_{secure_filename}"
                thumbnail_upload_path = f"{STORAGE_CONFIG['UPLOAD_TO']}/{tenant_id}/thumbnails/{thumbnail_filename}"
                thumbnail_path = default_storage.save(thumbnail_upload_path, thumbnail)
        
        return {
            'success': True,
            'file_path': file_path,
            'thumbnail_path': thumbnail_path,
            'file_hash': file_hash,
            'metadata': metadata,
            'secure_filename': secure_filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading file securely: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# ==================== OFFER UTILITIES ====================

def calculate_offer_performance_score(offer) -> float:
    """
    Calculate performance score for an offer based on various metrics
    """
    try:
        # Get offer statistics
        engagements = UserOfferEngagement.objects.filter(offer=offer)
        conversions = OfferConversion.objects.filter(engagement__offer=offer)
        
        # Calculate metrics
        total_clicks = engagements.count()
        total_conversions = conversions.count()
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        # Get average completion time
        completed_engagements = engagements.filter(status='completed')
        avg_completion_time = 0
        if completed_engagements.exists():
            completion_times = []
            for engagement in completed_engagements:
                if engagement.completed_at and engagement.started_at:
                    completion_time = (engagement.completed_at - engagement.started_at).total_seconds() / 60
                    completion_times.append(completion_time)
            
            if completion_times:
                avg_completion_time = sum(completion_times) / len(completion_times)
        
        # Calculate score (0-100)
        score = 0
        
        # Conversion rate weight: 40%
        if conversion_rate > 10:
            score += 40
        elif conversion_rate > 5:
            score += 30
        elif conversion_rate > 2:
            score += 20
        elif conversion_rate > 1:
            score += 10
        
        # Completion rate weight: 30%
        completion_rate = (completed_engagements.count() / total_clicks * 100) if total_clicks > 0 else 0
        if completion_rate > 80:
            score += 30
        elif completion_rate > 60:
            score += 25
        elif completion_rate > 40:
            score += 20
        elif completion_rate > 20:
            score += 15
        elif completion_rate > 10:
            score += 10
        
        # Average completion time weight: 20%
        if avg_completion_time > 0:
            if avg_completion_time < 5:
                score += 20
            elif avg_completion_time < 10:
                score += 15
            elif avg_completion_time < 15:
                score += 10
            elif avg_completion_time < 20:
                score += 5
        
        # User satisfaction weight: 10%
        # This could be based on user ratings or feedback
        score += 10  # Default value
        
        return min(score, 100.0)
        
    except Exception as e:
        logger.error(f"Error calculating offer performance score: {str(e)}")
        return 0.0


def get_user_personalized_offers(user, limit=10, tenant_id='default') -> List[Offer]:
    """
    Get personalized offers for a user based on their history and preferences
    """
    try:
        # Get user's offer history
        user_engagements = UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=tenant_id
        )
        
        # Get user's completed offers
        completed_offers = user_engagements.filter(status='completed').values_list('offer', flat=True)
        
        # Get user's preferred categories
        preferred_categories = Offer.objects.filter(
            id__in=completed_offers
        ).values_list('category', flat=True).distinct()
        
        # Get user's average reward preference
        avg_reward = UserOfferEngagement.objects.filter(
            user=user,
            offer__reward_amount__gt=0,
            tenant_id=tenant_id
        ).aggregate(avg_reward=models.Avg('offer__reward_amount'))['avg_reward'] or 0
        
        # Build personalized query
        offers_query = Offer.objects.filter(
            status='active',
            tenant_id=tenant_id
        ).exclude(
            id__in=completed_offers  # Exclude already completed
        )
        
        # Filter by preferred categories
        if preferred_categories:
            offers_query = offers_query.filter(category__in=preferred_categories)
        
        # Filter by reward range (±50% of user's average)
        if avg_reward > 0:
            min_reward = avg_reward * 0.5
            max_reward = avg_reward * 1.5
            offers_query = offers_query.filter(
                reward_amount__gte=min_reward,
                reward_amount__lte=max_reward
            )
        
        # Order by performance score and limit
        offers = offers_query.order_by('-performance_score', '-created_at')[:limit]
        
        return list(offers)
        
    except Exception as e:
        logger.error(f"Error getting personalized offers: {str(e)}")
        return []


def validate_offer_completion(user, offer, engagement_data=None) -> Dict[str, Any]:
    """
    Validate if an offer completion is legitimate
    """
    try:
        errors = []
        warnings = []
        
        # Check if user has already completed this offer
        existing_completion = UserOfferEngagement.objects.filter(
            user=user,
            offer=offer,
            status='completed',
            tenant_id=getattr(offer, 'tenant_id', 'default')
        ).first()
        
        if existing_completion:
            errors.append("Offer already completed by this user")
        
        # Check daily limit
        from .models import OfferDailyLimit
        daily_limit = OfferDailyLimit.objects.filter(
            user=user,
            offer=offer,
            tenant_id=getattr(offer, 'tenant_id', 'default')
        ).first()
        
        if daily_limit and daily_limit.is_limit_reached:
            errors.append("Daily limit reached for this offer")
        
        # Check user's offer limits
        total_completed = UserOfferEngagement.objects.filter(
            user=user,
            status='completed',
            tenant_id=getattr(offer, 'tenant_id', 'default')
        ).count()
        
        if offer.user_lifetime_limit and total_completed >= offer.user_lifetime_limit:
            errors.append("Lifetime limit reached for this offer")
        
        # Check if offer is still active
        if offer.status != 'active':
            errors.append("Offer is not currently active")
        
        # Check if offer has expired
        if offer.expires_at and offer.expires_at < timezone.now():
            errors.append("Offer has expired")
        
        # Check fraud indicators
        if engagement_data:
            # Check for suspicious patterns
            if engagement_data.get('completion_time', 0) < 30:  # Completed too quickly
                warnings.append("Completion time seems unusually fast")
            
            if engagement_data.get('ip_changes', 0) > 2:  # Multiple IP changes
                warnings.append("Multiple IP address changes detected")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'can_complete': len(errors) == 0
        }
        
    except Exception as e:
        logger.error(f"Error validating offer completion: {str(e)}")
        return {
            'is_valid': False,
            'errors': [f"Validation error: {str(e)}"],
            'warnings': [],
            'can_complete': False
        }


# ==================== NETWORK UTILITIES ====================

def test_network_connection(network) -> Dict[str, Any]:
    """
    Test connection to an ad network
    """
    try:
        from .services.AdNetworkFactory import AdNetworkFactory
        
        # Get network service
        service = AdNetworkFactory.get_service(network.network_type)
        if not service:
            return {
                'success': False,
                'error': 'Network service not found'
            }
        
        # Test connection
        start_time = timezone.now()
        
        try:
            # Make test API call
            result = service.test_connection()
            
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'response_time_ms': response_time,
                'result': result
            }
            
        except Exception as e:
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'error': str(e),
                'response_time_ms': response_time
            }
        
    except Exception as e:
        logger.error(f"Error testing network connection: {str(e)}")
        return {
            'success': False,
            'error': f"Test failed: {str(e)}"
        }


def get_network_statistics(network_id=None, tenant_id='default', days=30) -> Dict[str, Any]:
    """
    Get comprehensive statistics for networks
    """
    try:
        from datetime import timedelta
        from django.db.models import Count, Sum, Avg, Q
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Base query
        networks_query = AdNetwork.objects.filter(tenant_id=tenant_id)
        if network_id:
            networks_query = networks_query.filter(id=network_id)
        
        stats = {}
        
        for network in networks_query:
            # Offer statistics
            offers = Offer.objects.filter(
                ad_network=network,
                tenant_id=tenant_id
            )
            
            # Engagement statistics
            engagements = UserOfferEngagement.objects.filter(
                offer__ad_network=network,
                tenant_id=tenant_id,
                created_at__gte=start_date
            )
            
            # Conversion statistics
            conversions = OfferConversion.objects.filter(
                engagement__offer__ad_network=network,
                tenant_id=tenant_id,
                created_at__gte=start_date
            )
            
            # Calculate metrics
            total_offers = offers.count()
            active_offers = offers.filter(status='active').count()
            total_engagements = engagements.count()
            total_conversions = conversions.count()
            total_payout = conversions.aggregate(
                total=Sum('payout')
            )['total'] or 0
            
            conversion_rate = (total_conversions / total_engagements * 100) if total_engagements > 0 else 0
            
            stats[network.id] = {
                'network_name': network.name,
                'total_offers': total_offers,
                'active_offers': active_offers,
                'total_engagements': total_engagements,
                'total_conversions': total_conversions,
                'total_payout': total_payout,
                'conversion_rate': round(conversion_rate, 2),
                'avg_payout': round(total_payout / total_conversions, 2) if total_conversions > 0 else 0,
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting network statistics: {str(e)}")
        return {}


# ==================== ANALYTICS UTILITIES ====================

def generate_analytics_report(tenant_id='default', start_date=None, end_date=None) -> Dict[str, Any]:
    """
    Generate comprehensive analytics report
    """
    try:
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        report = {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {},
            'offers': {},
            'users': {},
            'networks': {},
            'revenue': {}
        }
        
        # Summary statistics
        total_offers = Offer.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).count()
        
        total_engagements = UserOfferEngagement.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).count()
        
        total_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).count()
        
        total_payout = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).aggregate(total=Sum('payout'))['total'] or 0
        
        report['summary'] = {
            'total_offers': total_offers,
            'total_engagements': total_engagements,
            'total_conversions': total_conversions,
            'total_payout': total_payout,
            'conversion_rate': round((total_conversions / total_engagements * 100) if total_engagements > 0 else 0, 2)
        }
        
        # Top performing offers
        top_offers = Offer.objects.filter(
            tenant_id=tenant_id
        ).annotate(
            conversion_count=Count('userofferengagement__offerconversion'),
            total_payout=Sum('userofferengagement__offerconversion__payout')
        ).order_by('-conversion_count')[:10]
        
        report['offers']['top_performing'] = [
            {
                'id': offer.id,
                'title': offer.title,
                'conversions': offer.conversion_count or 0,
                'payout': offer.total_payout or 0
            }
            for offer in top_offers
        ]
        
        # Active users
        active_users = UserOfferEngagement.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).values('user').distinct().count()
        
        report['users']['active_users'] = active_users
        
        # Network performance
        network_stats = get_network_statistics(tenant_id=tenant_id)
        report['networks'] = network_stats
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {str(e)}")
        return {}


# ==================== CURRENCY UTILITIES ====================

def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """
    Convert amount from one currency to another
    """
    try:
        # Exchange rates (in a real application, these would come from an API)
        exchange_rates = {
            'USD': 1.0,
            'BDT': 105.0,
            'EUR': 0.85,
            'GBP': 0.73,
            'INR': 83.0,
        }
        
        if from_currency not in exchange_rates or to_currency not in exchange_rates:
            raise ValidationError(f"Unsupported currency: {from_currency} or {to_currency}")
        
        # Convert to USD first, then to target currency
        usd_amount = amount / exchange_rates[from_currency]
        converted_amount = usd_amount * exchange_rates[to_currency]
        
        return converted_amount.quantize(Decimal('0.01'))
        
    except Exception as e:
        logger.error(f"Error converting currency: {str(e)}")
        return amount


def format_currency(amount: Decimal, currency: str = 'BDT') -> str:
    """
    Format currency amount with proper symbol and formatting
    """
    currency_symbols = {
        'USD': '$',
        'BDT': 'BDT',
        'EUR': 'EUR',
        'GBP': '£',
        'INR': 'INR',
    }
    
    symbol = currency_symbols.get(currency, currency)
    
    # Format with 2 decimal places
    formatted_amount = f"{amount:.2f}"
    
    return f"{symbol} {formatted_amount}"


# ==================== VALIDATION UTILITIES ====================

def validate_ip_address(ip_address: str) -> bool:
    """
    Validate IP address format
    """
    try:
        from ipaddress import ip_address
        ip_address(ip_address)
        return True
    except ValueError:
        return False


def validate_url(url: str) -> bool:
    """
    Validate URL format
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks
    """
    try:
        import bleach
        from bleach.css import sanitize_css
        
        # Allowed HTML tags
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'a', 'img', 'div', 'span'
        ]
        
        # Allowed attributes
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            '*': ['class']
        }
        
        # Sanitize HTML
        clean_html = bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return clean_html
        
    except ImportError:
        # If bleach is not available, remove all HTML tags
        import re
        clean_html = re.sub(r'<[^>]+>', '', html_content)
        return clean_html
    except Exception as e:
        logger.error(f"Error sanitizing HTML: {str(e)}")
        return html_content


# ==================== CACHE UTILITIES ====================

def cache_offer_data(offer_id: int, data: Dict, timeout: int = 300) -> bool:
    """
    Cache offer data with proper key structure
    """
    try:
        from django.core.cache import cache
        key = f"offer_data_{offer_id}"
        return cache.set(key, data, timeout)
    except Exception as e:
        logger.error(f"Error caching offer data: {str(e)}")
        return False


def get_cached_offer_data(offer_id: int) -> Optional[Dict]:
    """
    Get cached offer data
    """
    try:
        from django.core.cache import cache
        key = f"offer_data_{offer_id}"
        return cache.get(key)
    except Exception as e:
        logger.error(f"Error getting cached offer data: {str(e)}")
        return None


def invalidate_offer_cache(offer_id: int) -> bool:
    """
    Invalidate cached offer data
    """
    try:
        from django.core.cache import cache
        key = f"offer_data_{offer_id}"
        cache.delete(key)
        return True
    except Exception as e:
        logger.error(f"Error invalidating offer cache: {str(e)}")
        return False


# ==================== TENANT UTILITIES ====================

def get_tenant_from_request(request) -> Optional[str]:
    """
    Extract tenant ID from request
    """
    # Try subdomain
    host = request.get_host()
    if host:
        subdomain = host.split('.')[0]
        if subdomain and subdomain != 'www':
            return subdomain
    
    # Try header
    tenant_id = request.META.get('HTTP_X_TENANT_ID')
    if tenant_id:
        return tenant_id
    
    # Try query parameter
    tenant_id = request.GET.get('tenant_id')
    if tenant_id:
        return tenant_id
    
    # Try user's tenant
    if hasattr(request.user, 'tenant_id'):
        return request.user.tenant_id
    
    return None


def validate_tenant_access(request, tenant_id: str) -> bool:
    """
    Validate if user has access to tenant
    """
    try:
        # Superuser has access to all tenants
        if request.user.is_superuser:
            return True
        
        # Check if user belongs to tenant
        from api.tenants.models import TenantUser
        user_tenant = TenantUser.objects.filter(
            user=request.user,
            tenant__tenant_id=tenant_id,
            is_active=True
        ).first()
        
        return user_tenant is not None
        
    except Exception as e:
        logger.error(f"Error validating tenant access: {str(e)}")
        return False


# ==================== EXPORTS ====================

__all__ = [
    # File utilities
    'generate_secure_filename',
    'calculate_file_hash',
    'get_file_metadata',
    'create_thumbnail',
    'upload_file_securely',
    
    # Offer utilities
    'calculate_offer_performance_score',
    'get_user_personalized_offers',
    'validate_offer_completion',
    
    # Network utilities
    'test_network_connection',
    'get_network_statistics',
    
    # Analytics utilities
    'generate_analytics_report',
    
    # Currency utilities
    'convert_currency',
    'format_currency',
    
    # Validation utilities
    'validate_ip_address',
    'validate_url',
    'sanitize_html',
    
    # Cache utilities
    'cache_offer_data',
    'get_cached_offer_data',
    'invalidate_offer_cache',
    
    # Tenant utilities
    'get_tenant_from_request',
    'validate_tenant_access',
]
