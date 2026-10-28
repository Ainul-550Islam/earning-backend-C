"""
api/adapters/cms.py
CMS (Content Management System) adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_content_list(request):
    """Get content list from CMS."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        content_type = request.GET.get('type')  # 'all', 'page', 'post', 'banner', 'announcement'
        status = request.GET.get('status')  # 'all', 'published', 'draft', 'archived'
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get content
        from api.cms.models import Content
        queryset = Content.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if content_type and content_type != 'all':
            queryset = queryset.filter(content_type=content_type)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)
        
        # Paginate
        content_items = queryset[offset:offset+limit]
        
        # Serialize content
        content_data = []
        for item in content_items:
            content_data.append({
                'id': item.id,
                'title': item.title,
                'slug': item.slug,
                'content_type': item.content_type,
                'status': item.status,
                'category': item.category,
                'author': {
                    'id': item.author.id,
                    'username': item.author.username,
                    'first_name': item.author.first_name,
                    'last_name': item.author.last_name,
                },
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'published_at': item.published_at.isoformat() if item.published_at else None,
                'excerpt': item.excerpt,
                'featured_image': item.featured_image,
                'view_count': item.view_count,
                'like_count': item.like_count,
                'comment_count': item.comment_count,
                'is_featured': item.is_featured,
                'seo_title': item.seo_title,
                'seo_description': item.seo_description,
                'tags': item.tags,
                'metadata': item.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'content': content_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(content_data) == limit
                },
                'filters': {
                    'type': content_type,
                    'status': status,
                    'category': category
                }
            },
            'message': 'Content list retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error getting content list: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve content list',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_content_details(request, content_id):
    """Get detailed content information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get content
        from api.cms.models import Content
        try:
            content = Content.objects.get(
                id=content_id,
                tenant_id=tenant_id
            )
        except Content.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Content not found',
                'details': f'Content with ID {content_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get content sections
        from api.cms.models import ContentSection
        sections = ContentSection.objects.filter(
            content=content
        ).order_by('order')
        
        # Build detailed content data
        content_data = {
            'id': content.id,
            'title': content.title,
            'slug': content.slug,
            'content_type': content.content_type,
            'status': content.status,
            'category': content.category,
            'author': {
                'id': content.author.id,
                'username': content.author.username,
                'first_name': content.author.first_name,
                'last_name': content.author.last_name,
                'avatar': getattr(content.author, 'avatar', None),
            },
            'content_body': content.content_body,
            'excerpt': content.excerpt,
            'featured_image': content.featured_image,
            'gallery_images': content.gallery_images,
            'created_at': content.created_at.isoformat(),
            'updated_at': content.updated_at.isoformat(),
            'published_at': content.published_at.isoformat() if content.published_at else None,
            'view_count': content.view_count,
            'like_count': content.like_count,
            'comment_count': content.comment_count,
            'is_featured': content.is_featured,
            'seo': {
                'title': content.seo_title,
                'description': content.seo_description,
                'keywords': content.seo_keywords,
                'canonical_url': content.canonical_url,
            },
            'tags': content.tags,
            'categories': content.categories,
            'metadata': content.metadata,
            'sections': [
                {
                    'id': section.id,
                    'type': section.section_type,
                    'title': section.title,
                    'content': section.content,
                    'order': section.order,
                    'is_visible': section.is_visible
                }
                for section in sections
            ],
            'user_permissions': _get_user_content_permissions(user, content),
            'related_content': _get_related_content(content, tenant_id)
        }
        
        return Response({
            'success': True,
            'data': content_data,
            'message': 'Content details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error getting content details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve content details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_content(request):
    """Create new content."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'content_type', 'content_body']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user permissions
        if not _can_create_content(user, tenant_id):
            return Response({
                'success': False,
                'error': 'Permission denied',
                'details': 'You do not have permission to create content'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create content
        from api.cms.models import Content
        content = Content.objects.create(
            title=data['title'],
            slug=_generate_slug(data['title']),
            content_type=data['content_type'],
            content_body=data['content_body'],
            excerpt=data.get('excerpt', ''),
            category=data.get('category', 'general'),
            featured_image=data.get('featured_image', ''),
            gallery_images=data.get('gallery_images', []),
            status='draft',
            author=user,
            is_featured=data.get('is_featured', False),
            seo_title=data.get('seo_title', ''),
            seo_description=data.get('seo_description', ''),
            seo_keywords=data.get('seo_keywords', ''),
            canonical_url=data.get('canonical_url', ''),
            tags=data.get('tags', []),
            categories=data.get('categories', []),
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Create content sections if provided
        sections_data = data.get('sections', [])
        for i, section_data in enumerate(sections_data):
            from api.cms.models import ContentSection
            ContentSection.objects.create(
                content=content,
                section_type=section_data.get('type', 'text'),
                title=section_data.get('title', f'Section {i+1}'),
                body=section_data.get('content', ''),
                order=i,
                is_visible=section_data.get('is_visible', True)
            )
        
        # Emit content created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('cms.content_created', {
            'user_id': user.id,
            'content_id': content.id,
            'content_type': content.content_type,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'content_id': content.id,
                'title': content.title,
                'slug': content.slug,
                'status': content.status,
                'created_at': content.created_at.isoformat(),
                'sections_count': len(sections_data)
            },
            'message': 'Content created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error creating content: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create content',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_content(request, content_id):
    """Update existing content."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get content
        from api.cms.models import Content
        try:
            content = Content.objects.get(
                id=content_id,
                tenant_id=tenant_id
            )
        except Content.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Content not found',
                'details': f'Content with ID {content_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check user permissions
        if not _can_edit_content(user, content):
            return Response({
                'success': False,
                'error': 'Permission denied',
                'details': 'You do not have permission to edit this content'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update content
        if 'title' in data:
            content.title = data['title']
        if 'content_body' in data:
            content.content_body = data['content_body']
        if 'excerpt' in data:
            content.excerpt = data['excerpt']
        if 'category' in data:
            content.category = data['category']
        if 'featured_image' in data:
            content.featured_image = data['featured_image']
        if 'gallery_images' in data:
            content.gallery_images = data['gallery_images']
        if 'status' in data:
            content.status = data['status']
            if data['status'] == 'published' and not content.published_at:
                content.published_at = timezone.now()
        if 'is_featured' in data:
            content.is_featured = data['is_featured']
        if 'seo_title' in data:
            content.seo_title = data['seo_title']
        if 'seo_description' in data:
            content.seo_description = data['seo_description']
        if 'seo_keywords' in data:
            content.seo_keywords = data['seo_keywords']
        if 'canonical_url' in data:
            content.canonical_url = data['canonical_url']
        if 'tags' in data:
            content.tags = data['tags']
        if 'categories' in data:
            content.categories = data['categories']
        if 'metadata' in data:
            content.metadata = data['metadata']
        
        content.updated_at = timezone.now()
        content.save()
        
        # Emit content updated event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('cms.content_updated', {
            'user_id': user.id,
            'content_id': content.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'content_id': content.id,
                'title': content.title,
                'status': content.status,
                'updated_at': content.updated_at.isoformat()
            },
            'message': 'Content updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error updating content: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update content',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_content(request, content_id):
    """Delete content."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get content
        from api.cms.models import Content
        try:
            content = Content.objects.get(
                id=content_id,
                tenant_id=tenant_id
            )
        except Content.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Content not found',
                'details': f'Content with ID {content_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check user permissions
        if not _can_delete_content(user, content):
            return Response({
                'success': False,
                'error': 'Permission denied',
                'details': 'You do not have permission to delete this content'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Store content info for event
        content_info = {
            'id': content.id,
            'title': content.title,
            'content_type': content.content_type
        }
        
        # Delete content
        content.delete()
        
        # Emit content deleted event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('cms.content_deleted', {
            'user_id': user.id,
            'content_info': content_info,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'content_id': content_id,
                'deleted_at': timezone.now().isoformat()
            },
            'message': 'Content deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error deleting content: {e}")
        return Response({
            'success': False,
            'error': 'Failed to delete content',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_media_library(request):
    """Get media library for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        media_type = request.GET.get('type')  # 'all', 'image', 'video', 'document'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get media files
        from api.cms.models import MediaFile
        queryset = MediaFile.objects.filter(
            uploaded_by=user,
            tenant_id=tenant_id
        ).order_by('-uploaded_at')
        
        # Apply type filter
        if media_type and media_type != 'all':
            queryset = queryset.filter(file_type=media_type)
        
        # Paginate
        media_files = queryset[offset:offset+limit]
        
        # Serialize media files
        media_data = []
        for file in media_files:
            media_data.append({
                'id': file.id,
                'filename': file.filename,
                'original_filename': file.original_filename,
                'file_type': file.file_type,
                'mime_type': file.mime_type,
                'file_size': file.file_size,
                'file_url': file.file_url,
                'thumbnail_url': file.thumbnail_url,
                'duration': file.duration,
                'width': file.width,
                'height': file.height,
                'alt_text': file.alt_text,
                'caption': file.caption,
                'uploaded_at': file.uploaded_at.isoformat(),
                'is_public': file.is_public,
                'download_count': file.download_count,
                'tags': file.tags,
                'metadata': file.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'media': media_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(media_data) == limit
                },
                'filters': {
                    'type': media_type
                },
                'summary': {
                    'total_files': queryset.count(),
                    'total_size': queryset.aggregate(
                        total=Sum(F('file_size'))
                    )['total'] or 0,
                    'storage_used_percentage': _calculate_storage_usage(user, tenant_id)
                }
            },
            'message': 'Media library retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error getting media library: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve media library',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_cms_analytics(request):
    """Get CMS analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get CMS analytics
        from api.cms.models import Content, MediaFile
        content_stats = Content.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        media_stats = MediaFile.objects.filter(
            tenant_id=tenant_id,
            uploaded_at__gte=start_date
        )
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'content_metrics': {
                'total_content': content_stats.count(),
                'published_content': content_stats.filter(status='published').count(),
                'draft_content': content_stats.filter(status='draft').count(),
                'archived_content': content_stats.filter(status='archived').count(),
                'content_by_type': list(content_stats.values('content_type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'content_by_category': list(content_stats.values('category').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'total_views': content_stats.aggregate(
                    total=Sum(F('view_count'))
                )['total'] or 0,
                'total_likes': content_stats.aggregate(
                    total=Sum(F('like_count'))
                )['total'] or 0,
                'total_comments': content_stats.aggregate(
                    total=Sum(F('comment_count'))
                )['total'] or 0,
                'most_viewed': content_stats.order_by('-view_count')[:5],
                'most_liked': content_stats.order_by('-like_count')[:5],
                'most_commented': content_stats.order_by('-comment_count')[:5]
            },
            'media_metrics': {
                'total_files': media_stats.count(),
                'total_size': media_stats.aggregate(
                    total=Sum(F('file_size'))
                )['total'] or 0,
                'files_by_type': list(media_stats.values('file_type').annotate(
                    count=Count('id'),
                    total_size=Sum(F('file_size'))
                ).order_by('-total_size')),
                'total_downloads': media_stats.aggregate(
                    total=Sum(F('download_count'))
                )['total'] or 0,
                'storage_usage': _calculate_storage_usage(None, tenant_id),
                'upload_trends': _get_upload_trends(media_stats, days)
            },
            'user_metrics': {
                'total_authors': content_stats.values('author').distinct().count(),
                'active_authors': content_stats.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).values('author').distinct().count(),
                'top_contributors': list(content_stats.values('author').annotate(
                    content_count=Count('id')
                ).order_by('-content_count')[:10])
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'CMS analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CMSAdapter] Error getting CMS analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve CMS analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _can_create_content(user, tenant_id) -> bool:
    """Check if user can create content."""
    try:
        # Check if user has content creation permissions
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Admin users can always create content
        if user.is_staff:
            return True
        
        # Check user level and KYC
        if ctx.user_level >= 2 and ctx.kyc_tier in ['standard', 'full']:
            return True
        
        return False
    except Exception:
        return False


def _can_edit_content(user, content) -> bool:
    """Check if user can edit content."""
    try:
        # Admin users can always edit content
        if user.is_staff:
            return True
        
        # Users can edit their own content
        if content.author.id == user.id:
            return True
        
        # Check if user has edit permissions
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if ctx.user_level >= 3 and ctx.kyc_tier in ['standard', 'full']:
            return True
        
        return False
    except Exception:
        return False


def _can_delete_content(user, content) -> bool:
    """Check if user can delete content."""
    try:
        # Admin users can always delete content
        if user.is_staff:
            return True
        
        # Users can delete their own content
        if content.author.id == user.id:
            return True
        
        # Check if user has delete permissions
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if ctx.user_level >= 4 and ctx.kyc_tier == 'full':
            return True
        
        return False
    except Exception:
        return False


def _get_user_content_permissions(user, content) -> Dict:
    """Get user's permissions for content."""
    try:
        permissions = {
            'can_view': True,
            'can_edit': _can_edit_content(user, content),
            'can_delete': _can_delete_content(user, content),
            'can_comment': True,  # Basic users can comment
            'can_like': True,  # Basic users can like
            'can_share': True   # Basic users can share
        }
        
        # Add admin permissions
        if user.is_staff:
            permissions.update({
                'can_publish': True,
                'can_feature': True,
                'can_archive': True,
                'can_manage_seo': True
            })
        
        return permissions
    except Exception:
        return {}


def _get_related_content(content, tenant_id) -> List[Dict]:
    """Get related content."""
    try:
        from api.cms.models import Content
        # Get content with same category or tags
        related = Content.objects.filter(
            tenant_id=tenant_id,
            category=content.category,
            status='published',
            id__neq=content.id
        ).order_by('-view_count')[:5]
        
        return [
            {
                'id': item.id,
                'title': item.title,
                'slug': item.slug,
                'excerpt': item.excerpt,
                'featured_image': item.featured_image,
                'view_count': item.view_count
            }
            for item in related
        ]
    except Exception:
        return []


def _generate_slug(title) -> str:
    """Generate URL-friendly slug from title."""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    return slug


def _calculate_storage_usage(user, tenant_id) -> float:
    """Calculate storage usage percentage."""
    try:
        # Get storage quota from tenant settings
        storage_quota = cache.get(f'storage_quota_{tenant_id}', 1024 * 1024 * 1024)  # 1GB default
        
        # Get current usage
        from api.cms.models import MediaFile
        if user:
            used = MediaFile.objects.filter(
                uploaded_by=user,
                tenant_id=tenant_id
            ).aggregate(total=Sum(F('file_size')))['total'] or 0
        else:
            used = MediaFile.objects.filter(
                tenant_id=tenant_id
            ).aggregate(total=Sum(F('file_size')))['total'] or 0
        
        return round((used / max(storage_quota, 1)) * 100, 2)
    except Exception:
        return 0.0


def _get_upload_trends(media_stats, days) -> List[Dict]:
    """Get upload trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_uploads = media_stats.filter(
            uploaded_at__gte=start_date
        ).extra({
            'day': 'date(uploaded_at)'
        }).values('day').annotate(
            count=Count('id'),
            total_size=Sum(F('file_size'))
        ).order_by('day')
        
        return [
            {
                'date': upload['day'].isoformat(),
                'files_uploaded': upload['count'],
                'total_size': upload['total_size'] or 0
            }
            for upload in daily_uploads
        ]
    except Exception:
        return []
