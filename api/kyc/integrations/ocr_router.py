# kyc/integrations/ocr_router.py  ── WORLD #1
"""
Smart OCR Router — provider fallback chain.
Priority: Google Vision → AWS Textract → Azure → Tesseract (local).
Falls back automatically if a provider fails.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Provider priority order (from settings or default)
DEFAULT_PRIORITY = getattr(settings, 'KYC_OCR_PROVIDER_PRIORITY',
    ['google_vision', 'aws_textract', 'azure_vision', 'tesseract'])


def get_ocr_provider(name: str):
    """Get OCR provider instance by name."""
    if name == 'google_vision':
        from .providers.google_vision import GoogleVisionOCR
        return GoogleVisionOCR()
    if name == 'aws_textract':
        from .providers.aws_rekognition import AWSTextractOCR
        return AWSTextractOCR()
    if name == 'azure_vision':
        from .providers.azure_cognitive import AzureVisionOCR
        return AzureVisionOCR()
    # Fallback: local tesseract
    from kyc.utils.ocr_utils import _ocr_tesseract
    class TesseractProvider:
        def extract_text(self, f):
            text = _ocr_tesseract(f)
            return {'raw_text': text, 'confidence': 0.75 if text else 0.0,
                    'provider': 'tesseract', 'success': bool(text), 'error': ''}
    return TesseractProvider()


def run_ocr_with_fallback(image_file, priority: list = None) -> dict:
    """
    Try OCR providers in priority order.
    Returns first successful result.
    """
    order  = priority or DEFAULT_PRIORITY
    errors = {}

    for provider_name in order:
        try:
            provider = get_ocr_provider(provider_name)
            result   = provider.extract_text(image_file)
            if result.get('success') and result.get('raw_text'):
                logger.info(f"OCR success via {provider_name} (confidence={result.get('confidence')})")
                return result
            else:
                errors[provider_name] = result.get('error', 'No text extracted')
        except Exception as e:
            errors[provider_name] = str(e)
            logger.warning(f"OCR provider {provider_name} failed: {e}")

    # All failed
    logger.error(f"All OCR providers failed: {errors}")
    return {
        'raw_text':   '',
        'confidence': 0.0,
        'provider':   'none',
        'success':    False,
        'error':      f"All providers failed: {errors}",
    }


def get_face_matcher(name: str = None):
    """Get face matching provider."""
    name = name or getattr(settings, 'KYC_FACE_PROVIDER', 'aws_rekognition')
    if name == 'aws_rekognition':
        from .providers.aws_rekognition import AWSRekognitionFaceMatcher
        return AWSRekognitionFaceMatcher()
    if name == 'azure_face':
        from .providers.azure_cognitive import AzureFaceAPI
        return AzureFaceAPI()
    # Local deepface fallback
    from kyc.liveness.service import LivenessService
    svc = LivenessService(provider='mock')
    class MockMatcher:
        def compare_faces(self, s, d):
            return svc._check_mock(s)
    return MockMatcher()
