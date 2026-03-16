# =============================================================================
# api/promotions/ai/ocr_engine.py
# OCR Engine — Screenshot থেকে Text Extract করা
# Tesseract + EasyOCR + Google Vision API fallback chain
# =============================================================================

import base64
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve
import tempfile
import os

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('ai.ocr_engine')

# Cache config
CACHE_PREFIX_OCR   = 'ai:ocr:{}'
CACHE_TTL_OCR      = 3600 * 24   # 24 hours — same screenshot দুইবার process হবে না


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class OCRResult:
    """OCR এর output।"""
    text:             str
    confidence:       float        # 0.0 - 1.0
    language:         str          = 'unknown'
    engine_used:      str          = 'unknown'
    bounding_boxes:   list         = field(default_factory=list)
    extracted_data:   dict         = field(default_factory=dict)  # structured info
    processing_ms:    float        = 0.0
    cached:           bool         = False


@dataclass
class ProofVerificationResult:
    """Screenshot proof verify করার ফলাফল।"""
    is_valid:         bool
    confidence:       float
    extracted_text:   str
    matched_keywords: list
    failed_checks:    list
    recommendation:   str          # 'approve', 'reject', 'manual_review'


# =============================================================================
# ── OCR ENGINE ────────────────────────────────────────────────────────────────
# =============================================================================

class OCREngine:
    """
    Multi-engine OCR — Tesseract → EasyOCR → Google Vision fallback chain।
    Screenshot থেকে text extract করে proof verification এ ব্যবহার হয়।

    Priority:
    1. Tesseract (local, fast, free)
    2. EasyOCR (local, accurate, GPU optional)
    3. Google Cloud Vision (cloud, most accurate, paid)
    """

    def extract_text(
        self,
        image_source: str | bytes,
        language: str = 'eng',
        use_cache: bool = True,
    ) -> OCRResult:
        """
        Image থেকে text extract করে।

        Args:
            image_source: URL, file path, অথবা raw bytes
            language: 'eng', 'ben' (Bengali), 'hin', 'auto'
            use_cache: একই image দুইবার process না করা
        """
        import time
        start = time.monotonic()

        # ── Cache check ────────────────────────────────────────────────────
        if use_cache:
            image_hash = self._compute_hash(image_source)
            cache_key  = CACHE_PREFIX_OCR.format(image_hash)
            cached     = cache.get(cache_key)
            if cached:
                cached['cached'] = True
                return OCRResult(**cached)

        # ── Image load করো ────────────────────────────────────────────────
        image_bytes = self._load_image(image_source)
        if not image_bytes:
            return OCRResult(
                text='', confidence=0.0, engine_used='failed',
                extracted_data={'error': 'Could not load image'}
            )

        # ── Engine chain try করো ──────────────────────────────────────────
        result = None
        for engine_fn in [self._try_tesseract, self._try_easyocr, self._try_google_vision]:
            try:
                result = engine_fn(image_bytes, language)
                if result and result.confidence >= 0.3:
                    break
            except Exception as e:
                logger.debug(f'OCR engine failed: {e}')
                continue

        if not result:
            result = OCRResult(text='', confidence=0.0, engine_used='all_failed')

        # ── Structured data extract ────────────────────────────────────────
        result.extracted_data = self._extract_structured_data(result.text)
        result.processing_ms  = round((time.monotonic() - start) * 1000, 2)

        # ── Cache store ────────────────────────────────────────────────────
        if use_cache and result.confidence > 0:
            cache.set(
                CACHE_PREFIX_OCR.format(self._compute_hash(image_source)),
                result.__dict__,
                timeout=CACHE_TTL_OCR,
            )

        logger.info(
            f'OCR: engine={result.engine_used}, confidence={result.confidence:.2f}, '
            f'chars={len(result.text)}, time={result.processing_ms}ms'
        )
        return result

    # ── Engine Implementations ────────────────────────────────────────────────

    def _try_tesseract(self, image_bytes: bytes, language: str) -> Optional[OCRResult]:
        """Tesseract OCR — local, fast।"""
        import pytesseract
        from PIL import Image
        import io

        lang_map = {'eng': 'eng', 'ben': 'ben', 'hin': 'hin', 'auto': 'eng+ben'}
        tess_lang = lang_map.get(language, 'eng')

        img = Image.open(io.BytesIO(image_bytes))
        # Preprocessing — বড় করলে accuracy বাড়ে
        if img.width < 800:
            scale  = 800 / img.width
            img    = img.resize((int(img.width * scale), int(img.height * scale)))

        # Grayscale + threshold
        img = img.convert('L')

        data = pytesseract.image_to_data(
            img, lang=tess_lang,
            output_type=pytesseract.Output.DICT,
            config='--oem 3 --psm 6',
        )
        text        = pytesseract.image_to_string(img, lang=tess_lang)
        confidences = [int(c) for c in data['conf'] if int(c) > 0]
        avg_conf    = (sum(confidences) / len(confidences) / 100) if confidences else 0.0

        # Bounding boxes
        boxes = []
        for i in range(len(data['text'])):
            if int(data['conf'][i]) > 50 and data['text'][i].strip():
                boxes.append({
                    'text': data['text'][i],
                    'x': data['left'][i], 'y': data['top'][i],
                    'w': data['width'][i], 'h': data['height'][i],
                    'conf': data['conf'][i],
                })

        return OCRResult(
            text=text.strip(), confidence=avg_conf,
            language=tess_lang, engine_used='tesseract',
            bounding_boxes=boxes,
        )

    def _try_easyocr(self, image_bytes: bytes, language: str) -> Optional[OCRResult]:
        """EasyOCR — more accurate, supports Bengali।"""
        import easyocr
        import numpy as np
        from PIL import Image
        import io

        lang_map = {'eng': ['en'], 'ben': ['bn', 'en'], 'hin': ['hi', 'en'], 'auto': ['en', 'bn']}
        langs    = lang_map.get(language, ['en'])

        # EasyOCR reader cache (expensive to init)
        cache_attr = f'_easyocr_reader_{"_".join(langs)}'
        if not hasattr(self, cache_attr):
            reader = easyocr.Reader(langs, gpu=False, verbose=False)
            setattr(self, cache_attr, reader)
        reader = getattr(self, cache_attr)

        img    = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_np = np.array(img)
        results = reader.readtext(img_np, detail=1)

        if not results:
            return OCRResult(text='', confidence=0.0, engine_used='easyocr')

        texts       = []
        confidences = []
        boxes       = []
        for (bbox, text, conf) in results:
            texts.append(text)
            confidences.append(conf)
            boxes.append({'text': text, 'bbox': bbox, 'conf': round(conf, 3)})

        full_text = ' '.join(texts)
        avg_conf  = sum(confidences) / len(confidences)

        return OCRResult(
            text=full_text.strip(), confidence=round(avg_conf, 3),
            language=language, engine_used='easyocr',
            bounding_boxes=boxes,
        )

    def _try_google_vision(self, image_bytes: bytes, language: str) -> Optional[OCRResult]:
        """Google Cloud Vision API — সবচেয়ে accurate, paid।"""
        api_key = getattr(settings, 'GOOGLE_VISION_API_KEY', None)
        if not api_key:
            return None

        import requests

        payload = {
            'requests': [{
                'image':    {'content': base64.b64encode(image_bytes).decode()},
                'features': [{'type': 'TEXT_DETECTION', 'maxResults': 1}],
                'imageContext': {'languageHints': [language[:2]]},
            }]
        }
        resp = requests.post(
            f'https://vision.googleapis.com/v1/images:annotate?key={api_key}',
            json=payload, timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        annotations = data.get('responses', [{}])[0].get('textAnnotations', [])
        if not annotations:
            return OCRResult(text='', confidence=0.0, engine_used='google_vision')

        full_text = annotations[0].get('description', '').strip()

        # Confidence estimation (Vision API doesn't always return confidence)
        confidence = 0.95 if full_text else 0.0

        return OCRResult(
            text=full_text, confidence=confidence,
            language=language, engine_used='google_vision',
        )

    # ── Structured Data Extraction ────────────────────────────────────────────

    def _extract_structured_data(self, text: str) -> dict:
        """OCR text থেকে structured information extract করে।"""
        data = {}

        # URLs
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            data['urls'] = urls

        # Numbers (like like counts, follower counts)
        numbers = re.findall(r'\b\d[\d,\.]*[KMB]?\b', text)
        if numbers:
            data['numbers'] = numbers

        # Usernames (@username)
        usernames = re.findall(r'@[\w\.]+', text)
        if usernames:
            data['usernames'] = usernames

        # Hashtags
        hashtags = re.findall(r'#[\w]+', text)
        if hashtags:
            data['hashtags'] = hashtags

        # Email addresses
        emails = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', text)
        if emails:
            data['emails'] = emails

        # Dates
        dates = re.findall(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
            text
        )
        if dates:
            data['dates'] = dates

        # Social media specific — subscriber/follower counts
        social_patterns = [
            (r'(\d[\d,\.]*[KMB]?)\s*(?:subscribers?|followers?|likes?|views?)', 'social_metrics'),
        ]
        for pattern, key in social_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                data[key] = matches

        return data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_image(self, source: str | bytes) -> Optional[bytes]:
        """URL, path বা bytes থেকে image load করে।"""
        if isinstance(source, bytes):
            return source
        if isinstance(source, str):
            if source.startswith('http'):
                try:
                    import requests
                    resp = requests.get(source, timeout=10, stream=True)
                    resp.raise_for_status()
                    return resp.content
                except Exception as e:
                    logger.error(f'Image download failed ({source[:50]}): {e}')
                    return None
            elif os.path.exists(source):
                return Path(source).read_bytes()
        return None

    @staticmethod
    def _compute_hash(source: str | bytes) -> str:
        if isinstance(source, bytes):
            return hashlib.sha256(source).hexdigest()
        return hashlib.sha256(str(source).encode()).hexdigest()


# =============================================================================
# ── PROOF VERIFIER ────────────────────────────────────────────────────────────
# =============================================================================

class ProofVerifier:
    """
    Task submission proof (screenshot) verify করে।
    OCR দিয়ে text extract করে keyword check করে।
    """

    def __init__(self):
        self.ocr = OCREngine()

    def verify_screenshot_proof(
        self,
        image_source: str | bytes,
        required_keywords: list[str] = None,
        campaign_url: str = None,
        task_type: str = None,
    ) -> ProofVerificationResult:
        """
        Screenshot proof verify করে।

        Args:
            image_source: Screenshot URL বা bytes
            required_keywords: এগুলো screenshot এ থাকতে হবে
            campaign_url: Target URL — screenshot এ domain থাকা উচিত
            task_type: 'youtube_subscribe', 'facebook_like' ইত্যাদি
        """
        ocr_result = self.ocr.extract_text(image_source)

        if ocr_result.confidence < 0.2:
            return ProofVerificationResult(
                is_valid=False, confidence=0.0,
                extracted_text='', matched_keywords=[],
                failed_checks=['ocr_failed_low_confidence'],
                recommendation='reject',
            )

        text_lower     = ocr_result.text.lower()
        matched        = []
        failed         = []
        score          = 0.0

        # ── Check 1: Required keywords ────────────────────────────────────
        if required_keywords:
            for kw in required_keywords:
                if kw.lower() in text_lower:
                    matched.append(kw)
                else:
                    failed.append(f'missing_keyword:{kw}')

            keyword_score = len(matched) / len(required_keywords)
            score        += keyword_score * 0.50

        # ── Check 2: Domain match ─────────────────────────────────────────
        if campaign_url:
            from urllib.parse import urlparse
            domain = urlparse(campaign_url).netloc.replace('www.', '')
            if domain and domain.lower() in text_lower:
                score += 0.20
                matched.append(f'domain:{domain}')
            else:
                failed.append(f'missing_domain:{domain}')

        # ── Check 3: Task-specific validation ────────────────────────────
        task_score, task_matched, task_failed = self._check_task_specific(
            text_lower, ocr_result.extracted_data, task_type
        )
        score    += task_score * 0.30
        matched.extend(task_matched)
        failed.extend(task_failed)

        # ── Check 4: OCR confidence factor ────────────────────────────────
        score *= (0.5 + ocr_result.confidence * 0.5)

        score = min(1.0, score)

        if score >= 0.70:
            recommendation = 'approve'
        elif score >= 0.40:
            recommendation = 'manual_review'
        else:
            recommendation = 'reject'

        return ProofVerificationResult(
            is_valid         = score >= 0.50,
            confidence       = round(score, 3),
            extracted_text   = ocr_result.text[:500],
            matched_keywords = matched,
            failed_checks    = failed,
            recommendation   = recommendation,
        )

    def _check_task_specific(
        self, text: str, extracted: dict, task_type: str
    ) -> tuple[float, list, list]:
        """Task type অনুযায়ী specific validation।"""
        score   = 0.5  # Default neutral
        matched = []
        failed  = []

        if not task_type:
            return score, matched, failed

        task_type = task_type.lower()

        if 'youtube' in task_type and 'subscribe' in task_type:
            indicators = ['subscribed', 'subscribe', 'bell', 'notification', 'unsubscribe']
            found      = [i for i in indicators if i in text]
            if found:
                score = 0.8; matched.extend(found)
            else:
                score = 0.2; failed.append('youtube_subscribe_indicators_missing')

        elif 'youtube' in task_type and 'like' in task_type:
            if any(w in text for w in ['liked', 'thumbs up', 'unlike']):
                score = 0.8; matched.append('youtube_like_indicator')
            else:
                score = 0.3; failed.append('youtube_like_indicator_missing')

        elif 'facebook' in task_type and 'like' in task_type:
            if any(w in text for w in ['like', 'liked', 'unlike', '👍']):
                score = 0.8; matched.append('facebook_like_indicator')

        elif 'app' in task_type and ('install' in task_type or 'download' in task_type):
            if any(w in text for w in ['installed', 'open', 'uninstall', 'update']):
                score = 0.8; matched.append('app_install_indicator')
            elif any(w in text for w in ['install', 'get', 'download']):
                score = 0.5; matched.append('app_not_yet_installed')
                failed.append('app_may_not_be_installed')

        return score, matched, failed
