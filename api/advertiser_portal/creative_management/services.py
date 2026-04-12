"""
Creative Management Services

This module contains service classes for managing creatives,
including creation, approval, optimization, and analytics.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import hashlib
import os

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
from django.contrib.auth import get_user_model

from ..database_models.creative_model import Creative, CreativeAsset, CreativeApprovalLog
from ..database_models.campaign_model import Campaign
from ..database_models.impression_model import Impression
from ..database_models.click_model import Click
from ..database_models.conversion_model import Conversion
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class CreativeService:
    """Service for managing creative operations."""
    
    @staticmethod
    def create_creative(data: Dict[str, Any], created_by: Optional[User] = None) -> Creative:
        """Create a new creative."""
        try:
            with transaction.atomic():
                # Handle file upload
                creative_file = data.get('file')
                file_info = {}
                
                if creative_file:
                    file_info = CreativeService._process_file_upload(creative_file)
                
                # Create creative
                creative = Creative.objects.create(
                    advertiser=data.get('advertiser'),
                    campaign=data.get('campaign'),
                    name=data['name'],
                    description=data.get('description', ''),
                    creative_type=data['creative_type'],
                    file_path=file_info.get('file_path'),
                    file_name=file_info.get('file_name'),
                    file_size=file_info.get('file_size', 0),
                    file_mime_type=file_info.get('mime_type'),
                    file_hash=file_info.get('file_hash'),
                    width=data.get('width'),
                    height=data.get('height'),
                    duration=data.get('duration'),
                    aspect_ratio=data.get('aspect_ratio'),
                    file_format=data.get('file_format'),
                    color_scheme=data.get('color_scheme', []),
                    brand_colors=data.get('brand_colors', []),
                    text_content=data.get('text_content', ''),
                    call_to_action=data.get('call_to_action', ''),
                    landing_page_url=data.get('landing_page_url', ''),
                    display_url=data.get('display_url', ''),
                    third_party_tracking_urls=data.get('third_party_tracking_urls', []),
                    click_tracking_url=data.get('click_tracking_url', ''),
                    impression_tracking_url=data.get('impression_tracking_url', ''),
                    dynamic_creative=data.get('dynamic_creative', False),
                    template_id=data.get('template_id'),
                    template_data=data.get('template_data', {}),
                    personalization_rules=data.get('personalization_rules', {}),
                    ad_variations=data.get('ad_variations', []),
                    fallback_creative=data.get('fallback_creative'),
                    status=CreativeStatusEnum.DRAFT.value,
                    approval_status=CreativeApprovalStatusEnum.PENDING.value,
                    quality_score=0,
                    performance_score=0,
                    labels=data.get('labels', []),
                    external_creative_id=data.get('external_creative_id'),
                    integration_settings=data.get('integration_settings', {}),
                    auto_optimize=data.get('auto_optimize', False),
                    optimization_goals=data.get('optimization_goals', []),
                    require_approval=data.get('require_approval', True),
                    created_by=created_by
                )
                
                # Create assets if provided
                assets_data = data.get('assets', [])
                for asset_data in assets_data:
                    CreativeAsset.objects.create(
                        creative=creative,
                        asset_type=asset_data.get('asset_type'),
                        asset_path=asset_data.get('asset_path'),
                        asset_name=asset_data.get('asset_name'),
                        asset_size=asset_data.get('asset_size', 0),
                        asset_mime_type=asset_data.get('mime_type'),
                        asset_url=asset_data.get('asset_url'),
                        created_by=created_by
                    )
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=created_by,
                    title='Creative Created',
                    message=f'Creative "{creative.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    creative,
                    created_by,
                    description=f"Created creative: {creative.name}"
                )
                
                return creative
                
        except Exception as e:
            logger.error(f"Error creating creative: {str(e)}")
            raise CreativeServiceError(f"Failed to create creative: {str(e)}")
    
    @staticmethod
    def update_creative(creative_id: UUID, data: Dict[str, Any],
                         updated_by: Optional[User] = None) -> Creative:
        """Update creative details."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Handle file update
                creative_file = data.get('file')
                if creative_file:
                    file_info = CreativeService._process_file_upload(creative_file)
                    
                    # Update file info
                    old_file_path = creative.file_path
                    creative.file_path = file_info.get('file_path')
                    creative.file_name = file_info.get('file_name')
                    creative.file_size = file_info.get('file_size', 0)
                    creative.file_mime_type = file_info.get('mime_type')
                    creative.file_hash = file_info.get('file_hash')
                    
                    # Delete old file
                    if old_file_path and os.path.exists(old_file_path):
                        os.remove(old_file_path)
                    
                    changed_fields['file'] = {'old': old_file_path, 'new': creative.file_path}
                
                # Update basic fields
                for field in ['name', 'description', 'landing_page_url', 'display_url',
                             'call_to_action', 'text_content', 'color_scheme', 'brand_colors',
                             'third_party_tracking_urls', 'click_tracking_url',
                             'impression_tracking_url', 'dynamic_creative', 'template_id',
                             'template_data', 'personalization_rules', 'ad_variations',
                             'fallback_creative', 'labels', 'external_creative_id',
                             'integration_settings', 'auto_optimize', 'optimization_goals',
                             'require_approval']:
                    if field in data:
                        old_value = getattr(creative, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(creative, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                creative.modified_by = updated_by
                creative.save()
                
                # Update assets if provided
                assets_data = data.get('assets', [])
                if assets_data:
                    # Delete existing assets
                    creative.assets.all().delete()
                    
                    # Create new assets
                    for asset_data in assets_data:
                        CreativeAsset.objects.create(
                            creative=creative,
                            asset_type=asset_data.get('asset_type'),
                            asset_path=asset_data.get('asset_path'),
                            asset_name=asset_data.get('asset_name'),
                            asset_size=asset_data.get('asset_size', 0),
                            asset_mime_type=asset_data.get('mime_type'),
                            asset_url=asset_data.get('asset_url'),
                            created_by=updated_by
                        )
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        creative,
                        changed_fields,
                        updated_by,
                        description=f"Updated creative: {creative.name}"
                    )
                
                return creative
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error updating creative {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to update creative: {str(e)}")
    
    @staticmethod
    def delete_creative(creative_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete creative (soft delete)."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    creative,
                    deleted_by,
                    description=f"Deleted creative: {creative.name}"
                )
                
                # Soft delete
                creative.soft_delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=deleted_by,
                    title='Creative Deleted',
                    message=f'Creative "{creative.name}" has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error deleting creative {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to delete creative: {str(e)}")
    
    @staticmethod
    def get_creative(creative_id: UUID) -> Creative:
        """Get creative by ID."""
        try:
            return Creative.objects.get(id=creative_id, is_deleted=False)
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
    
    @staticmethod
    def list_creatives(advertiser_id: Optional[UUID] = None, campaign_id: Optional[UUID] = None,
                        filters: Optional[Dict[str, Any]] = None,
                        page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List creatives with filtering and pagination."""
        try:
            queryset = Creative.objects.filter(is_deleted=False)
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Apply campaign filter
            if campaign_id:
                queryset = queryset.filter(campaign_id=campaign_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'creative_type' in filters:
                    queryset = queryset.filter(creative_type=filters['creative_type'])
                if 'approval_status' in filters:
                    queryset = queryset.filter(approval_status=filters['approval_status'])
                if 'is_active' in filters:
                    if filters['is_active']:
                        queryset = queryset.filter(status='active')
                    else:
                        queryset = queryset.exclude(status='active')
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(name__icontains=search) |
                        Q(description__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            creatives = queryset[offset:offset + page_size]
            
            return {
                'creatives': creatives,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing creatives: {str(e)}")
            raise CreativeServiceError(f"Failed to list creatives: {str(e)}")
    
    @staticmethod
    def activate_creative(creative_id: UUID, activated_by: Optional[User] = None) -> bool:
        """Activate creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                creative.status = CreativeStatusEnum.ACTIVE.value
                creative.save(update_fields=['status'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=activated_by,
                    title='Creative Activated',
                    message=f'Creative "{creative.name}" has been activated.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log activation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='activate',
                    object_type='Creative',
                    object_id=str(creative.id),
                    user=activated_by,
                    advertiser=creative.advertiser,
                    description=f"Activated creative: {creative.name}"
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error activating creative {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def pause_creative(creative_id: UUID, paused_by: Optional[User] = None) -> bool:
        """Pause creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                creative.status = CreativeStatusEnum.PAUSED.value
                creative.save(update_fields=['status'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=paused_by,
                    title='Creative Paused',
                    message=f'Creative "{creative.name}" has been paused.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log pause
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='pause',
                    object_type='Creative',
                    object_id=str(creative.id),
                    user=paused_by,
                    advertiser=creative.advertiser,
                    description=f"Paused creative: {creative.name}"
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error pausing creative {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def duplicate_creative(creative_id: UUID, new_name: Optional[str] = None,
                           duplicated_by: Optional[User] = None) -> Creative:
        """Duplicate creative."""
        try:
            original_creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                new_creative = original_creative.duplicate(new_name)
                
                # Duplicate assets if exists
                for asset in original_creative.assets.all():
                    CreativeAsset.objects.create(
                        creative=new_creative,
                        asset_type=asset.asset_type,
                        asset_path=asset.asset_path,
                        asset_name=asset.asset_name,
                        asset_size=asset.asset_size,
                        asset_mime_type=asset.asset_mime_type,
                        asset_url=asset.asset_url,
                        created_by=duplicated_by
                    )
                
                # Send notification
                Notification.objects.create(
                    advertiser=new_creative.advertiser,
                    user=duplicated_by,
                    title='Creative Duplicated',
                    message=f'Creative "{new_creative.name}" has been duplicated from "{original_creative.name}".',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log duplication
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='duplicate',
                    object_type='Creative',
                    object_id=str(new_creative.id),
                    user=duplicated_by,
                    advertiser=new_creative.advertiser,
                    description=f"Duplicated creative: {original_creative.name} -> {new_creative.name}"
                )
                
                return new_creative
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error duplicating creative {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to duplicate creative: {str(e)}")
    
    @staticmethod
    def get_creative_performance(creative_id: UUID) -> Dict[str, Any]:
        """Get creative performance metrics."""
        try:
            creative = CreativeService.get_creative(creative_id)
            return creative.get_performance_metrics()
        except Exception as e:
            logger.error(f"Error getting creative performance {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to get creative performance: {str(e)}")
    
    @staticmethod
    def _process_file_upload(uploaded_file: InMemoryUploadedFile) -> Dict[str, Any]:
        """Process uploaded file and return file info."""
        try:
            # Generate unique filename
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"creative_{timestamp}_{uploaded_file.name}"
            
            # Create upload directory if not exists
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'creatives')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Calculate file hash
            file_hash = CreativeService._calculate_file_hash(file_path)
            
            # Get file info
            file_size = uploaded_file.size
            mime_type = uploaded_file.content_type
            
            return {
                'file_path': file_path,
                'file_name': uploaded_file.name,
                'file_size': file_size,
                'mime_type': mime_type,
                'file_hash': file_hash
            }
            
        except Exception as e:
            logger.error(f"Error processing file upload: {str(e)}")
            raise CreativeServiceError(f"Failed to process file upload: {str(e)}")
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    @staticmethod
    def validate_file(uploaded_file: InMemoryUploadedFile, creative_type: str) -> bool:
        """Validate uploaded file based on creative type."""
        try:
            # Get allowed file types for creative type
            allowed_types = {
                CreativeTypeEnum.IMAGE.value: ['image/jpeg', 'image/png', 'image/gif'],
                CreativeTypeEnum.VIDEO.value: ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
                CreativeTypeEnum.HTML.value: ['text/html', 'application/html'],
                CreativeTypeEnum.RICH_MEDIA.value: ['application/x-shockwave-flash', 'application/javascript'],
                CreativeTypeEnum.TEXT.value: ['text/plain'],
                CreativeTypeEnum.CAROUSEL.value: ['image/jpeg', 'image/png'],
                CreativeTypeEnum.BANNER.value: ['image/jpeg', 'image/png', 'image/gif']
            }
            
            allowed_mime_types = allowed_types.get(creative_type, [])
            
            if allowed_mime_types and uploaded_file.content_type not in allowed_mime_types:
                return False
            
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if uploaded_file.size > max_size:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return False
    
    @staticmethod
    def get_optimization_recommendations(creative_id: UUID) -> List[Dict[str, Any]]:
        """Get optimization recommendations for creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            return creative.get_optimization_recommendations()
        except Exception as e:
            logger.error(f"Error getting optimization recommendations {creative_id}: {str(e)}")
            return []


class CreativeApprovalService:
    """Service for managing creative approval workflow."""
    
    @staticmethod
    def submit_for_approval(creative_id: UUID, submitted_by: Optional[User] = None) -> bool:
        """Submit creative for approval."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                creative.approval_status = CreativeApprovalStatusEnum.SUBMITTED.value
                creative.save(update_fields=['approval_status'])
                
                # Create approval log
                CreativeApprovalLog.objects.create(
                    creative=creative,
                    action='submitted',
                    reviewed_by=submitted_by,
                    notes='Creative submitted for approval'
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=submitted_by,
                    title='Creative Submitted for Approval',
                    message=f'Creative "{creative.name}" has been submitted for approval.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error submitting creative for approval {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def approve_creative(creative_id: UUID, notes: str = '', approved_by: Optional[User] = None) -> bool:
        """Approve creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                creative.approval_status = CreativeApprovalStatusEnum.APPROVED.value
                creative.approved_by = approved_by
                creative.approved_at = timezone.now()
                creative.save(update_fields=['approval_status', 'approved_by', 'approved_at'])
                
                # Create approval log
                CreativeApprovalLog.objects.create(
                    creative=creative,
                    action='approved',
                    reviewed_by=approved_by,
                    notes=notes
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=creative.created_by,
                    title='Creative Approved',
                    message=f'Your creative "{creative.name}" has been approved.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error approving creative {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def reject_creative(creative_id: UUID, rejection_reason: str = '',
                        rejected_by: Optional[User] = None) -> bool:
        """Reject creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                creative.approval_status = CreativeApprovalStatusEnum.REJECTED.value
                creative.rejected_by = rejected_by
                creative.rejected_at = timezone.now()
                creative.rejection_reason = rejection_reason
                creative.save(update_fields=['approval_status', 'rejected_by', 'rejected_at', 'rejection_reason'])
                
                # Create approval log
                CreativeApprovalLog.objects.create(
                    creative=creative,
                    action='rejected',
                    reviewed_by=rejected_by,
                    notes=rejection_reason
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=creative.advertiser,
                    user=creative.created_by,
                    title='Creative Rejected',
                    message=f'Your creative "{creative.name}" has been rejected. Reason: {rejection_reason}',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error rejecting creative {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_approval_history(creative_id: UUID) -> List[Dict[str, Any]]:
        """Get approval history for creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            approval_logs = creative.approval_logs.order_by('-created_at')
            
            return [
                {
                    'id': str(log.id),
                    'action': log.action,
                    'reviewed_by': log.reviewed_by.username if log.reviewed_by else None,
                    'notes': log.notes,
                    'created_at': log.created_at.isoformat()
                }
                for log in approval_logs
            ]
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error getting approval history {creative_id}: {str(e)}")
            return []


class CreativeOptimizationService:
    """Service for creative optimization operations."""
    
    @staticmethod
    def optimize_creative(creative_id: UUID, optimization_type: str = 'auto',
                           optimized_by: Optional[User] = None) -> bool:
        """Optimize creative based on performance data."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            with transaction.atomic():
                # Get current performance metrics
                performance = creative.get_performance_metrics()
                
                # Apply optimization logic based on type
                if optimization_type == 'auto':
                    recommendations = creative.get_optimization_recommendations()
                    
                    for recommendation in recommendations:
                        if recommendation['priority'] == 'high':
                            CreativeOptimizationService._apply_optimization(
                                creative, recommendation
                            )
                
                # Update quality and performance scores
                creative.quality_score = creative.calculate_quality_score()
                creative.performance_score = creative.calculate_performance_score()
                creative.save(update_fields=['quality_score', 'performance_score'])
                
                # Log optimization
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='optimize',
                    object_type='Creative',
                    object_id=str(creative.id),
                    user=optimized_by,
                    advertiser=creative.advertiser,
                    description=f"Optimized creative: {creative.name}"
                )
                
                return True
                
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing creative {creative_id}: {str(e)}")
            return False
    
    @staticmethod
    def _apply_optimization(creative: Creative, recommendation: Dict[str, Any]) -> None:
        """Apply specific optimization recommendation."""
        action = recommendation.get('action')
        
        if action == 'update_text':
            # Update text content
            creative.text_content = recommendation.get('suggested_text', creative.text_content)
            creative.save(update_fields=['text_content'])
        
        elif action == 'update_cta':
            # Update call to action
            creative.call_to_action = recommendation.get('suggested_cta', creative.call_to_action)
            creative.save(update_fields=['call_to_action'])
        
        elif action == 'update_colors':
            # Update brand colors
            creative.brand_colors = recommendation.get('suggested_colors', creative.brand_colors)
            creative.save(update_fields=['brand_colors'])
    
    @staticmethod
    def get_optimization_report(creative_id: UUID) -> Dict[str, Any]:
        """Get optimization report for creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            performance = creative.get_performance_metrics()
            recommendations = creative.get_optimization_recommendations()
            
            return {
                'creative': {
                    'id': str(creative.id),
                    'name': creative.name,
                    'status': creative.status,
                    'quality_score': float(creative.quality_score),
                    'performance_score': float(creative.performance_score)
                },
                'performance': performance,
                'recommendations': recommendations,
                'optimization_history': CreativeOptimizationService._get_optimization_history(creative)
            }
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error getting optimization report {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to get optimization report: {str(e)}")
    
    @staticmethod
    def _get_optimization_history(creative: Creative) -> List[Dict[str, Any]]:
        """Get optimization history for creative."""
        # This would query optimization logs
        # For now, return empty list
        return []


class CreativeAnalyticsService:
    """Service for creative analytics and reporting."""
    
    @staticmethod
    def get_analytics(creative_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get creative analytics data."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            # Default to last 30 days if no date range provided
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get aggregated data
            from ..database_models.impression_model import ImpressionAggregation
            from ..database_models.click_model import ClickAggregation
            from ..database_models.conversion_model import ConversionAggregation
            
            impressions = ImpressionAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_cost=Sum('total_cost')
            )
            
            clicks = ClickAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_clicks=Sum('clicks'),
                total_cost=Sum('total_cost')
            )
            
            conversions = ConversionAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('total_revenue')
            )
            
            # Calculate derived metrics
            total_impressions = impressions['total_impressions'] or 0
            total_clicks = clicks['total_clicks'] or 0
            total_conversions = conversions['total_conversions'] or 0
            total_cost = clicks['total_cost'] or 0
            total_revenue = conversions['total_revenue'] or 0
            
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
            cpa = (total_cost / total_conversions) if total_conversions > 0 else 0
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            roas = (total_revenue / total_cost) if total_cost > 0 else 0
            
            return {
                'creative': {
                    'id': str(creative.id),
                    'name': creative.name,
                    'creative_type': creative.creative_type,
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    }
                },
                'metrics': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_cost': float(total_cost),
                    'total_revenue': float(total_revenue),
                    'ctr': ctr,
                    'cpc': cpc,
                    'cpa': cpa,
                    'conversion_rate': conversion_rate,
                    'roas': roas
                }
            }
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error getting analytics {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to get analytics: {str(e)}")
    
    @staticmethod
    def generate_report(creative_id: UUID, report_type: str = 'performance',
                        date_range: Optional[Dict[str, str]] = None,
                        format_type: str = 'pdf') -> str:
        """Generate creative report."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            # Create report
            from ..database_models.analytics_model import AnalyticsReport
            report = AnalyticsReport.objects.create(
                advertiser=creative.advertiser,
                campaign=creative.campaign,
                report_name=f"{creative.name} - {report_type.title()} Report",
                report_type=report_type,
                start_date=date_range['start_date'] if date_range else None,
                end_date=date_range['end_date'] if date_range else None,
                output_format=format_type
            )
            
            # Generate report data
            report.generate_report()
            
            return report.last_file
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error generating report {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to generate report: {str(e)}")


class CreativeAssetService:
    """Service for managing creative assets."""
    
    @staticmethod
    def add_asset(creative_id: UUID, asset_data: Dict[str, Any],
                   created_by: Optional[User] = None) -> CreativeAsset:
        """Add asset to creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            
            asset = CreativeAsset.objects.create(
                creative=creative,
                asset_type=asset_data['asset_type'],
                asset_path=asset_data.get('asset_path'),
                asset_name=asset_data.get('asset_name'),
                asset_size=asset_data.get('asset_size', 0),
                asset_mime_type=asset_data.get('mime_type'),
                asset_url=asset_data.get('asset_url'),
                created_by=created_by
            )
            
            return asset
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error adding asset to creative {creative_id}: {str(e)}")
            raise CreativeServiceError(f"Failed to add asset: {str(e)}")
    
    @staticmethod
    def remove_asset(asset_id: UUID, removed_by: Optional[User] = None) -> bool:
        """Remove asset from creative."""
        try:
            asset = CreativeAsset.objects.get(id=asset_id)
            asset.delete()
            return True
            
        except CreativeAsset.DoesNotExist:
            raise CreativeServiceError(f"Asset {asset_id} not found")
        except Exception as e:
            logger.error(f"Error removing asset {asset_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_assets(creative_id: UUID) -> List[CreativeAsset]:
        """Get all assets for creative."""
        try:
            creative = CreativeService.get_creative(creative_id)
            return creative.assets.all()
            
        except Creative.DoesNotExist:
            raise CreativeNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error getting assets for creative {creative_id}: {str(e)}")
            return []
