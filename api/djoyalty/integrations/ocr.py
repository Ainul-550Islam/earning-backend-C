# api/djoyalty/integrations/ocr.py
"""
OCR Integration -- Receipt scanning (Fetch Rewards style)।
Google Cloud Vision API + Tesseract fallback।

2025: AI-generated receipt fraud spike -- built-in fraud detection।

Settings:
    GOOGLE_APPLICATION_CREDENTIALS = '/path/to/credentials.json'
    OR
    DJOYALTY_GOOGLE_VISION_API_KEY = 'AIza...'

pip install google-cloud-vision  # for Cloud Vision
pip install pytesseract Pillow    # for Tesseract fallback
"""
import base64
import hashlib
import logging
import re
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleVisionOCR:
    """
    Google Cloud Vision OCR -- receipt text extraction।
    Best accuracy for printed receipts।
    """

    def __init__(self):
        self.api_key = getattr(settings, 'DJOYALTY_GOOGLE_VISION_API_KEY', '')
        self.base_url = 'https://vision.googleapis.com/v1/images:annotate'

    def extract_text_from_url(self, image_url: str) -> str:
        """Image URL থেকে text extract করো।"""
        payload = {
            'requests': [{
                'image': {'source': {'imageUri': image_url}},
                'features': [{'type': 'DOCUMENT_TEXT_DETECTION', 'maxResults': 1}],
            }]
        }
        resp = requests.post(
            f'{self.base_url}?key={self.api_key}',
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        try:
            return data['responses'][0]['fullTextAnnotation']['text']
        except (KeyError, IndexError):
            return ''

    def extract_text_from_base64(self, image_b64: str) -> str:
        """Base64 image থেকে text extract করো।"""
        payload = {
            'requests': [{
                'image': {'content': image_b64},
                'features': [{'type': 'DOCUMENT_TEXT_DETECTION', 'maxResults': 1}],
            }]
        }
        resp = requests.post(
            f'{self.base_url}?key={self.api_key}',
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            return data['responses'][0]['fullTextAnnotation']['text']
        except (KeyError, IndexError):
            return ''

    @staticmethod
    def is_configured() -> bool:
        import os
        return bool(
            getattr(settings, 'DJOYALTY_GOOGLE_VISION_API_KEY', '') or
            os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )


class TesseractOCR:
    """
    Tesseract OCR -- free/offline fallback।
    pip install pytesseract Pillow
    sudo apt-get install tesseract-ocr tesseract-ocr-ben (for Bengali)
    """

    def extract_text_from_file(self, image_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='eng+ben')
            return text
        except ImportError:
            logger.warning('TesseractOCR: pytesseract not installed')
            return ''
        except Exception as e:
            logger.error('TesseractOCR error: %s', e)
            return ''

    @staticmethod
    def is_configured() -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False


class ReceiptParser:
    """
    OCR text থেকে receipt data parse করো।
    merchant name, total amount, date extract করে।
    + AI fraud detection (AI-generated receipt detection)।
    """

    # Known Bangladesh merchants
    BD_MERCHANTS = [
        'Shajgoj', 'Chaldal', 'Pathao', 'Shohoz', 'Daraz',
        'Meena Bazar', 'Agora', 'Shwapno', 'PriyoShop',
        'Amar Desh', 'Grameenphone', 'Banglalink', 'Robi',
        'Khaas Food', 'Foodpanda', 'Shohoz Food',
    ]

    TOTAL_PATTERNS = [
        r'(?:total|grand total|bill total|amount due|মোট|সর্বমোট)[:\s]*(?:tk\.?|bdt\.?|৳)?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
        r'(?:tk\.?|bdt\.?|৳)\s*([0-9,]+(?:\.[0-9]{1,2})?)',
        r'([0-9,]+\.[0-9]{2})\s*(?:tk|bdt|taka)',
    ]

    DATE_PATTERNS = [
        r'(\d{2}[/-]\d{2}[/-]\d{4})',
        r'(\d{4}[/-]\d{2}[/-]\d{2})',
        r'(\d{2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',
    ]

    @classmethod
    def parse(cls, raw_text: str) -> dict:
        """OCR text parse করো -> structured receipt data।"""
        text_lower = raw_text.lower()
        result = {
            'raw_text': raw_text,
            'merchant_name': cls._extract_merchant(raw_text),
            'total_amount': cls._extract_total(raw_text),
            'purchase_date': cls._extract_date(raw_text),
            'items': cls._extract_items(raw_text),
            'fraud_score': cls._compute_fraud_score(raw_text),
            'is_ai_generated': cls._detect_ai_generated(raw_text),
        }
        return result

    @classmethod
    def _extract_merchant(cls, text: str) -> str:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # First non-empty line usually has merchant name
        for line in lines[:3]:
            if len(line) > 3 and not re.match(r'^[\d\s]+$', line):
                # Check if it matches known merchants
                for merchant in cls.BD_MERCHANTS:
                    if merchant.lower() in line.lower():
                        return merchant
                return line[:100]
        return ''

    @classmethod
    def _extract_total(cls, text: str):
        text_lower = text.lower()
        for pattern in cls.TOTAL_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return Decimal(amount_str)
                except InvalidOperation:
                    continue
        return None

    @classmethod
    def _extract_date(cls, text: str):
        from datetime import datetime
        for pattern in cls.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                for fmt in ('%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%Y-%m-%d'):
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
        return None

    @classmethod
    def _extract_items(cls, text: str) -> list:
        items = []
        lines = text.split('\n')
        item_pattern = re.compile(
            r'^(.+?)\s+(\d+)\s*[xX*]\s*([0-9.]+)\s*=?\s*([0-9.]+)?$'
        )
        for line in lines:
            match = item_pattern.match(line.strip())
            if match:
                items.append({
                    'name': match.group(1).strip(),
                    'qty': int(match.group(2)),
                    'unit_price': float(match.group(3)),
                    'total': float(match.group(4)) if match.group(4) else None,
                })
            if len(items) >= 20:
                break
        return items

    @classmethod
    def _compute_fraud_score(cls, text: str) -> Decimal:
        """
        Receipt fraud scoring।
        2025: AI-generated receipt fraud spike।
        """
        score = Decimal('0')
        text_lower = text.lower()

        # Very short text
        if len(text) < 50:
            score += Decimal('0.3')

        # No numbers at all
        if not re.search(r'\d{3,}', text):
            score += Decimal('0.2')

        # Suspicious patterns
        suspicious = ['lorem ipsum', 'sample', 'test receipt', 'demo', 'fake']
        if any(s in text_lower for s in suspicious):
            score += Decimal('0.8')

        # No date found
        if not cls._extract_date(text):
            score += Decimal('0.1')

        # No total found
        if not cls._extract_total(text):
            score += Decimal('0.15')

        # Too perfect formatting (AI-generated tends to be too clean)
        lines = [l for l in text.split('\n') if l.strip()]
        if len(lines) > 5:
            line_lengths = [len(l) for l in lines]
            avg = sum(line_lengths) / len(line_lengths)
            variance = sum((l - avg) ** 2 for l in line_lengths) / len(line_lengths)
            if variance < 5:  # Suspiciously uniform
                score += Decimal('0.2')

        return min(score, Decimal('1.0'))

    @classmethod
    def _detect_ai_generated(cls, text: str) -> bool:
        """AI-generated receipt detect করো।"""
        score = cls._compute_fraud_score(text)
        return score > Decimal('0.6')


class OCRService:
    """
    Unified OCR service।
    Auto-selects Google Vision -> Tesseract fallback।
    """

    @classmethod
    def process_receipt(cls, image_url: str) -> dict:
        """
        Receipt image process করো।
        Returns parsed receipt data।
        """
        raw_text = ''

        # Try Google Vision first
        if GoogleVisionOCR.is_configured():
            try:
                ocr = GoogleVisionOCR()
                raw_text = ocr.extract_text_from_url(image_url)
                logger.info('OCRService: text extracted via Google Vision (%d chars)', len(raw_text))
            except Exception as e:
                logger.error('OCRService Google Vision error: %s', e)

        # Tesseract fallback for local files
        if not raw_text and TesseractOCR.is_configured():
            try:
                ocr = TesseractOCR()
                if not image_url.startswith('http'):
                    raw_text = ocr.extract_text_from_file(image_url)
            except Exception as e:
                logger.error('OCRService Tesseract error: %s', e)

        if not raw_text:
            return {
                'raw_text': '',
                'merchant_name': '',
                'total_amount': None,
                'purchase_date': None,
                'items': [],
                'fraud_score': Decimal('0.5'),
                'is_ai_generated': False,
                'error': 'OCR extraction failed',
            }

        return ReceiptParser.parse(raw_text)
