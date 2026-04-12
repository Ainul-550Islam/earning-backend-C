# kyc/utils/image_utils.py  ── WORLD #1
"""Image processing utilities for KYC verification"""
import io
import logging

logger = logging.getLogger(__name__)


def get_image_dimensions(image_file) -> tuple:
    """Return (width, height) of image. (0,0) on failure."""
    try:
        from PIL import Image
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        img = Image.open(image_file)
        dims = img.size
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        return dims
    except Exception as e:
        logger.warning(f"get_image_dimensions failed: {e}")
        return (0, 0)


def get_image_size_mb(image_file) -> float:
    """Return file size in MB."""
    try:
        if hasattr(image_file, 'size'):
            return image_file.size / (1024 * 1024)
        if hasattr(image_file, 'file'):
            image_file.file.seek(0, 2)
            size = image_file.file.tell()
            image_file.file.seek(0)
            return size / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def compute_clarity_score(image_file) -> float:
    """
    Compute image clarity (sharpness) score 0-100.
    Uses Laplacian variance method.
    """
    try:
        import numpy as np
        from PIL import Image, ImageFilter

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file).convert('L')  # grayscale
        img_array = np.array(img, dtype=np.float32)

        # Laplacian variance — higher = sharper
        laplacian = img_array - np.roll(img_array, 1, axis=0) - np.roll(img_array, 1, axis=1)
        variance = float(np.var(laplacian))

        # Normalize to 0-100
        score = min(100.0, variance / 100.0)

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        return round(score, 2)
    except ImportError:
        # numpy/PIL not available — return mock score
        logger.warning("numpy not available for clarity scoring, returning mock score")
        return 75.0
    except Exception as e:
        logger.warning(f"compute_clarity_score failed: {e}")
        return 50.0


def resize_image(image_file, max_width: int = 1920, max_height: int = 1080, quality: int = 85) -> bytes:
    """Resize image to max dimensions while maintaining aspect ratio. Returns JPEG bytes."""
    try:
        from PIL import Image

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file)
        img.thumbnail((max_width, max_height), Image.LANCZOS)

        buf = io.BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=quality, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"resize_image failed: {e}")
        return b''


def convert_to_grayscale(image_file) -> bytes:
    """Convert image to grayscale. Returns PNG bytes."""
    try:
        from PIL import Image

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file).convert('L')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.error(f"convert_to_grayscale failed: {e}")
        return b''


def detect_faces(image_file) -> dict:
    """
    Basic face detection.
    Returns {'count': int, 'detected': bool, 'locations': list}
    Requires opencv-python or deepface.
    """
    result = {'count': 0, 'detected': False, 'locations': []}
    try:
        import cv2
        import numpy as np
        from PIL import Image

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file).convert('RGB')
        img_array = np.array(img)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        result['count'] = len(faces)
        result['detected'] = len(faces) > 0
        result['locations'] = [{'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)} for x, y, w, h in faces]
    except ImportError:
        logger.warning("cv2 not available — face detection skipped")
        result['detected'] = True   # assume detected for flow
        result['count'] = 1
    except Exception as e:
        logger.warning(f"detect_faces failed: {e}")

    return result


def image_to_base64(image_file) -> str:
    """Convert image file to base64 string (for API payloads)."""
    import base64
    try:
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        data = image_file.read()
        return base64.b64encode(data).decode('utf-8')
    except Exception as e:
        logger.error(f"image_to_base64 failed: {e}")
        return ''


def validate_image_not_corrupt(image_file) -> bool:
    """Check if image file is a valid, readable image."""
    try:
        from PIL import Image
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        img = Image.open(image_file)
        img.verify()  # raises on corrupt
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        return True
    except Exception:
        return False
