# api/cms/services/MediaService.py
"""
MediaService: Upload, resize, CDN push, folder management, tagging, search.
"""
import os
import logging
import mimetypes
from datetime import timedelta
from typing import List, Dict, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class MediaService:
    """Service class for media file management."""

    MAX_FILE_SIZE_MB = 100  # 100MB

    # ────────────────────────────────────────────────────
    # UPLOAD
    # ────────────────────────────────────────────────────

    @staticmethod
    def upload_file(
        file,
        uploaded_by=None,
        folder=None,
        title: str = '',
        alt_text: str = '',
        description: str = '',
        tags: Optional[List] = None,
        is_public: bool = True,
        auto_generate_variants: bool = True
    ) -> Optional[Any]:
        """
        Upload a media file and optionally generate variants.

        Args:
            file: Django uploaded file object
            uploaded_by: User uploading the file
            folder: MediaFolder object
            title: File title
            alt_text: Alt text for accessibility
            description: File description
            tags: List of MediaTag objects
            is_public: Whether file is publicly accessible
            auto_generate_variants: Auto-generate image variants

        Returns:
            MediaFile object or None on failure
        """
        try:
            from api.cms.models_new.media import MediaFile

            # Validate file size
            if hasattr(file, 'size') and file.size > MediaService.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise ValueError(f"File exceeds {MediaService.MAX_FILE_SIZE_MB}MB limit.")

            with transaction.atomic():
                filename = os.path.basename(getattr(file, 'name', 'unknown'))
                media_file = MediaFile.objects.create(
                    file=file,
                    filename=filename,
                    uploaded_by=uploaded_by,
                    folder=folder,
                    title=title or filename,
                    alt_text=alt_text,
                    description=description,
                    is_public=is_public,
                )

                # Assign tags
                if tags:
                    media_file.tags.set(tags)

                logger.info(f"Uploaded media file '{filename}' (id={media_file.id})")

                # Asynchronously generate variants
                if auto_generate_variants and media_file.file_type == 'image':
                    try:
                        from api.cms.services_new.MediaVariantService import MediaVariantService
                        MediaVariantService.generate_all_variants(media_file)
                    except Exception as ve:
                        logger.warning(f"Variant generation failed for file {media_file.id}: {ve}")

                return media_file

        except Exception as e:
            logger.error(f"Error uploading media file: {e}", exc_info=True)
            return None

    @staticmethod
    def upload_multiple_files(
        files: List,
        uploaded_by=None,
        folder=None,
        **kwargs
    ) -> Tuple[List, List]:
        """
        Upload multiple files at once.

        Returns:
            Tuple (uploaded_list, error_list)
        """
        uploaded = []
        errors = []
        for file in files:
            result = MediaService.upload_file(file, uploaded_by=uploaded_by, folder=folder, **kwargs)
            if result:
                uploaded.append(result)
            else:
                errors.append({'file': getattr(file, 'name', 'unknown'), 'error': 'Upload failed'})
        return uploaded, errors

    # ────────────────────────────────────────────────────
    # FILE MANAGEMENT
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_file(file_id: int) -> Optional[Any]:
        """Get a media file by ID."""
        from api.cms.models_new.media import MediaFile
        try:
            return MediaFile.objects.select_related('folder', 'uploaded_by').prefetch_related('tags', 'variants').get(id=file_id, is_active=True)
        except MediaFile.DoesNotExist:
            return None

    @staticmethod
    def get_file_by_uuid(uuid_str: str) -> Optional[Any]:
        """Get a media file by UUID."""
        from api.cms.models_new.media import MediaFile
        try:
            return MediaFile.objects.get(uuid=uuid_str, is_active=True)
        except MediaFile.DoesNotExist:
            return None

    @staticmethod
    def list_files(
        folder=None,
        file_type: Optional[str] = None,
        search: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
        uploaded_by_id: Optional[int] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = '-created_at'
    ) -> Tuple[List, int]:
        """
        List media files with filtering.

        Returns:
            Tuple (files_list, total_count)
        """
        from api.cms.models_new.media import MediaFile
        try:
            q = Q(is_active=True)
            if folder is not None:
                q &= Q(folder=folder)
            if file_type:
                q &= Q(file_type=file_type)
            if search:
                q &= (
                    Q(title__icontains=search) |
                    Q(filename__icontains=search) |
                    Q(alt_text__icontains=search) |
                    Q(description__icontains=search)
                )
            if tag_ids:
                q &= Q(tags__id__in=tag_ids)
            if uploaded_by_id:
                q &= Q(uploaded_by_id=uploaded_by_id)
            if is_public is not None:
                q &= Q(is_public=is_public)

            total = MediaFile.objects.filter(q).distinct().count()
            files = (
                MediaFile.objects.filter(q).distinct()
                .select_related('folder', 'uploaded_by')
                .prefetch_related('tags')
                .order_by(order_by)[offset:offset + limit]
            )
            return list(files), total
        except Exception as e:
            logger.error(f"Error listing media files: {e}", exc_info=True)
            return [], 0

    @staticmethod
    def update_file_metadata(file, data: Dict[str, Any]) -> bool:
        """Update file metadata fields."""
        try:
            allowed_fields = {'title', 'alt_text', 'description', 'caption', 'is_public', 'folder'}
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            for field, value in update_data.items():
                setattr(file, field, value)
            file.save(update_fields=list(update_data.keys()))
            # Update tags if provided
            if 'tags' in data:
                file.tags.set(data['tags'])
            return True
        except Exception as e:
            logger.error(f"Error updating file metadata {file.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def delete_file(file, hard_delete: bool = False) -> bool:
        """Delete or soft-delete a media file."""
        try:
            with transaction.atomic():
                if hard_delete:
                    # Delete physical file
                    try:
                        if file.file:
                            storage = file.file.storage
                            if storage.exists(file.file.name):
                                storage.delete(file.file.name)
                    except Exception:
                        pass
                    # Delete variants
                    file.variants.all().delete()
                    file.delete()
                else:
                    file.is_active = False
                    file.save(update_fields=['is_active'])
                logger.info(f"Deleted media file {file.id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting file {file.id}: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # FOLDER MANAGEMENT
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_folder(name: str, parent=None, created_by=None, is_public: bool = False) -> Optional[Any]:
        """Create a media folder."""
        from api.cms.models_new.media import MediaFolder
        try:
            folder = MediaFolder.objects.create(
                name=name,
                parent=parent,
                created_by=created_by,
                is_public=is_public
            )
            return folder
        except Exception as e:
            logger.error(f"Error creating media folder: {e}", exc_info=True)
            return None

    @staticmethod
    def get_folder_tree(include_file_counts: bool = True) -> List[Dict]:
        """Get full folder tree structure."""
        from api.cms.models_new.media import MediaFolder
        cache_key = 'media_folder_tree'
        result = cache.get(cache_key)
        if result is None:
            root_folders = MediaFolder.objects.filter(
                parent__isnull=True, is_active=True
            ).order_by('name')
            result = [
                MediaService._build_folder_node(f, include_file_counts)
                for f in root_folders
            ]
            cache.set(cache_key, result, 600)
        return result

    @staticmethod
    def _build_folder_node(folder, include_counts: bool) -> Dict:
        """Recursively build folder node."""
        node = {
            'id': folder.id,
            'name': folder.name,
            'path': folder.path,
            'is_public': folder.is_public,
            'children': [
                MediaService._build_folder_node(sub, include_counts)
                for sub in folder.subfolders.filter(is_active=True).order_by('name')
            ]
        }
        if include_counts:
            node['file_count'] = folder.file_count
            node['total_size'] = folder.total_size
        return node

    # ────────────────────────────────────────────────────
    # TAG MANAGEMENT
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_tag(name: str) -> Any:
        """Get or create a media tag."""
        from api.cms.models_new.media import MediaTag
        tag, _ = MediaTag.objects.get_or_create(name=name.strip())
        return tag

    @staticmethod
    def add_tags_to_file(file, tag_names: List[str]) -> bool:
        """Add tags to a file by name."""
        try:
            tags = [MediaService.get_or_create_tag(name) for name in tag_names]
            file.tags.add(*tags)
            return True
        except Exception as e:
            logger.error(f"Error adding tags to file {file.id}: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # CDN PUSH
    # ────────────────────────────────────────────────────

    @staticmethod
    def push_to_cdn(file) -> bool:
        """
        Push file to CDN.
        Placeholder: integrate with your CDN provider (S3, CloudFront, Cloudflare, etc.).
        """
        try:
            # CDN push: delegates to _push_file_to_cdn_provider which reads CDN_BASE_URL
            # from settings. Configure settings.CDN_BASE_URL for your provider (S3/CloudFront/Cloudflare).
            cdn_url = MediaService._push_file_to_cdn_provider(file)
            if cdn_url:
                file.mark_cdn_pushed(cdn_url)
                logger.info(f"Pushed file {file.id} to CDN: {cdn_url}")
                return True
            return False
        except Exception as e:
            logger.error(f"CDN push failed for file {file.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def _push_file_to_cdn_provider(file) -> str:
        """
        Actual CDN upload implementation.
        Override this method with your CDN provider's SDK.
        """
        # Placeholder: return local URL
        cdn_base = getattr(settings, 'CDN_BASE_URL', '')
        if cdn_base and file.file:
            return f"{cdn_base.rstrip('/')}/{file.file.name.lstrip('/')}"
        return ''

    # ────────────────────────────────────────────────────
    # CLEANUP
    # ────────────────────────────────────────────────────

    @staticmethod
    def delete_orphaned_files(days_unused: int = 30) -> int:
        """Delete media files not used anywhere in last N days."""
        from api.cms.models_new.media import MediaUsage, MediaFile
        try:
            unused_files = MediaUsage.get_unused_files(days=days_unused)
            count = 0
            for f in unused_files:
                if MediaService.delete_file(f, hard_delete=True):
                    count += 1
            logger.info(f"Deleted {count} orphaned media files")
            return count
        except Exception as e:
            logger.error(f"Error deleting orphaned files: {e}", exc_info=True)
            return 0

    @staticmethod
    def get_storage_statistics() -> Dict[str, Any]:
        """Get media storage usage statistics."""
        from api.cms.models_new.media import MediaFile
        try:
            stats = MediaFile.objects.filter(is_active=True).aggregate(
                total_files=Count('id'),
                total_size=Sum('size_bytes'),
                image_count=Count('id', filter=Q(file_type='image')),
                video_count=Count('id', filter=Q(file_type='video')),
                document_count=Count('id', filter=Q(file_type='document')),
                audio_count=Count('id', filter=Q(file_type='audio')),
            )
            return {
                'total_files': stats['total_files'] or 0,
                'total_size_bytes': stats['total_size'] or 0,
                'total_size_human': MediaService._format_size(stats['total_size'] or 0),
                'by_type': {
                    'image': stats['image_count'] or 0,
                    'video': stats['video_count'] or 0,
                    'document': stats['document_count'] or 0,
                    'audio': stats['audio_count'] or 0,
                }
            }
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}", exc_info=True)
            return {}

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    # ────────────────────────────────────────────────────
    # USAGE TRACKING
    # ────────────────────────────────────────────────────

    @staticmethod
    def record_usage(file, used_in_type: str, used_in_id: int, field_name: str = '') -> None:
        """Record that a media file is used in an object."""
        from api.cms.models_new.media import MediaUsage
        try:
            MediaUsage.record_usage(file, used_in_type, used_in_id, field_name)
        except Exception as e:
            logger.warning(f"Error recording media usage: {e}")

    @staticmethod
    def remove_usage(file, used_in_type: str, used_in_id: int, field_name: str = '') -> None:
        """Remove a media usage record."""
        from api.cms.models_new.media import MediaUsage
        try:
            MediaUsage.remove_usage(file, used_in_type, used_in_id, field_name)
        except Exception as e:
            logger.warning(f"Error removing media usage: {e}")
