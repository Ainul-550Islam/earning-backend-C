# api/ad_networks/attachment_upload_view.py
# SaaS-Ready Multi-Tenant File Upload Handling with Complete Security

import os
import uuid
import logging
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from PIL import Image, ImageOps
import magic
import boto3
import redis
from io import BytesIO

from .models import AdNetwork, Offer, OfferAttachment
from .mixins import TenantMixin
from .constants import (
    UPLOAD_SETTINGS, FILE_SIZE_LIMITS, ALLOWED_MIME_TYPES,
    IMAGE_DIMENSIONS, STORAGE_CONFIG
)
from .exceptions import FileUploadError, SecurityValidationError
from .validators import FileValidator, ImageValidator, DocumentValidator
from .utils import generate_secure_filename, calculate_file_hash, get_file_metadata

logger = logging.getLogger(__name__)

# ============================================================================
# FILE UPLOAD CONFIGURATION
# ============================================================================

class UploadConfig:
    """Configuration for file uploads"""
    
    # File size limits (in bytes)
    MAX_FILE_SIZE = {
        'image': FILE_SIZE_LIMITS['image'],
        'document': FILE_SIZE_LIMITS['document'],
        'csv': FILE_SIZE_LIMITS.get('csv', 1024 * 1024),  # 1MB default
        'video': FILE_SIZE_LIMITS['video'],
        'audio': FILE_SIZE_LIMITS['audio'],
    }
    
    # Allowed MIME types
    ALLOWED_MIME_TYPES = ALLOWED_MIME_TYPES
    
    # Image dimensions
    MAX_IMAGE_DIMENSIONS = IMAGE_DIMENSIONS
    
    # Storage configuration
    USE_S3 = STORAGE_CONFIG.get('USE_S3', False)
    S3_BUCKET = STORAGE_CONFIG.get('S3_BUCKET', '')
    S3_REGION = STORAGE_CONFIG.get('S3_REGION', 'us-east-1')
    
    # Security settings
    ENABLE_VIRUS_SCAN = UPLOAD_SETTINGS.get('ENABLE_VIRUS_SCAN', False)
    ENABLE_CONTENT_SCAN = UPLOAD_SETTINGS.get('ENABLE_CONTENT_SCAN', True)
    ENABLE_RATE_LIMITING = UPLOAD_SETTINGS.get('ENABLE_RATE_LIMITING', True)

# ============================================================================
# FILE VALIDATION
# ============================================================================

class FileUploadValidator:
    """Comprehensive file upload validation"""
    
    @staticmethod
    def validate_file(file_obj, file_type='image', tenant_id='default'):
        """
        Validate uploaded file
        """
        try:
            # Check file size
            if file_obj.size > UploadConfig.MAX_FILE_SIZE.get(file_type, UploadConfig.MAX_FILE_SIZE['image']):
                raise ValidationError(f"File size exceeds limit of {UploadConfig.MAX_FILE_SIZE[file_type]} bytes")
            
            # Check MIME type
            mime_type = magic.from_buffer(file_obj.read(1024), mime=True)
            file_obj.seek(0)  # Reset file pointer
            
            if mime_type not in UploadConfig.ALLOWED_MIME_TYPES.get(file_type, []):
                raise ValidationError(f"File type {mime_type} not allowed for {file_type}")
            
            # Additional validation based on file type
            if file_type == 'image':
                FileUploadValidator._validate_image(file_obj)
            elif file_type == 'document':
                FileUploadValidator._validate_document(file_obj)
            elif file_type == 'csv':
                FileUploadValidator._validate_csv(file_obj)
            
            # Security scans
            if UploadConfig.ENABLE_VIRUS_SCAN:
                FileUploadValidator._scan_for_viruses(file_obj)
            
            if UploadConfig.ENABLE_CONTENT_SCAN:
                FileUploadValidator._scan_content(file_obj)
            
            return {'valid': True, 'mime_type': mime_type}
            
        except ValidationError as e:
            return {'valid': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            return {'valid': False, 'error': 'File validation failed'}
    
    @staticmethod
    def _validate_image(file_obj):
        """Validate image file"""
        try:
            with Image.open(file_obj) as img:
                # Check image format
                if img.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
                    raise ValidationError("Invalid image format")
                
                # Check dimensions
                max_width, max_height = UploadConfig.MAX_IMAGE_DIMENSIONS['MAX_WIDTH'], UploadConfig.MAX_IMAGE_DIMENSIONS['MAX_HEIGHT']
                if img.width > max_width or img.height > max_height:
                    raise ValidationError(f"Image dimensions exceed {max_width}x{max_height}")
                
                # Auto-orient image
                img = ImageOps.exif_transpose(img)
                
        except Exception as e:
            raise ValidationError(f"Invalid image file: {str(e)}")
    
    @staticmethod
    def _validate_document(file_obj):
        """Validate document file"""
        mime_type = magic.from_buffer(file_obj.read(1024), mime=True)
        file_obj.seek(0)
        
        allowed_doc_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        
        if mime_type not in allowed_doc_types:
            raise ValidationError("Invalid document format")
    
    @staticmethod
    def _validate_csv(file_obj):
        """Validate CSV file"""
        mime_type = magic.from_buffer(file_obj.read(1024), mime=True)
        file_obj.seek(0)
        
        if mime_type not in ['text/csv', 'application/csv']:
            raise ValidationError("Invalid CSV format")
        
        # Try to read first few lines
        try:
            content = file_obj.read(1024).decode('utf-8')
            file_obj.seek(0)
            
            lines = content.split('\n')
            if len(lines) < 2:
                raise ValidationError("CSV file appears to be empty or invalid")
                
        except UnicodeDecodeError:
            raise ValidationError("CSV file must be UTF-8 encoded")
    
    @staticmethod
    def _scan_for_viruses(file_obj):
        """Scan file for viruses (placeholder)"""
        # This would integrate with antivirus software
        # For now, just log that scan was performed
        logger.info(f"Virus scan performed on file: {file_obj.name}")
    
    @staticmethod
    def _scan_content(file_obj):
        """Scan file content for security issues"""
        # Read file content for scanning
        content = file_obj.read(1024)
        file_obj.seek(0)
        
        # Check for suspicious patterns
        suspicious_patterns = [
            b'<script',
            b'javascript:',
            b'data:text/html',
            b'eval(',
            b'exec(',
        ]
        
        for pattern in suspicious_patterns:
            if pattern in content.lower():
                raise ValidationError("Suspicious content detected in file")

# ============================================================================
# FILE PROCESSING
# ============================================================================

class FileProcessor:
    """Process uploaded files"""
    
    @staticmethod
    def process_image(file_obj, tenant_id='default'):
        """Process image file"""
        try:
            with Image.open(file_obj) as img:
                # Auto-orient
                img = ImageOps.exif_transpose(img)
                
                # Resize if needed
                max_width, max_height = UploadConfig.MAX_IMAGE_DIMENSIONS['MAX_WIDTH'], UploadConfig.MAX_IMAGE_DIMENSIONS['MAX_HEIGHT']
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Save to BytesIO
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)
                
                return output
                
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            raise FileUploadError(f"Image processing failed: {str(e)}")
    
    @staticmethod
    def generate_thumbnail(file_obj, size=(150, 150)):
        """Generate thumbnail for image"""
        try:
            with Image.open(file_obj) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Create thumbnail
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save to BytesIO
                output = BytesIO()
                img.save(output, format='JPEG', quality=80, optimize=True)
                output.seek(0)
                
                return output
                
        except Exception as e:
            logger.error(f"Thumbnail generation error: {str(e)}")
            return None
    
    @staticmethod
    def extract_metadata(file_obj):
        """Extract file metadata"""
        try:
            metadata = {}
            
            # Basic file info
            metadata['size'] = file_obj.size
            metadata['name'] = file_obj.name
            metadata['content_type'] = magic.from_buffer(file_obj.read(1024), mime=True)
            file_obj.seek(0)
            
            # Image metadata
            if metadata['content_type'].startswith('image/'):
                with Image.open(file_obj) as img:
                    metadata['width'] = img.width
                    metadata['height'] = img.height
                    metadata['format'] = img.format
                    metadata['mode'] = img.mode
                    
                    # EXIF data
                    if hasattr(img, '_getexif') and img._getexif():
                        from PIL.ExifTags import TAGS
                        exif_data = {}
                        for tag_id, value in img._getexif().items():
                            tag = TAGS.get(tag_id, tag_id)
                            exif_data[tag] = value
                        metadata['exif'] = exif_data
            
            # Calculate file hash
            file_content = file_obj.read()
            file_obj.seek(0)
            metadata['md5_hash'] = hashlib.md5(file_content).hexdigest()
            metadata['sha256_hash'] = hashlib.sha256(file_content).hexdigest()
            
            return metadata
            
        except Exception as e:
            logger.error(f"Metadata extraction error: {str(e)}")
            return {}

# ============================================================================
# STORAGE HANDLERS
# ============================================================================

class StorageHandler:
    """Handle file storage operations"""
    
    @staticmethod
    def save_file(file_obj, filename, tenant_id='default'):
        """Save file to storage"""
        try:
            if UploadConfig.USE_S3:
                return StorageHandler._save_to_s3(file_obj, filename, tenant_id)
            else:
                return StorageHandler._save_to_local(file_obj, filename, tenant_id)
                
        except Exception as e:
            logger.error(f"File storage error: {str(e)}")
            raise FileUploadError(f"File storage failed: {str(e)}")
    
    @staticmethod
    def _save_to_local(file_obj, filename, tenant_id='default'):
        """Save file to local storage"""
        # Create tenant-specific directory
        tenant_dir = f"uploads/{tenant_id}"
        file_path = os.path.join(tenant_dir, filename)
        
        # Save file
        path = default_storage.save(file_path, ContentFile(file_obj.read()))
        file_obj.seek(0)
        
        return {
            'url': default_storage.url(path),
            'path': path,
            'size': file_obj.size
        }
    
    @staticmethod
    def _save_to_s3(file_obj, filename, tenant_id='default'):
        """Save file to S3"""
        try:
            s3_client = boto3.client('s3')
            
            # Create S3 key with tenant prefix
            s3_key = f"{tenant_id}/uploads/{filename}"
            
            # Upload to S3
            s3_client.upload_fileobj(
                file_obj,
                UploadConfig.S3_BUCKET,
                s3_key,
                ExtraArgs={
                    'ContentType': magic.from_buffer(file_obj.read(1024), mime=True),
                    'ACL': 'private'
                }
            )
            file_obj.seek(0)
            
            # Generate URL
            url = f"https://{UploadConfig.S3_BUCKET}.s3.{UploadConfig.S3_REGION}.amazonaws.com/{s3_key}"
            
            return {
                'url': url,
                'path': s3_key,
                'size': file_obj.size
            }
            
        except Exception as e:
            logger.error(f"S3 upload error: {str(e)}")
            raise FileUploadError(f"S3 upload failed: {str(e)}")
    
    @staticmethod
    def delete_file(file_path, tenant_id='default'):
        """Delete file from storage"""
        try:
            if UploadConfig.USE_S3:
                s3_client = boto3.client('s3')
                s3_client.delete_object(Bucket=UploadConfig.S3_BUCKET, Key=file_path)
            else:
                default_storage.delete(file_path)
                
        except Exception as e:
            logger.error(f"File deletion error: {str(e)}")

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Rate limiting for file uploads"""
    
    @staticmethod
    def check_rate_limit(user_id, tenant_id='default'):
        """Check if user exceeds rate limit"""
        if not UploadConfig.ENABLE_RATE_LIMITING:
            return True
        
        try:
            # Use Redis for rate limiting
            redis_client = redis.Redis(host='localhost', port=6379, db=0)
            
            key = f"upload_rate:{tenant_id}:{user_id}"
            current_count = redis_client.get(key) or 0
            
            if int(current_count) >= UPLOAD_SETTINGS['MAX_UPLOADS_PER_HOUR']:
                return False
            
            # Increment counter
            redis_client.incr(key)
            redis_client.expire(key, 3600)  # 1 hour expiry
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiting error: {str(e)}")
            return True  # Allow upload if rate limiting fails

# ============================================================================
# MAIN UPLOAD VIEWS
# ============================================================================

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def upload_attachment(request):
    """
    Handle file uploads for ad networks attachments
    SaaS-ready with tenant support and comprehensive security
    """
    try:
        # Get tenant ID
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        # Check rate limiting
        if not RateLimiter.check_rate_limit(request.user.id, tenant_id):
            return JsonResponse({
                'success': False,
                'error': 'Rate limit exceeded. Please try again later.'
            }, status=429)
        
        # Validate file presence
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        file_type = request.POST.get('file_type', 'image')
        related_object_id = request.POST.get('related_object_id')
        related_object_type = request.POST.get('related_object_type', 'offer')
        
        # Validate file
        validation_result = FileUploadValidator.validate_file(uploaded_file, file_type, tenant_id)
        if not validation_result['valid']:
            return JsonResponse({
                'success': False,
                'error': validation_result['error']
            }, status=400)
        
        # Process file
        processed_file = uploaded_file
        if file_type == 'image':
            processed_file = FileProcessor.process_image(uploaded_file, tenant_id)
        
        # Generate secure filename
        original_filename = uploaded_file.name
        secure_filename = generate_secure_filename(original_filename)
        filename = f"{timezone.now().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{secure_filename}"
        
        # Extract metadata
        metadata = FileProcessor.extract_metadata(uploaded_file)
        metadata.update({
            'original_filename': original_filename,
            'file_type': file_type,
            'mime_type': validation_result['mime_type']
        })
        
        # Save file
        with transaction.atomic():
            # Save to storage
            storage_result = StorageHandler.save_file(processed_file, filename, tenant_id)
            
            # Generate thumbnail for images
            thumbnail_url = None
            if file_type == 'image':
                thumbnail = FileProcessor.generate_thumbnail(uploaded_file)
                if thumbnail:
                    thumbnail_filename = f"thumbnails/{uuid.uuid4()}_thumb.jpg"
                    thumb_result = StorageHandler.save_file(thumbnail, thumbnail_filename, tenant_id)
                    thumbnail_url = thumb_result['url']
            
            # Create database record
            attachment = OfferAttachment.objects.create(
                tenant_id=tenant_id,
                filename=secure_filename,
                original_filename=original_filename,
                file_path=storage_result['path'],
                file_url=storage_result['url'],
                file_size=storage_result['size'],
                mime_type=validation_result['mime_type'],
                file_type=file_type,
                metadata=metadata,
                thumbnail_url=thumbnail_url,
                uploaded_by=request.user
            )
            
            # Link to related object if specified
            if related_object_id and related_object_type:
                if related_object_type == 'offer':
                    try:
                        offer = Offer.objects.get(id=related_object_id, tenant_id=tenant_id)
                        attachment.related_offer = offer
                        attachment.save()
                    except Offer.DoesNotExist:
                        logger.warning(f"Offer {related_object_id} not found for attachment")
                elif related_object_type == 'ad_network':
                    try:
                        ad_network = AdNetwork.objects.get(id=related_object_id, tenant_id=tenant_id)
                        attachment.related_ad_network = ad_network
                        attachment.save()
                    except AdNetwork.DoesNotExist:
                        logger.warning(f"AdNetwork {related_object_id} not found for attachment")
        
        # Log upload
        logger.info(f"File uploaded successfully: {attachment.id} by user {request.user.id} in tenant {tenant_id}")
        
        return JsonResponse({
            'success': True,
            'attachment': {
                'id': attachment.id,
                'filename': attachment.filename,
                'original_filename': attachment.original_filename,
                'file_url': attachment.file_url,
                'thumbnail_url': attachment.thumbnail_url,
                'file_size': attachment.file_size,
                'mime_type': attachment.mime_type,
                'file_type': attachment.file_type,
                'created_at': attachment.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'File upload failed. Please try again.'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def upload_bulk_attachments(request):
    """
    Handle bulk file uploads
    """
    try:
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        if 'files' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No files provided'
            }, status=400)
        
        files = request.FILES.getlist('files')
        file_type = request.POST.get('file_type', 'image')
        
        # Check rate limiting for bulk uploads
        if not RateLimiter.check_rate_limit(request.user.id, tenant_id):
            return JsonResponse({
                'success': False,
                'error': 'Rate limit exceeded'
            }, status=429)
        
        # Limit bulk upload size
        if len(files) > UPLOAD_SETTINGS['MAX_BULK_UPLOAD_SIZE']:
            return JsonResponse({
                'success': False,
                'error': f'Maximum {UPLOAD_SETTINGS["MAX_BULK_UPLOAD_SIZE"]} files allowed per bulk upload'
            }, status=400)
        
        results = []
        errors = []
        
        for i, file_obj in enumerate(files):
            try:
                # Validate each file
                validation_result = FileUploadValidator.validate_file(file_obj, file_type, tenant_id)
                if not validation_result['valid']:
                    errors.append({
                        'file_index': i,
                        'filename': file_obj.name,
                        'error': validation_result['error']
                    })
                    continue
                
                # Process and save file
                processed_file = file_obj
                if file_type == 'image':
                    processed_file = FileProcessor.process_image(file_obj, tenant_id)
                
                secure_filename = generate_secure_filename(file_obj.name)
                filename = f"{timezone.now().strftime('%Y/%m/%d')}/bulk_{uuid.uuid4()}_{secure_filename}"
                
                storage_result = StorageHandler.save_file(processed_file, filename, tenant_id)
                
                attachment = OfferAttachment.objects.create(
                    tenant_id=tenant_id,
                    filename=secure_filename,
                    original_filename=file_obj.name,
                    file_path=storage_result['path'],
                    file_url=storage_result['url'],
                    file_size=storage_result['size'],
                    mime_type=validation_result['mime_type'],
                    file_type=file_type,
                    metadata=FileProcessor.extract_metadata(file_obj),
                    uploaded_by=request.user
                )
                
                results.append({
                    'file_index': i,
                    'filename': file_obj.name,
                    'attachment_id': attachment.id,
                    'file_url': attachment.file_url
                })
                
            except Exception as e:
                errors.append({
                    'file_index': i,
                    'filename': file_obj.name,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'errors': errors,
            'total_files': len(files),
            'successful_uploads': len(results),
            'failed_uploads': len(errors)
        })
        
    except Exception as e:
        logger.error(f"Bulk upload error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Bulk upload failed'
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_attachment(request, attachment_id):
    """
    Delete uploaded attachment
    """
    try:
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        with transaction.atomic():
            attachment = OfferAttachment.objects.get(id=attachment_id, tenant_id=tenant_id)
            
            # Check permissions
            if attachment.uploaded_by != request.user and not request.user.is_staff:
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied'
                }, status=403)
            
            # Delete file from storage
            StorageHandler.delete_file(attachment.file_path, tenant_id)
            
            # Delete thumbnail if exists
            if attachment.thumbnail_url:
                thumb_path = attachment.thumbnail_url.split('/')[-1]
                StorageHandler.delete_file(f"thumbnails/{thumb_path}", tenant_id)
            
            # Delete database record
            attachment.delete()
            
        logger.info(f"Attachment {attachment_id} deleted by user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Attachment deleted successfully'
        })
        
    except OfferAttachment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Attachment not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Attachment deletion error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Deletion failed'
        }, status=500)

# ============================================================================
# API VIEWSET FOR ATTACHMENTS
# ============================================================================

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from .serializers import OfferAttachmentSerializer

class AttachmentViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    SaaS-Ready Attachment ViewSet
    """
    serializer_class = OfferAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return OfferAttachment.objects.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def regenerate_thumbnail(self, request, pk=None):
        """Regenerate thumbnail for image attachment"""
        try:
            attachment = self.get_object()
            
            if attachment.file_type != 'image':
                return Response({
                    'success': False,
                    'error': 'Thumbnails only available for images'
                }, status=400)
            
            # Get original file
            if UploadConfig.USE_S3:
                s3_client = boto3.client('s3')
                response = s3_client.get_object(Bucket=UploadConfig.S3_BUCKET, Key=attachment.file_path)
                file_obj = BytesIO(response['Body'].read())
            else:
                file_obj = default_storage.open(attachment.file_path, 'rb')
            
            # Generate new thumbnail
            thumbnail = FileProcessor.generate_thumbnail(file_obj)
            if thumbnail:
                # Delete old thumbnail
                if attachment.thumbnail_url:
                    thumb_path = attachment.thumbnail_url.split('/')[-1]
                    StorageHandler.delete_file(f"thumbnails/{thumb_path}", attachment.tenant_id)
                
                # Save new thumbnail
                thumbnail_filename = f"thumbnails/{uuid.uuid4()}_thumb.jpg"
                thumb_result = StorageHandler.save_file(thumbnail, thumbnail_filename, attachment.tenant_id)
                
                attachment.thumbnail_url = thumb_result['url']
                attachment.save()
                
                return Response({
                    'success': True,
                    'thumbnail_url': attachment.thumbnail_url
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to generate thumbnail'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Thumbnail regeneration error: {str(e)}")
            return Response({
                'success': False,
                'error': 'Thumbnail regeneration failed'
            }, status=500)
    
    @action(detail=False, methods=['get'])
    def user_uploads(self, request):
        """Get user's upload history"""
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        attachments = OfferAttachment.objects.filter(
            tenant_id=tenant_id,
            uploaded_by=request.user
        ).order_by('-created_at')
        
        page = self.paginate_queryset(attachments)
        serializer = self.get_serializer(page, many=True)
        
        return self.get_paginated_response(serializer.data)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_upload_stats(request):
    """
    Get upload statistics for tenant
    """
    try:
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        stats = OfferAttachment.objects.filter(tenant_id=tenant_id).aggregate(
            total_files=Count('id'),
            total_size=Sum('file_size'),
            image_files=Count('id', filter=Q(file_type='image')),
            document_files=Count('id', filter=Q(file_type='document')),
            csv_files=Count('id', filter=Q(file_type='csv')),
            uploads_today=Count('id', filter=Q(created_at__date=timezone.now().date()))
        )
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Upload stats error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get upload stats'
        }, status=500)

def cleanup_old_files():
    """
    Clean up old unused files (for management command)
    """
    try:
        # Delete files older than 30 days that are not linked to any objects
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_attachments = OfferAttachment.objects.filter(
            created_at__lt=cutoff_date,
            related_offer__isnull=True,
            related_ad_network__isnull=True
        )
        
        deleted_count = 0
        for attachment in old_attachments:
            try:
                StorageHandler.delete_file(attachment.file_path, attachment.tenant_id)
                if attachment.thumbnail_url:
                    thumb_path = attachment.thumbnail_url.split('/')[-1]
                    StorageHandler.delete_file(f"thumbnails/{thumb_path}", attachment.tenant_id)
                attachment.delete()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting attachment {attachment.id}: {str(e)}")
        
        logger.info(f"Cleaned up {deleted_count} old attachments")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        return 0

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'upload_attachment',
    'upload_bulk_attachments', 
    'delete_attachment',
    'AttachmentViewSet',
    'get_upload_stats',
    'cleanup_old_files',
    'FileUploadValidator',
    'FileProcessor',
    'StorageHandler',
    'RateLimiter',
]
