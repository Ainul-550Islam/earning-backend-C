"""
api/ad_networks/services/OfferAttachmentService.py
Service for managing offer attachments
SaaS-ready with tenant support
"""

import os
import hashlib
import mimetypes
from datetime import datetime
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from PIL import Image
from io import BytesIO

from ..models import OfferAttachment, Offer
from .base import BaseService


class OfferAttachmentService(BaseService):
    """Service for managing offer attachments"""
    
    def __init__(self, tenant_id=None):
        super().__init__(tenant_id)
    
    def upload_attachment(self, offer_id, file_obj, filename=None, description=None, is_primary=False):
        """Upload and process an attachment for an offer"""
        try:
            # Get offer
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            # Generate file hash
            file_hash = self._generate_file_hash(file_obj)
            
            # Check for duplicate
            if OfferAttachment.objects.filter(
                file_hash=file_hash, 
                tenant_id=self.tenant_id
            ).exists():
                raise ValueError("Duplicate file detected")
            
            # Determine file type and mime type
            file_type = self._determine_file_type(filename or file_obj.name)
            mime_type = mimetypes.guess_type(filename or file_obj.name)[0] or 'application/octet-stream'
            
            # Process image if applicable
            width, height, thumbnail = None, None, None
            if file_type == 'image':
                width, height, thumbnail = self._process_image(file_obj)
            
            # Generate filename
            if not filename:
                filename = f"attachment_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
            
            # Create attachment
            attachment = OfferAttachment.objects.create(
                tenant_id=self.tenant_id,
                offer=offer,
                file=file_obj,
                filename=filename,
                original_filename=file_obj.name,
                file_type=file_type,
                mime_type=mime_type,
                file_size=file_obj.size,
                file_hash=file_hash,
                width=width,
                height=height,
                thumbnail=thumbnail,
                description=description,
                is_primary=is_primary,
                display_order=self._get_next_display_order(offer)
            )
            
            return attachment
            
        except Offer.DoesNotExist:
            raise ValueError("Offer not found")
        except Exception as e:
            self.logger.error(f"Error uploading attachment: {str(e)}")
            raise
    
    def get_attachment(self, attachment_id):
        """Get attachment by ID"""
        try:
            return OfferAttachment.objects.get(
                id=attachment_id, 
                tenant_id=self.tenant_id
            )
        except OfferAttachment.DoesNotExist:
            raise ValueError("Attachment not found")
    
    def update_attachment(self, attachment_id, **kwargs):
        """Update attachment details"""
        try:
            attachment = self.get_attachment(attachment_id)
            
            # Update allowed fields
            allowed_fields = ['description', 'is_primary', 'display_order']
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(attachment, field, value)
            
            # Handle primary flag
            if 'is_primary' in kwargs and kwargs['is_primary']:
                # Unset other primary attachments for this offer
                OfferAttachment.objects.filter(
                    offer=attachment.offer,
                    tenant_id=self.tenant_id,
                    is_primary=True
                ).exclude(id=attachment.id).update(is_primary=False)
            
            attachment.save()
            return attachment
            
        except Exception as e:
            self.logger.error(f"Error updating attachment: {str(e)}")
            raise
    
    def delete_attachment(self, attachment_id):
        """Delete an attachment"""
        try:
            attachment = self.get_attachment(attachment_id)
            
            # Delete file from storage
            if attachment.file and hasattr(attachment.file, 'delete'):
                attachment.file.delete(save=False)
            
            # Delete thumbnail if exists
            if attachment.thumbnail and hasattr(attachment.thumbnail, 'delete'):
                attachment.thumbnail.delete(save=False)
            
            # Delete attachment record
            attachment.delete()
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting attachment: {str(e)}")
            raise
    
    def get_offer_attachments(self, offer_id, file_type=None):
        """Get all attachments for an offer"""
        try:
            queryset = OfferAttachment.objects.filter(
                offer_id=offer_id,
                tenant_id=self.tenant_id,
                is_active=True
            )
            
            if file_type:
                queryset = queryset.filter(file_type=file_type)
            
            return queryset.order_by('display_order', 'created_at')
            
        except Exception as e:
            self.logger.error(f"Error getting attachments: {str(e)}")
            raise
    
    def get_primary_attachment(self, offer_id):
        """Get primary attachment for an offer"""
        try:
            return OfferAttachment.objects.get(
                offer_id=offer_id,
                tenant_id=self.tenant_id,
                is_primary=True,
                is_active=True
            )
        except OfferAttachment.DoesNotExist:
            # Return first attachment if no primary is set
            return OfferAttachment.objects.filter(
                offer_id=offer_id,
                tenant_id=self.tenant_id,
                is_active=True
            ).first()
    
    def reorder_attachments(self, offer_id, attachment_order):
        """Reorder attachments for an offer"""
        try:
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            for index, attachment_id in enumerate(attachment_order):
                OfferAttachment.objects.filter(
                    id=attachment_id,
                    offer=offer,
                    tenant_id=self.tenant_id
                ).update(display_order=index + 1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error reordering attachments: {str(e)}")
            raise
    
    def _generate_file_hash(self, file_obj):
        """Generate SHA-256 hash of file content"""
        hash_sha256 = hashlib.sha256()
        
        # Reset file pointer
        file_obj.seek(0)
        
        # Read file in chunks
        for chunk in iter(lambda: file_obj.read(4096), b""):
            hash_sha256.update(chunk)
        
        # Reset file pointer
        file_obj.seek(0)
        
        return hash_sha256.hexdigest()
    
    def _determine_file_type(self, filename):
        """Determine file type from filename"""
        extension = os.path.splitext(filename)[1].lower()
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
        document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
        video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}
        audio_extensions = {'.mp3', '.wav', '.ogg', '.aac', '.flac'}
        
        if extension in image_extensions:
            return 'image'
        elif extension in document_extensions:
            return 'document'
        elif extension in video_extensions:
            return 'video'
        elif extension in audio_extensions:
            return 'audio'
        else:
            return 'other'
    
    def _process_image(self, file_obj):
        """Process image and extract metadata"""
        try:
            # Open image
            image = Image.open(file_obj)
            width, height = image.size
            
            # Create thumbnail
            thumbnail_size = (150, 150)
            image_copy = image.copy()
            image_copy.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            
            # Save thumbnail to bytes
            thumbnail_bytes = BytesIO()
            image_copy.save(thumbnail_bytes, format='JPEG', quality=85)
            thumbnail_bytes.seek(0)
            
            # Create UploadedFile for thumbnail
            thumbnail_filename = f"thumb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            thumbnail = UploadedFile(
                file=thumbnail_bytes,
                name=thumbnail_filename
            )
            
            return width, height, thumbnail
            
        except Exception as e:
            self.logger.warning(f"Error processing image: {str(e)}")
            return None, None, None
    
    def _get_next_display_order(self, offer):
        """Get next display order for offer attachments"""
        last_order = OfferAttachment.objects.filter(
            offer=offer,
            tenant_id=self.tenant_id
        ).aggregate(models.Max('display_order'))['display_order__max']
        
        return (last_order or 0) + 1
    
    def get_attachment_stats(self, offer_id):
        """Get attachment statistics for an offer"""
        try:
            attachments = OfferAttachment.objects.filter(
                offer_id=offer_id,
                tenant_id=self.tenant_id
            )
            
            stats = {
                'total_count': attachments.count(),
                'total_size': attachments.aggregate(
                    total=models.Sum('file_size')
                )['total_size'] or 0,
                'by_type': attachments.values('file_type').annotate(
                    count=models.Count('id')
                ).order_by('file_type'),
                'primary_count': attachments.filter(is_primary=True).count(),
                'active_count': attachments.filter(is_active=True).count()
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting attachment stats: {str(e)}")
            raise
