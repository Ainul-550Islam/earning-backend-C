# kyc/utils/ocr_utils.py  ── WORLD #1
"""OCR extraction utilities — provider-agnostic"""
import re
import logging

logger = logging.getLogger(__name__)


def extract_bd_nid_data(image_file, provider: str = 'tesseract') -> dict:
    """
    Extract data from Bangladesh NID card.
    Returns dict with extracted fields + confidence.
    """
    result = {
        'name_en': '', 'name_bn': '', 'nid_number': '',
        'date_of_birth': None, 'father_name': '', 'mother_name': '',
        'address': '', 'raw_text': '', 'confidence': 0.0,
        'provider': provider, 'success': False, 'error': '',
    }

    try:
        raw_text = _run_ocr(image_file, provider=provider)
        result['raw_text'] = raw_text
        result.update(_parse_nid_fields(raw_text))
        result['success'] = True
        result['confidence'] = _estimate_confidence(raw_text, result)
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"OCR extraction failed [{provider}]: {e}")

    return result


def _run_ocr(image_file, provider: str = 'tesseract') -> str:
    """Run OCR on image, return raw text."""
    if provider == 'tesseract':
        return _ocr_tesseract(image_file)
    elif provider == 'google_vision':
        return _ocr_google_vision(image_file)
    elif provider == 'aws_textract':
        return _ocr_aws_textract(image_file)
    return _ocr_tesseract(image_file)  # fallback


def _ocr_tesseract(image_file) -> str:
    """Tesseract OCR (local, free)."""
    try:
        import pytesseract
        from PIL import Image

        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file)
        # Try Bengali + English
        text = pytesseract.image_to_string(img, lang='ben+eng', config='--psm 6')
        return text.strip()
    except ImportError:
        logger.warning("pytesseract not installed")
        return ''
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return ''


def _ocr_google_vision(image_file) -> str:
    """Google Cloud Vision OCR."""
    try:
        from google.cloud import vision
        from .image_utils import image_to_base64

        client  = vision.ImageAnnotatorClient()
        content = image_to_base64(image_file)
        image   = vision.Image(content=content)
        response = client.text_detection(image=image)
        return response.full_text_annotation.text if response.full_text_annotation else ''
    except ImportError:
        logger.warning("google-cloud-vision not installed")
        return ''
    except Exception as e:
        logger.error(f"Google Vision OCR failed: {e}")
        return ''


def _ocr_aws_textract(image_file) -> str:
    """AWS Textract OCR."""
    try:
        import boto3
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        content  = image_file.read()
        client   = boto3.client('textract')
        response = client.detect_document_text(Document={'Bytes': content})
        lines    = [b['Text'] for b in response.get('Blocks', []) if b['BlockType'] == 'LINE']
        return '\n'.join(lines)
    except ImportError:
        logger.warning("boto3 not installed")
        return ''
    except Exception as e:
        logger.error(f"AWS Textract OCR failed: {e}")
        return ''


def _parse_nid_fields(text: str) -> dict:
    """Parse NID-specific fields from raw OCR text."""
    fields = {
        'name_en': '', 'name_bn': '', 'nid_number': '',
        'date_of_birth': None, 'father_name': '', 'mother_name': '', 'address': '',
    }
    if not text:
        return fields

    # NID Number — 10, 13, or 17 digits
    nid_match = re.search(r'\b(\d{10}|\d{13}|\d{17})\b', text)
    if nid_match:
        fields['nid_number'] = nid_match.group(1)

    # English name
    name_match = re.search(r'Name\s*[:\-]\s*([A-Za-z\s]+)', text, re.IGNORECASE)
    if name_match:
        fields['name_en'] = name_match.group(1).strip()

    # Bengali name (Unicode block U+0980–U+09FF)
    bn_name = re.search(r'নাম\s*[:\-]?\s*([\u0980-\u09FF\s]+)', text)
    if bn_name:
        fields['name_bn'] = bn_name.group(1).strip()

    # Date of birth
    dob_match = re.search(
        r'(?:Date of Birth|DOB|জন্ম তারিখ)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        text, re.IGNORECASE
    )
    if dob_match:
        fields['date_of_birth'] = dob_match.group(1)

    # Father / Mother
    father = re.search(r'(?:Father|পিতা)[:\s]*([A-Za-z\u0980-\u09FF\s]+)', text, re.IGNORECASE)
    if father:
        fields['father_name'] = father.group(1).strip()[:100]

    mother = re.search(r'(?:Mother|মাতা)[:\s]*([A-Za-z\u0980-\u09FF\s]+)', text, re.IGNORECASE)
    if mother:
        fields['mother_name'] = mother.group(1).strip()[:100]

    # Address
    addr = re.search(r'(?:Address|ঠিকানা)[:\s]*([A-Za-z\u0980-\u09FF\s,\-\.]+)', text, re.IGNORECASE)
    if addr:
        fields['address'] = addr.group(1).strip()[:300]

    return fields


def _estimate_confidence(raw_text: str, extracted: dict) -> float:
    """
    Estimate OCR confidence 0.0–1.0 based on how many key fields were found.
    """
    if not raw_text or len(raw_text) < 20:
        return 0.1

    key_fields = ['nid_number', 'name_en', 'name_bn', 'date_of_birth']
    found = sum(1 for f in key_fields if extracted.get(f))
    base  = found / len(key_fields)

    # Bonus if text is long (more data = better scan quality)
    length_bonus = min(0.2, len(raw_text) / 1000)

    return round(min(1.0, base + length_bonus), 4)


def normalize_dob_string(dob_str: str):
    """Parse various DOB string formats to Python date or None."""
    if not dob_str:
        return None
    from datetime import datetime
    formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d.%m.%Y']
    for fmt in formats:
        try:
            return datetime.strptime(dob_str.strip(), fmt).date()
        except ValueError:
            continue
    return None
