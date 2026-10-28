# api/cms/services/MediaVariantService.py
"""
MediaVariantService: Generate thumbnail/medium/large/webp variants for images.
"""
import os
import logging
from typing import List, Dict, Optional, Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class MediaVariantService:
    """Generate image variants for media files."""

    VARIANT_CONFIGS = {
        'thumb': {'width': 150, 'height': 150, 'quality': 80, 'format': 'WEBP'},
        'medium': {'width': 600, 'height': 400, 'quality': 85, 'format': 'WEBP'},
        'large': {'width': 1200, 'height': 800, 'quality': 90, 'format': 'WEBP'},
        'webp': {'width': 1200, 'height': 800, 'quality': 90, 'format': 'WEBP'},
        'og': {'width': 1200, 'height': 630, 'quality': 90, 'format': 'WEBP'},
        'mobile': {'width': 480, 'height': 320, 'quality': 80, 'format': 'WEBP'},
    }

    @classmethod
    def generate_all_variants(cls, media_file) -> Dict[str, bool]:
        """
        Generate all configured variants for an image file.

        Args:
            media_file: MediaFile instance

        Returns:
            Dict of {variant_type: success}
        """
        results = {}
        if media_file.file_type != 'image':
            logger.warning(f"Cannot generate variants for non-image file {media_file.id}")
            return results

        for variant_type in cls.VARIANT_CONFIGS.keys():
            results[variant_type] = cls.generate_variant(media_file, variant_type)

        return results

    @classmethod
    def generate_variant(cls, media_file, variant_type: str) -> bool:
        """
        Generate a specific variant for an image file.

        Args:
            media_file: MediaFile instance
            variant_type: One of 'thumb', 'medium', 'large', 'webp', 'og', 'mobile'

        Returns:
            True on success
        """
        from api.cms.models_new.media import MediaVariant
        if variant_type not in cls.VARIANT_CONFIGS:
            logger.warning(f"Unknown variant type: {variant_type}")
            return False

        config = cls.VARIANT_CONFIGS[variant_type]

        try:
            with transaction.atomic():
                # Try to use Pillow for resizing
                variant_path, width, height, size = cls._resize_image(
                    media_file, config['width'], config['height'],
                    config['quality'], config['format']
                )
                if not variant_path:
                    return False

                # Save or update variant
                MediaVariant.objects.update_or_create(
                    file=media_file,
                    variant_type=variant_type,
                    defaults={
                        'file_path': variant_path,
                        'width': width,
                        'height': height,
                        'size_bytes': size,
                        'mime_type': 'image/webp',
                        'is_active': True,
                    }
                )
                logger.info(f"Generated {variant_type} variant for file {media_file.id}")
                return True
        except Exception as e:
            logger.error(f"Error generating {variant_type} variant for file {media_file.id}: {e}", exc_info=True)
            return False

    @classmethod
    def _resize_image(cls, media_file, width: int, height: int, quality: int, fmt: str):
        """
        Resize image using Pillow.

        Returns:
            Tuple (file_path, actual_width, actual_height, size_bytes) or (None, 0, 0, 0)
        """
        try:
            from PIL import Image
            import io
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage

            # Open original image
            with media_file.file.open('rb') as f:
                img = Image.open(f)
                img.load()

            # Convert to RGBA if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Resize with aspect ratio preservation
            img.thumbnail((width, height), Image.LANCZOS)
            actual_w, actual_h = img.size

            # Save to bytes
            output = io.BytesIO()
            img.save(output, format=fmt, quality=quality, optimize=True)
            output.seek(0)
            size_bytes = len(output.getvalue())

            # Build variant path
            base_name = os.path.splitext(os.path.basename(media_file.file.name))[0]
            variant_dir = os.path.join('media', 'variants', str(media_file.uuid))
            variant_filename = f"{base_name}_{width}x{height}.webp"
            variant_path = os.path.join(variant_dir, variant_filename)

            # Save to storage
            saved_path = default_storage.save(variant_path, ContentFile(output.read()))
            return saved_path, actual_w, actual_h, size_bytes

        except ImportError:
            logger.warning("Pillow not installed. Cannot generate image variants.")
            return None, 0, 0, 0
        except Exception as e:
            logger.error(f"Image resize error: {e}", exc_info=True)
            return None, 0, 0, 0

    @classmethod
    def delete_variants(cls, media_file) -> int:
        """Delete all variants for a media file."""
        from api.cms.models_new.media import MediaVariant
        deleted, _ = MediaVariant.objects.filter(file=media_file).delete()
        return deleted

    @classmethod
    def regenerate_missing_variants(cls) -> Dict[str, int]:
        """Regenerate variants that are missing for all image files."""
        from api.cms.models_new.media import MediaFile, MediaVariant
        stats = {'processed': 0, 'generated': 0, 'errors': 0}
        image_files = MediaFile.objects.filter(file_type='image', is_active=True)
        for media_file in image_files:
            stats['processed'] += 1
            existing_types = set(
                MediaVariant.objects.filter(file=media_file).values_list('variant_type', flat=True)
            )
            missing_types = set(cls.VARIANT_CONFIGS.keys()) - existing_types
            for variant_type in missing_types:
                if cls.generate_variant(media_file, variant_type):
                    stats['generated'] += 1
                else:
                    stats['errors'] += 1
        return stats
