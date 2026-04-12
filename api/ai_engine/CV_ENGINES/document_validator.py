"""
api/ai_engine/CV_ENGINES/document_validator.py
===============================================
Document Validator — KYC document image validate করো।
"""

import logging
from .ocr_engine import OCREngine

logger = logging.getLogger(__name__)


class DocumentValidator:
    """
    KYC document validation।
    ID card, passport, driving license।
    """

    DOC_TYPES = ['national_id', 'passport', 'driving_license', 'birth_certificate']

    def validate(self, image_path: str = None, image_url: str = None,
                 doc_type: str = 'national_id') -> dict:
        ocr = OCREngine()
        ocr_result = ocr.extract_text(image_path, image_url)

        text = ocr_result.get('text', '')
        is_valid = False
        confidence = 0.0
        extracted_data = {}

        if doc_type == 'national_id':
            is_valid, extracted_data = self._validate_nid(text)
            confidence = 0.85 if is_valid else 0.3
        elif doc_type == 'passport':
            is_valid, extracted_data = self._validate_passport(text)
            confidence = 0.80 if is_valid else 0.3

        return {
            'is_valid':        is_valid,
            'doc_type':        doc_type,
            'confidence':      confidence,
            'extracted_data':  extracted_data,
            'ocr_text':        text[:500],
            'ocr_confidence':  ocr_result.get('confidence', 0.0),
        }

    def _validate_nid(self, text: str) -> tuple:
        import re
        nid_patterns = [
            r'\b\d{10}\b',   # 10-digit NID
            r'\b\d{13}\b',   # 13-digit NID
            r'\b\d{17}\b',   # 17-digit NID
        ]
        for pattern in nid_patterns:
            match = re.search(pattern, text)
            if match:
                return True, {'nid_number': match.group()}
        return False, {}

    def _validate_passport(self, text: str) -> tuple:
        import re
        match = re.search(r'[A-Z]{1,2}\d{6,9}', text)
        if match:
            return True, {'passport_number': match.group()}
        return False, {}
