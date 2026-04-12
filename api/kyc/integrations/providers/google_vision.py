# kyc/integrations/providers/google_vision.py  ── WORLD #1
"""
Google Cloud Vision API — Real OCR integration.
Setup: pip install google-cloud-vision
Credentials: GOOGLE_APPLICATION_CREDENTIALS env var OR service account JSON.

Free tier: 1,000 units/month. Paid: ~$1.50/1,000 units.
"""
import logging
import base64
import time

logger = logging.getLogger(__name__)


class GoogleVisionOCR:
    """
    Google Cloud Vision OCR provider.
    Extracts text from NID, Passport, Driving License images.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import vision
                self._client = vision.ImageAnnotatorClient()
            except ImportError:
                raise ImportError(
                    "google-cloud-vision not installed.\n"
                    "Run: pip install google-cloud-vision"
                )
        return self._client

    def extract_text(self, image_file) -> dict:
        """
        Extract all text from image.
        Returns: {raw_text, confidence, blocks, error}
        """
        start = time.time()
        result = {
            'raw_text':      '',
            'confidence':    0.0,
            'blocks':        [],
            'provider':      'google_vision',
            'processing_ms': 0,
            'error':         '',
            'success':       False,
        }

        try:
            from google.cloud import vision

            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            content = image_file.read()

            client   = self._get_client()
            image    = vision.Image(content=content)

            # Full document text detection (better for IDs than TEXT_DETECTION)
            response = client.document_text_detection(image=image)

            if response.error.message:
                result['error'] = response.error.message
                return result

            full_text = response.full_text_annotation
            if not full_text:
                result['error'] = 'No text detected'
                return result

            result['raw_text'] = full_text.text

            # Confidence from pages
            confidences = []
            blocks_data = []
            for page in full_text.pages:
                for block in page.blocks:
                    block_conf = block.confidence
                    confidences.append(block_conf)
                    block_text = ' '.join(
                        ' '.join(word.text for word in para.words)
                        for para in block.paragraphs
                        for word in para.words
                    )
                    if block_text.strip():
                        blocks_data.append({
                            'text':       block_text.strip(),
                            'confidence': round(block_conf, 4),
                            'type':       str(block.block_type),
                        })

            result['confidence'] = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
            result['blocks']     = blocks_data
            result['success']    = True

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Google Vision OCR error: {e}")

        finally:
            result['processing_ms'] = int((time.time() - start) * 1000)
            if hasattr(image_file, 'seek'):
                image_file.seek(0)

        return result

    def detect_document_type(self, image_file) -> str:
        """
        Auto-detect document type from image.
        Returns: 'nid' | 'passport' | 'driving_license' | 'unknown'
        """
        result = self.extract_text(image_file)
        text   = result.get('raw_text', '').lower()

        if any(kw in text for kw in ['national id', 'জাতীয় পরিচয়পত্র', 'nid']):
            return 'nid'
        if any(kw in text for kw in ['passport', 'পাসপোর্ট']):
            return 'passport'
        if any(kw in text for kw in ['driving', 'license', 'licence', 'ড্রাইভিং']):
            return 'driving_license'
        return 'unknown'

    def extract_nid_fields(self, image_file) -> dict:
        """
        Extract NID-specific fields using Vision API.
        Combines raw OCR with regex parsing.
        """
        ocr_result = self.extract_text(image_file)
        raw_text   = ocr_result.get('raw_text', '')

        from kyc.utils.ocr_utils import _parse_nid_fields, _estimate_confidence
        fields = _parse_nid_fields(raw_text)
        fields['confidence']    = ocr_result['confidence']
        fields['raw_text']      = raw_text
        fields['provider']      = 'google_vision'
        fields['processing_ms'] = ocr_result['processing_ms']
        fields['success']       = ocr_result['success']
        fields['error']         = ocr_result['error']
        return fields
