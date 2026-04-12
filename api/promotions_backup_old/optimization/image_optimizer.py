# =============================================================================
# api/promotions/optimization/image_optimizer.py
# Image Optimization — Upload এর সময় auto compress, resize, WebP convert
# Proof screenshot, ad creative, profile photo সবকিছু optimize করে
# =============================================================================

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('optimization.image')

# Config — settings.py তে override করা যাবে
IMG_MAX_WIDTH        = getattr(settings, 'IMG_MAX_WIDTH',        1920)
IMG_MAX_HEIGHT       = getattr(settings, 'IMG_MAX_HEIGHT',       1080)
IMG_QUALITY_WEBP     = getattr(settings, 'IMG_QUALITY_WEBP',     82)
IMG_QUALITY_JPEG     = getattr(settings, 'IMG_QUALITY_JPEG',     85)
IMG_THUMB_SIZE       = getattr(settings, 'IMG_THUMB_SIZE',       (400, 300))
IMG_MAX_SIZE_BYTES   = getattr(settings, 'IMG_MAX_SIZE_BYTES',   5 * 1024 * 1024)  # 5MB
CACHE_PREFIX_IMGOPT  = 'opt:img:{}'
CACHE_TTL_IMGOPT     = 3600 * 24


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class OptimizationResult:
    original_size_bytes:  int
    optimized_size_bytes: int
    savings_percent:      float
    original_format:      str
    output_format:        str
    original_dimensions:  tuple
    output_dimensions:    tuple
    output_bytes:         bytes
    thumbnail_bytes:      Optional[bytes]
    processing_ms:        float
    operations_applied:   list[str]


# =============================================================================
# ── IMAGE OPTIMIZER ───────────────────────────────────────────────────────────
# =============================================================================

class ImageOptimizer:
    """
    Pillow দিয়ে image optimize করে।

    Operations:
    1. Resize — max dimension enforce
    2. Format convert — WebP (best compression) বা JPEG
    3. Quality reduce — progressive JPEG
    4. Metadata strip — EXIF data remove (privacy + size)
    5. Thumbnail generate — lazy loading এর জন্য
    6. Progressive encode — browser এ faster load

    Usage:
        optimizer = ImageOptimizer()
        result    = optimizer.optimize(image_bytes)
        # result.output_bytes save করুন storage তে
    """

    def optimize(
        self,
        image_bytes:      bytes,
        max_width:        int  = None,
        max_height:       int  = None,
        output_format:    str  = 'webp',   # 'webp', 'jpeg', 'png', 'auto'
        generate_thumb:   bool = True,
        strip_metadata:   bool = True,
    ) -> OptimizationResult:
        """
        Image optimize করে।

        Args:
            image_bytes:   Raw image bytes
            max_width:     Maximum width (default: IMG_MAX_WIDTH from settings)
            max_height:    Maximum height (default: IMG_MAX_HEIGHT from settings)
            output_format: Target format ('webp' recommended)
            generate_thumb: Thumbnail generate করবে কিনা
            strip_metadata: EXIF data remove করবে কিনা
        """
        import time
        start = time.monotonic()

        max_w = max_width  or IMG_MAX_WIDTH
        max_h = max_height or IMG_MAX_HEIGHT
        ops   = []

        try:
            from PIL import Image, ImageOps, ExifTags
            import io as _io

            # ── Load ──────────────────────────────────────────────────────
            img  = Image.open(_io.BytesIO(image_bytes))
            orig_format = img.format or 'UNKNOWN'
            orig_dims   = img.size   # (width, height)
            orig_size   = len(image_bytes)

            # ── EXIF rotation fix ─────────────────────────────────────────
            try:
                img = ImageOps.exif_transpose(img)
                ops.append('exif_rotate')
            except Exception:
                pass

            # ── Strip metadata ────────────────────────────────────────────
            if strip_metadata:
                # Convert to strip EXIF (create new image without metadata)
                data = list(img.getdata())
                clean = Image.new(img.mode, img.size)
                clean.putdata(data)
                img  = clean
                ops.append('strip_metadata')

            # ── Convert RGBA/P to RGB for JPEG/WebP ───────────────────────
            if img.mode in ('RGBA', 'P', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
                ops.append('rgba_to_rgb')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                ops.append(f'convert_to_rgb')

            # ── Resize ────────────────────────────────────────────────────
            w, h = img.size
            if w > max_w or h > max_h:
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                ops.append(f'resize:{w}x{h}→{img.size[0]}x{img.size[1]}')

            final_dims = img.size

            # ── Format selection ──────────────────────────────────────────
            fmt = self._select_format(output_format, orig_format, img)
            ops.append(f'format:{orig_format}→{fmt}')

            # ── Encode ────────────────────────────────────────────────────
            out_buf = _io.BytesIO()
            save_kwargs = self._get_save_kwargs(fmt, img)
            img.save(out_buf, format=fmt, **save_kwargs)
            out_bytes   = out_buf.getvalue()

            # ── If output is larger than input, keep original ─────────────
            if len(out_bytes) > orig_size * 0.95 and fmt == orig_format.upper():
                out_bytes = image_bytes
                ops.append('kept_original_smaller')

            # ── Thumbnail ─────────────────────────────────────────────────
            thumb_bytes = None
            if generate_thumb:
                thumb_bytes = self._generate_thumbnail(img)
                if thumb_bytes:
                    ops.append(f'thumbnail:{IMG_THUMB_SIZE[0]}x{IMG_THUMB_SIZE[1]}')

            elapsed  = round((time.monotonic() - start) * 1000, 2)
            savings  = round((1 - len(out_bytes) / max(orig_size, 1)) * 100, 1)

            logger.info(
                f'Image optimized: {orig_size/1024:.1f}KB → {len(out_bytes)/1024:.1f}KB '
                f'({savings}% saved), format={fmt}, ops={ops}, time={elapsed}ms'
            )

            return OptimizationResult(
                original_size_bytes  = orig_size,
                optimized_size_bytes = len(out_bytes),
                savings_percent      = savings,
                original_format      = orig_format,
                output_format        = fmt,
                original_dimensions  = orig_dims,
                output_dimensions    = final_dims,
                output_bytes         = out_bytes,
                thumbnail_bytes      = thumb_bytes,
                processing_ms        = elapsed,
                operations_applied   = ops,
            )

        except ImportError:
            raise RuntimeError('Pillow required: pip install Pillow')
        except Exception as e:
            logger.exception(f'Image optimization failed: {e}')
            # Fail gracefully — original bytes return করো
            return OptimizationResult(
                original_size_bytes=len(image_bytes), optimized_size_bytes=len(image_bytes),
                savings_percent=0.0, original_format='unknown', output_format='unknown',
                original_dimensions=(0, 0), output_dimensions=(0, 0),
                output_bytes=image_bytes, thumbnail_bytes=None,
                processing_ms=0.0, operations_applied=['failed_kept_original'],
            )

    def optimize_url(self, url: str, **kwargs) -> OptimizationResult:
        """URL থেকে image download করে optimize করে।"""
        import requests
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return self.optimize(r.content, **kwargs)

    def batch_optimize(self, images: list[dict]) -> list[OptimizationResult]:
        """
        Multiple images একসাথে optimize করে।

        Args:
            images: [{'bytes': b'...', 'format': 'webp'}, ...]
        """
        results = []
        for img_config in images:
            try:
                result = self.optimize(
                    img_config['bytes'],
                    output_format=img_config.get('format', 'webp'),
                )
                results.append(result)
            except Exception as e:
                logger.error(f'Batch optimize failed for one image: {e}')
        return results

    def optimize_and_save(
        self,
        image_bytes:  bytes,
        storage_path: str,
        **kwargs,
    ) -> dict:
        """
        Optimize করে Django storage তে save করে।

        Returns:
            dict: {main_path, thumb_path, savings_percent, format}
        """
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        result = self.optimize(image_bytes, **kwargs)

        # Main image save
        ext       = result.output_format.lower()
        main_path = f'{storage_path}.{ext}'
        default_storage.save(main_path, ContentFile(result.output_bytes))

        # Thumbnail save
        thumb_path = None
        if result.thumbnail_bytes:
            thumb_path = f'{storage_path}_thumb.{ext}'
            default_storage.save(thumb_path, ContentFile(result.thumbnail_bytes))

        return {
            'main_path':      main_path,
            'thumb_path':     thumb_path,
            'savings_percent': result.savings_percent,
            'format':         result.output_format,
            'dimensions':     result.output_dimensions,
            'size_bytes':     result.optimized_size_bytes,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _select_format(self, requested: str, original: str, img) -> str:
        """Best output format select করে।"""
        if requested == 'auto':
            # PNG → WebP (lossy ok), JPEG → WebP, GIF → keep GIF (animation)
            if original and original.upper() == 'GIF':
                return 'GIF'
            return 'WEBP'
        fmt_map = {'webp': 'WEBP', 'jpeg': 'JPEG', 'jpg': 'JPEG', 'png': 'PNG'}
        return fmt_map.get(requested.lower(), 'WEBP')

    def _get_save_kwargs(self, fmt: str, img) -> dict:
        """Format অনুযায়ী save parameters।"""
        if fmt == 'WEBP':
            return {'quality': IMG_QUALITY_WEBP, 'method': 4, 'optimize': True}
        if fmt == 'JPEG':
            return {'quality': IMG_QUALITY_JPEG, 'optimize': True, 'progressive': True}
        if fmt == 'PNG':
            return {'optimize': True, 'compress_level': 7}
        return {}

    def _generate_thumbnail(self, img) -> Optional[bytes]:
        """Thumbnail generate করে।"""
        try:
            from PIL import Image
            import io as _io
            thumb = img.copy()
            thumb.thumbnail(IMG_THUMB_SIZE, Image.LANCZOS)
            buf = _io.BytesIO()
            thumb.save(buf, format='WEBP', quality=70, method=2)
            return buf.getvalue()
        except Exception as e:
            logger.debug(f'Thumbnail generation failed: {e}')
            return None


# =============================================================================
# ── DJANGO SIGNAL INTEGRATION ─────────────────────────────────────────────────
# =============================================================================

def auto_optimize_on_upload(sender, instance, **kwargs):
    """
    Django signal দিয়ে upload এর সময় auto optimize।

    Usage in models.py:
        from django.db.models.signals import pre_save
        from .optimization.image_optimizer import auto_optimize_on_upload
        pre_save.connect(auto_optimize_on_upload, sender=AdCreative)
    """
    image_fields = ['image', 'thumbnail', 'banner', 'proof_file']
    optimizer    = ImageOptimizer()

    for field_name in image_fields:
        field_file = getattr(instance, field_name, None)
        if not field_file or not hasattr(field_file, 'read'):
            continue
        try:
            field_file.seek(0)
            original_bytes = field_file.read()
            if len(original_bytes) > 10 * 1024:  # 10KB এর বেশি হলেই optimize
                result = optimizer.optimize(original_bytes)
                if result.savings_percent > 5:   # কমপক্ষে ৫% save হলেই replace
                    field_file.seek(0)
                    field_file.write(result.output_bytes)
                    field_file.truncate()
        except Exception as e:
            logger.warning(f'Auto-optimize failed for {field_name}: {e}')
