# api/offer_inventory/optimization_scale/image_compressor.py
"""Image Compressor — Compress and optimize offer creative images."""
import logging

logger = logging.getLogger(__name__)

MAX_WIDTH     = 800
MAX_HEIGHT    = 600
JPEG_QUALITY  = 85
WEBP_QUALITY  = 80


class ImageCompressor:
    """Compress and optimize images for offer creatives."""

    @staticmethod
    def compress_from_url(image_url: str) -> dict:
        """Download image from URL and compress it."""
        try:
            import requests, io
            from PIL import Image
        except ImportError:
            return {'success': False, 'error': 'Pillow or requests not installed'}

        try:
            resp = requests.get(image_url, timeout=10)
            resp.raise_for_status()
            original_size = len(resp.content)

            img = Image.open(io.BytesIO(resp.content))
            # Resize if too large
            if img.width > MAX_WIDTH or img.height > MAX_HEIGHT:
                img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)
            # Convert to RGB
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')

            output = io.BytesIO()
            img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            compressed      = output.getvalue()
            compressed_size = len(compressed)
            saving_pct      = round((1 - compressed_size / max(original_size, 1)) * 100, 1)

            return {
                'success'        : True,
                'original_size'  : original_size,
                'compressed_size': compressed_size,
                'saving_pct'     : saving_pct,
                'width'          : img.width,
                'height'         : img.height,
                'data'           : compressed,
            }
        except Exception as e:
            logger.error(f'Image compress error: {e}')
            return {'success': False, 'error': str(e)}

    @staticmethod
    def compress_bytes(data: bytes, fmt: str = 'JPEG') -> bytes:
        """Compress raw image bytes."""
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            if img.width > MAX_WIDTH or img.height > MAX_HEIGHT:
                img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)
            output = io.BytesIO()
            img.save(output, format=fmt, quality=JPEG_QUALITY, optimize=True)
            return output.getvalue()
        except Exception as e:
            logger.error(f'compress_bytes error: {e}')
            return data

    @staticmethod
    def get_webp_url(original_url: str) -> str:
        """Return WebP version URL (CDN auto-convert)."""
        if not original_url:
            return original_url
        for ext in ['.jpg', '.jpeg', '.png']:
            if ext in original_url.lower():
                return original_url.rsplit('.', 1)[0] + '.webp'
        return original_url

    @staticmethod
    def estimate_savings(image_url: str) -> dict:
        """Estimate compression savings without actually compressing."""
        try:
            import requests
            resp = requests.head(image_url, timeout=5)
            size = int(resp.headers.get('content-length', 0))
            if size:
                est_compressed = int(size * 0.6)
                return {
                    'original_bytes'  : size,
                    'estimated_bytes' : est_compressed,
                    'estimated_saving': round((1 - est_compressed / size) * 100, 1),
                }
        except Exception:
            pass
        return {}
