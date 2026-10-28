"""
Gamification Attachment Upload View — File upload handling for gamification.

This module provides file upload capabilities for gamification assets,
including badge images, challenge attachments, and other media files.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.gamification.exceptions import GamificationServiceError
from api.gamification.models import (
    Badge, DailyChallenge, UserPoints, PointsTransaction, StreakFreeze, 
    ContestParticipant, GamificationConfig, GamificationInsight
)
from api.gamification.encryption import log_security_event

User = get_user_model()
logger = logging.getLogger(__name__)


class AttachmentUploader:
    """Attachment uploader for gamification files."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.allowed_extensions = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
            'document': ['.pdf', '.doc', '.docx', '.txt'],
            'video': ['.mp4', '.avi', '.mov', '.wmv'],
            'audio': ['.mp3', '.wav', '.ogg']
        }
        self.max_file_sizes = {
            'image': 5 * 1024 * 1024,  # 5MB
            'document': 10 * 1024 * 1024,  # 10MB
            'video': 100 * 1024 * 1024,  # 100MB
            'audio': 20 * 1024 * 1024  # 20MB
        }
    
    def validate_file(self, file: UploadedFile, file_type: str = 'image') -> Dict[str, Any]:
        """Validate uploaded file."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check if file is empty
        if not file or file.size == 0:
            validation_result['valid'] = False
            validation_result['errors'].append('File is empty')
            return validation_result
        
        # Check file extension
        file_extension = os.path.splitext(file.name)[1].lower()
        allowed_extensions = self.allowed_extensions.get(file_type, [])
        
        if file_extension not in allowed_extensions:
            validation_result['valid'] = False
            validation_result['errors'].append(f'File type {file_extension} not allowed. Allowed types: {", ".join(allowed_extensions)}')
        
        # Check file size
        max_size = self.max_file_sizes.get(file_type, 5 * 1024 * 1024)
        if file.size > max_size:
            validation_result['valid'] = False
            validation_result['errors'].append(f'File size {file.size} bytes exceeds maximum {max_size} bytes')
        
        # Check MIME type
        allowed_mime_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'],
            'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
            'video': ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-ms-wmv'],
            'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg']
        }
        
        if hasattr(file, 'content_type'):
            allowed_mimes = allowed_mime_types.get(file_type, [])
            if file.content_type not in allowed_mimes:
                validation_result['warnings'].append(f'MIME type {file.content_type} may not be allowed')
        
        return validation_result
    
    def generate_filename(self, original_filename: str, prefix: str = '') -> str:
        """Generate unique filename."""
        file_extension = os.path.splitext(original_filename)[1]
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if prefix:
            return f"{prefix}_{timestamp}_{unique_id}{file_extension}"
        else:
            return f"{timestamp}_{unique_id}{file_extension}"
    
    def upload_file(self, file: UploadedFile, upload_path: str = 'gamification/uploads/',
                   file_type: str = 'image', prefix: str = '') -> Dict[str, Any]:
        """Upload file to storage."""
        try:
            # Validate file
            validation_result = self.validate_file(file, file_type)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings']
                }
            
            # Generate filename
            filename = self.generate_filename(file.name, prefix)
            
            # Create upload path
            full_path = os.path.join(upload_path, filename)
            
            # Ensure directory exists
            if not default_storage.exists(upload_path):
                default_storage.makedirs(upload_path)
            
            # Save file
            file_path = default_storage.save(full_path, file)
            file_url = default_storage.url(file_path)
            
            # Log upload
            self.logger.info(f"File uploaded successfully: {file_path}")
            
            return {
                'success': True,
                'file_path': file_path,
                'file_url': file_url,
                'filename': filename,
                'original_filename': file.name,
                'file_size': file.size,
                'content_type': getattr(file, 'content_type', None),
                'warnings': validation_result['warnings']
            }
            
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }
    
    def delete_file(self, file_path: str) -> bool:
        """Delete uploaded file."""
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
                self.logger.info(f"File deleted successfully: {file_path}")
                return True
            else:
                self.logger.warning(f"File not found for deletion: {file_path}")
                return False
        except Exception as e:
            self.logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information."""
        try:
            if not default_storage.exists(file_path):
                return None
            
            file_size = default_storage.size(file_path)
            modified_time = default_storage.modified_time(file_path)
            file_url = default_storage.url(file_path)
            
            return {
                'file_path': file_path,
                'file_url': file_url,
                'file_size': file_size,
                'modified_time': modified_time,
                'exists': True
            }
        except Exception as e:
            self.logger.error(f"Error getting file info for {file_path}: {e}")
            return None


class BadgeImageUploader(AttachmentUploader):
    """Specialized uploader for badge images."""
    
    def __init__(self):
        super().__init__()
        self.upload_path = 'gamification/badges/'
        self.file_type = 'image'
        self.prefix = 'badge'
    
    def upload_badge_image(self, file: UploadedFile, badge_id: Optional[str] = None) -> Dict[str, Any]:
        """Upload badge image."""
        prefix = f"badge_{badge_id}" if badge_id else self.prefix
        return self.upload_file(file, self.upload_path, self.file_type, prefix)
    
    def update_badge_image(self, badge: Badge, file: UploadedFile) -> Dict[str, Any]:
        """Update badge image and delete old one."""
        try:
            # Delete old image if exists
            if badge.icon and badge.icon.startswith(self.upload_path):
                self.delete_file(badge.icon)
            
            # Upload new image
            upload_result = self.upload_badge_image(file, str(badge.id))
            
            if upload_result['success']:
                # Update badge icon
                badge.icon = upload_result['file_path']
                badge.save(update_fields=['icon'])
                
                upload_result['badge_id'] = str(badge.id)
                upload_result['badge_name'] = badge.name
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error updating badge image for badge {badge.id}: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }


class ChallengeAttachmentUploader(AttachmentUploader):
    """Specialized uploader for challenge attachments."""
    
    def __init__(self):
        super().__init__()
        self.upload_path = 'gamification/challenges/'
        self.file_type = 'document'
        self.prefix = 'challenge'
    
    def upload_challenge_attachment(self, file: UploadedFile, challenge_id: Optional[str] = None) -> Dict[str, Any]:
        """Upload challenge attachment."""
        prefix = f"challenge_{challenge_id}" if challenge_id else self.prefix
        return self.upload_file(file, self.upload_path, self.file_type, prefix)
    
    def update_challenge_attachment(self, challenge: DailyChallenge, file: UploadedFile) -> Dict[str, Any]:
        """Update challenge attachment."""
        try:
            # Upload new attachment
            upload_result = self.upload_challenge_attachment(file, str(challenge.id))
            
            if upload_result['success']:
                # Store attachment info in metadata
                metadata = challenge.metadata or {}
                metadata['attachment'] = {
                    'file_path': upload_result['file_path'],
                    'file_url': upload_result['file_url'],
                    'original_filename': upload_result['original_filename'],
                    'file_size': upload_result['file_size'],
                    'uploaded_at': timezone.now().isoformat()
                }
                challenge.metadata = metadata
                challenge.save(update_fields=['metadata'])
                
                upload_result['challenge_id'] = str(challenge.id)
                upload_result['challenge_title'] = challenge.title
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error updating challenge attachment for challenge {challenge.id}: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }


class ContestAttachmentUploader(AttachmentUploader):
    """Specialized uploader for contest attachments."""
    
    def __init__(self):
        super().__init__()
        self.upload_path = 'gamification/contests/'
        self.file_type = 'document'
        self.prefix = 'contest'
    
    def upload_contest_attachment(self, file: UploadedFile, contest_id: Optional[str] = None) -> Dict[str, Any]:
        """Upload contest attachment."""
        prefix = f"contest_{contest_id}" if contest_id else self.prefix
        return self.upload_file(file, self.upload_path, self.file_type, prefix)
    
    def update_contest_attachment(self, participant: ContestParticipant, file: UploadedFile) -> Dict[str, Any]:
        """Update contest participant attachment."""
        try:
            # Upload new attachment
            upload_result = self.upload_contest_attachment(file, str(participant.contest_cycle_id))
            
            if upload_result['success']:
                # Store attachment info in metadata
                metadata = participant.metadata or {}
                metadata['attachment'] = {
                    'file_path': upload_result['file_path'],
                    'file_url': upload_result['file_url'],
                    'original_filename': upload_result['original_filename'],
                    'file_size': upload_result['file_size'],
                    'uploaded_at': timezone.now().isoformat()
                }
                participant.metadata = metadata
                participant.save(update_fields=['metadata'])
                
                upload_result['participant_id'] = str(participant.id)
                upload_result['contest_id'] = str(participant.contest_cycle_id)
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error updating contest attachment for participant {participant.id}: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }


class GamificationConfigUploader(AttachmentUploader):
    """Specialized uploader for gamification configuration files."""
    
    def __init__(self):
        super().__init__()
        self.upload_path = 'gamification/config/'
        self.file_type = 'document'
        self.prefix = 'config'
    
    def upload_config_file(self, file: UploadedFile, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Upload gamification configuration file."""
        prefix = f"config_{tenant_id}" if tenant_id else self.prefix
        return self.upload_file(file, self.upload_path, self.file_type, prefix)
    
    def update_config_file(self, config: GamificationConfig, file: UploadedFile) -> Dict[str, Any]:
        """Update gamification configuration file."""
        try:
            # Upload new config file
            upload_result = self.upload_config_file(file, str(config.tenant_id))
            
            if upload_result['success']:
                # Store file info in metadata
                metadata = config.metadata or {}
                metadata['config_file'] = {
                    'file_path': upload_result['file_path'],
                    'file_url': upload_result['file_url'],
                    'original_filename': upload_result['original_filename'],
                    'file_size': upload_result['file_size'],
                    'uploaded_at': timezone.now().isoformat()
                }
                config.metadata = metadata
                config.save(update_fields=['metadata'])
                
                upload_result['config_id'] = str(config.id)
                upload_result['tenant_id'] = str(config.tenant_id)
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error updating config file for config {config.id}: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }


class InsightReportUploader(AttachmentUploader):
    """Specialized uploader for insight reports."""
    
    def __init__(self):
        super().__init__()
        self.upload_path = 'gamification/insights/'
        self.file_type = 'document'
        self.prefix = 'insight'
    
    def upload_insight_report(self, file: UploadedFile, insight_id: Optional[str] = None) -> Dict[str, Any]:
        """Upload insight report."""
        prefix = f"insight_{insight_id}" if insight_id else self.prefix
        return self.upload_file(file, self.upload_path, self.file_type, prefix)
    
    def update_insight_report(self, insight: GamificationInsight, file: UploadedFile) -> Dict[str, Any]:
        """Update insight report."""
        try:
            # Upload new report
            upload_result = self.upload_insight_report(file, str(insight.id))
            
            if upload_result['success']:
                # Store report info in metadata
                metadata = insight.metadata or {}
                metadata['report'] = {
                    'file_path': upload_result['file_path'],
                    'file_url': upload_result['file_url'],
                    'original_filename': upload_result['original_filename'],
                    'file_size': upload_result['file_size'],
                    'uploaded_at': timezone.now().isoformat()
                }
                insight.metadata = metadata
                insight.save(update_fields=['metadata'])
                
                upload_result['insight_id'] = str(insight.id)
                upload_result['date'] = str(insight.date)
            
            return upload_result
            
        except Exception as e:
            self.logger.error(f"Error updating insight report for insight {insight.id}: {e}")
            return {
                'success': False,
                'errors': [str(e)]
            }


# Global instances
attachment_uploader = AttachmentUploader()
badge_image_uploader = BadgeImageUploader()
challenge_attachment_uploader = ChallengeAttachmentUploader()
contest_attachment_uploader = ContestAttachmentUploader()
config_uploader = GamificationConfigUploader()
insight_uploader = InsightReportUploader()


# API Views
@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_badge_image(request: HttpRequest, badge_id: Optional[str] = None) -> JsonResponse:
    """Upload badge image."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate badge exists if badge_id provided
        if badge_id:
            try:
                badge = Badge.objects.get(id=badge_id)
            except Badge.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': ['Badge not found']
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            badge = None
        
        # Upload image
        uploader = BadgeImageUploader()
        
        if badge:
            upload_result = uploader.update_badge_image(badge, file)
        else:
            upload_result = uploader.upload_badge_image(file, badge_id)
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type="badge_image",
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading badge image: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_challenge_attachment(request: HttpRequest, challenge_id: Optional[str] = None) -> JsonResponse:
    """Upload challenge attachment."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate challenge exists if challenge_id provided
        if challenge_id:
            try:
                challenge = DailyChallenge.objects.get(id=challenge_id)
            except DailyChallenge.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': ['Challenge not found']
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            challenge = None
        
        # Upload attachment
        uploader = ChallengeAttachmentUploader()
        
        if challenge:
            upload_result = uploader.update_challenge_attachment(challenge, file)
        else:
            upload_result = uploader.upload_challenge_attachment(file, challenge_id)
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type="challenge_attachment",
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading challenge attachment: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_general_attachment(request: HttpRequest) -> JsonResponse:
    """Upload general attachment."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        file_type = request.POST.get('file_type', 'image')
        prefix = request.POST.get('prefix', 'attachment')
        
        # Validate file_type
        if file_type not in attachment_uploader.allowed_extensions:
            return JsonResponse({
                'success': False,
                'errors': [f'Invalid file type: {file_type}']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Upload file
        upload_result = attachment_uploader.upload_file(
            file, 
            'gamification/attachments/', 
            file_type, 
            prefix
        )
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type=file_type,
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading general attachment: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["DELETE"])
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_attachment(request: HttpRequest) -> JsonResponse:
    """Delete attachment."""
    try:
        file_path = request.GET.get('file_path')
        if not file_path:
            return JsonResponse({
                'success': False,
                'errors': ['file_path parameter is required']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Security check - ensure user can delete this file
        if not file_path.startswith('gamification/'):
            return JsonResponse({
                'success': False,
                'errors': ['Invalid file path']
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Delete file
        success = attachment_uploader.delete_file(file_path)
        
        # Log security event
        log_security_event(
            "file_delete",
            request.user.id,
            file_path=file_path
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'File deleted successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': ['File not found or could not be deleted']
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error deleting attachment: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attachment_info(request: HttpRequest) -> JsonResponse:
    """Get attachment information."""
    try:
        file_path = request.GET.get('file_path')
        if not file_path:
            return JsonResponse({
                'success': False,
                'errors': ['file_path parameter is required']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Security check
        if not file_path.startswith('gamification/'):
            return JsonResponse({
                'success': False,
                'errors': ['Invalid file path']
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get file info
        file_info = attachment_uploader.get_file_info(file_path)
        
        if file_info:
            return JsonResponse({
                'success': True,
                'file_info': file_info
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': ['File not found']
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error getting attachment info: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_contest_attachment(request: HttpRequest, participant_id: Optional[str] = None) -> JsonResponse:
    """Upload contest attachment."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate participant exists if participant_id provided
        if participant_id:
            try:
                participant = ContestParticipant.objects.get(id=participant_id)
            except ContestParticipant.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': ['Contest participant not found']
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            participant = None
        
        # Upload attachment
        uploader = ContestAttachmentUploader()
        
        if participant:
            upload_result = uploader.update_contest_attachment(participant, file)
        else:
            upload_result = uploader.upload_contest_attachment(file, participant_id)
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type="contest_attachment",
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading contest attachment: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_config_file(request: HttpRequest, tenant_id: Optional[str] = None) -> JsonResponse:
    """Upload gamification configuration file."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate config exists if tenant_id provided
        if tenant_id:
            try:
                config = GamificationConfig.objects.get(tenant_id=tenant_id)
            except GamificationConfig.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': ['Gamification config not found']
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            config = None
        
        # Upload config file
        uploader = GamificationConfigUploader()
        
        if config:
            upload_result = uploader.update_config_file(config, file)
        else:
            upload_result = uploader.upload_config_file(file, tenant_id)
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type="config_file",
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading config file: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_insight_report(request: HttpRequest, insight_id: Optional[str] = None) -> JsonResponse:
    """Upload insight report."""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'errors': ['No file provided']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate insight exists if insight_id provided
        if insight_id:
            try:
                insight = GamificationInsight.objects.get(id=insight_id)
            except GamificationInsight.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': ['Gamification insight not found']
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            insight = None
        
        # Upload insight report
        uploader = InsightReportUploader()
        
        if insight:
            upload_result = uploader.update_insight_report(insight, file)
        else:
            upload_result = uploader.upload_insight_report(file, insight_id)
        
        # Log security event
        log_security_event(
            "file_upload",
            request.user.id,
            file_type="insight_report",
            file_name=file.name,
            file_size=file.size
        )
        
        if upload_result['success']:
            return JsonResponse(upload_result, status=status.HTTP_201_CREATED)
        else:
            return JsonResponse(upload_result, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error uploading insight report: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_user_attachments(request: HttpRequest) -> JsonResponse:
    """List user's uploaded attachments."""
    try:
        user_id = request.user.id
        
        # Get attachments from cache or database
        cache_key = f"user_attachments:{user_id}"
        cached_attachments = cache.get(cache_key)
        
        if cached_attachments:
            return JsonResponse({
                'success': True,
                'attachments': cached_attachments
            })
        
        # For now, return empty list (in production, this would query database)
        attachments = []
        
        # Cache for 5 minutes
        cache.set(cache_key, attachments, 300)
        
        return JsonResponse({
            'success': True,
            'attachments': attachments
        })
        
    except Exception as e:
        logger.error(f"Error listing user attachments: {e}")
        return JsonResponse({
            'success': False,
            'errors': [str(e)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
