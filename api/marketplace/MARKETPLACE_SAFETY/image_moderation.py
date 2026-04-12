"""
MARKETPLACE_SAFETY/image_moderation.py — Product Image Moderation
"""
import logging
import os
from PIL import Image as PILImage
import io

logger = logging.getLogger(__name__)

MAX_WIDTH  = 3000
MAX_HEIGHT = 3000
MIN_WIDTH  = 200
MIN_HEIGHT = 200
MAX_SIZE_MB= 10
ALLOWED_FORMATS = {"JPEG","PNG","WEBP","GIF"}


def validate_product_image(image_file) -> dict:
    """
    Validate an uploaded product image.
    Returns {"valid": bool, "errors": list, "warnings": list}
    """
    errors, warnings = [], []

    # Size check
    size_mb = image_file.size / 1024 / 1024
    if size_mb > MAX_SIZE_MB:
        errors.append(f"File too large: {size_mb:.1f}MB (max {MAX_SIZE_MB}MB)")

    # Extension check
    ext = os.path.splitext(image_file.name)[1].upper().replace(".", "")
    if ext == "JPG":
        ext = "JPEG"
    if ext not in ALLOWED_FORMATS:
        errors.append(f"Invalid format: {ext}. Allowed: {ALLOWED_FORMATS}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Read image
    try:
        content = image_file.read()
        image_file.seek(0)
        img = PILImage.open(io.BytesIO(content))
        w, h = img.size

        if img.format not in ALLOWED_FORMATS:
            errors.append(f"Invalid image format: {img.format}")

        if w < MIN_WIDTH or h < MIN_HEIGHT:
            warnings.append(f"Image too small ({w}x{h}). Recommended: {MIN_WIDTH}x{MIN_HEIGHT}+")

        if w > MAX_WIDTH or h > MAX_HEIGHT:
            warnings.append(f"Image very large ({w}x{h}). Will be resized.")

        # Check for placeholder/blank images (mostly white or mostly black)
        if img.mode in ("RGB","RGBA"):
            pixels = list(img.getdata())[:1000]
            avg_brightness = sum(sum(p[:3])/3 for p in pixels) / len(pixels)
            if avg_brightness > 250:
                warnings.append("Image appears to be mostly white (possible placeholder)")
            elif avg_brightness < 5:
                warnings.append("Image appears to be mostly black")

    except Exception as e:
        errors.append(f"Cannot read image: {str(e)}")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def resize_product_image(image_content: bytes, max_dimension: int = 1200) -> bytes:
    """Resize image to max dimension while maintaining aspect ratio."""
    try:
        img = PILImage.open(io.BytesIO(image_content))
        if img.format == "GIF":
            return image_content  # don't resize GIFs

        img.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error("[ImageMod] Resize failed: %s", e)
        return image_content


def is_image_safe(image_content: bytes) -> dict:
    """
    Basic safety check. For production, integrate AWS Rekognition or Google Vision API.
    """
    # Placeholder — in production, call an AI moderation API
    return {
        "safe":        True,
        "confidence":  1.0,
        "flags":       [],
        "note":        "Configure AWS Rekognition or Google Cloud Vision for AI moderation",
    }
