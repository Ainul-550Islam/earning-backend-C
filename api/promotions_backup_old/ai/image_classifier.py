# =============================================================================
# api/promotions/ai/image_classifier.py
# Image Classifier — Screenshot Authenticity, Content Type Detection
# NSFW Filter, Fake Screenshot Detection, Platform UI Recognition
# =============================================================================

import hashlib
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('ai.image_classifier')

CACHE_PREFIX_CLASSIFY = 'ai:classify:{}'
CACHE_TTL_CLASSIFY    = 3600 * 24


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class ClassificationResult:
    """Image classification এর ফলাফল।"""
    is_authentic:     bool
    authenticity_score: float        # 0.0 = fake, 1.0 = real
    platform_detected: Optional[str] # 'youtube', 'facebook', 'play_store', None
    content_type:     str            # 'screenshot', 'photo', 'edited', 'unknown'
    is_nsfw:          bool
    nsfw_score:       float
    manipulation_detected: bool
    manipulation_type:     Optional[str]  # 'photoshopped', 'screenshot_of_screenshot', 'ai_generated'
    labels:           list           # detected objects/labels
    confidence:       float
    engine_used:      str
    processing_ms:    float          = 0.0
    cached:           bool           = False
    flags:            list           = field(default_factory=list)


@dataclass
class PlatformDetectionResult:
    """Social media platform UI detection।"""
    platform:         Optional[str]
    confidence:       float
    ui_elements:      list           # detected UI elements (subscribe button, like button, etc.)
    action_completed: bool           # task আসলে complete হয়েছে কিনা
    evidence:         dict


# =============================================================================
# ── IMAGE CLASSIFIER ──────────────────────────────────────────────────────────
# =============================================================================

class ImageClassifier:
    """
    Multi-purpose image classification।

    Features:
    1. Screenshot authenticity detection
    2. Platform UI recognition (YouTube, Facebook, etc.)
    3. NSFW content filter
    4. AI-generated image detection
    5. Screenshot manipulation detection
    """

    # Platform UI signatures — এই patterns থাকলে platform identify করা যায়
    PLATFORM_UI_SIGNATURES = {
        'youtube': {
            'colors':   [(255, 0, 0)],           # YouTube red
            'keywords': ['subscribe', 'subscribed', 'views', 'likes', 'share', 'youtube'],
            'ui_elements': ['subscribe_button', 'like_button', 'view_count'],
        },
        'facebook': {
            'colors':   [(24, 119, 242)],         # Facebook blue
            'keywords': ['like', 'comment', 'share', 'facebook', 'messenger'],
            'ui_elements': ['like_button', 'comment_box', 'share_button'],
        },
        'instagram': {
            'colors':   [(225, 48, 108), (64, 93, 230)],  # Instagram gradient
            'keywords': ['follow', 'following', 'followers', 'instagram', 'reels', 'story'],
            'ui_elements': ['follow_button', 'heart_button'],
        },
        'tiktok': {
            'colors':   [(0, 0, 0), (254, 44, 85)],       # TikTok black/red
            'keywords': ['follow', 'following', 'tiktok', 'duet', 'stitch'],
            'ui_elements': ['follow_button', 'heart_button', 'share_button'],
        },
        'play_store': {
            'colors':   [(1, 135, 134), (234, 67, 53)],   # Google colors
            'keywords': ['install', 'update', 'uninstall', 'open', 'rating', 'reviews', 'google play'],
            'ui_elements': ['install_button', 'rating_stars', 'review_count'],
        },
    }

    def classify(
        self,
        image_source: str | bytes,
        expected_platform: str = None,
        use_cache: bool = True,
    ) -> ClassificationResult:
        """
        Image classify করে।

        Args:
            image_source: URL, path বা bytes
            expected_platform: 'youtube', 'facebook' ইত্যাদি
            use_cache: Cache থেকে result নেওয়া
        """
        import time
        start = time.monotonic()

        # Load image
        image_bytes = self._load_image(image_source)
        if not image_bytes:
            return self._error_result('image_load_failed')

        # Cache check
        img_hash = hashlib.sha256(image_bytes).hexdigest()
        if use_cache:
            cached = cache.get(CACHE_PREFIX_CLASSIFY.format(img_hash))
            if cached:
                result = ClassificationResult(**cached)
                result.cached = True
                return result

        # Run all checks
        result = self._run_classification_pipeline(image_bytes, expected_platform)
        result.processing_ms = round((time.monotonic() - start) * 1000, 2)

        # Cache store
        if use_cache:
            cache.set(
                CACHE_PREFIX_CLASSIFY.format(img_hash),
                result.__dict__,
                timeout=CACHE_TTL_CLASSIFY,
            )

        logger.info(
            f'Image classify: platform={result.platform_detected}, '
            f'authentic={result.is_authentic}({result.authenticity_score:.2f}), '
            f'nsfw={result.is_nsfw}, time={result.processing_ms}ms'
        )
        return result

    def detect_platform_action(
        self,
        image_source: str | bytes,
        platform: str,
        task_type: str,
    ) -> PlatformDetectionResult:
        """
        Screenshot এ specific platform action complete হয়েছে কিনা detect করে।
        যেমন: YouTube subscribe করা হয়েছে কিনা।
        """
        image_bytes = self._load_image(image_source)
        if not image_bytes:
            return PlatformDetectionResult(
                platform=None, confidence=0.0, ui_elements=[],
                action_completed=False, evidence={'error': 'image_load_failed'}
            )

        # Color analysis
        dominant_colors = self._get_dominant_colors(image_bytes, n=5)
        # Text from OCR (lazy import)
        text = self._get_text_from_image(image_bytes)

        sig           = self.PLATFORM_UI_SIGNATURES.get(platform.lower(), {})
        text_lower    = text.lower()
        found_keywords = [kw for kw in sig.get('keywords', []) if kw in text_lower]
        ui_elements   = self._detect_ui_elements(image_bytes, platform, text_lower)
        action_done   = self._check_action_completed(text_lower, platform, task_type)

        keyword_score = len(found_keywords) / max(len(sig.get('keywords', [1])), 1)
        ui_score      = len(ui_elements) / max(len(sig.get('ui_elements', [1])), 1)
        confidence    = (keyword_score * 0.5 + ui_score * 0.5)

        return PlatformDetectionResult(
            platform          = platform if confidence > 0.3 else None,
            confidence        = round(confidence, 3),
            ui_elements       = ui_elements,
            action_completed  = action_done and confidence > 0.4,
            evidence          = {
                'found_keywords':  found_keywords,
                'dominant_colors': dominant_colors[:3],
                'text_sample':     text[:200],
            },
        )

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _run_classification_pipeline(
        self, image_bytes: bytes, expected_platform: str
    ) -> ClassificationResult:
        """সব classification steps run করে।"""
        flags = []

        # ── 1. Basic image analysis ────────────────────────────────────────
        img_info      = self._analyze_image_basic(image_bytes)
        text          = self._get_text_from_image(image_bytes)

        # ── 2. Platform detection ──────────────────────────────────────────
        platform, platform_conf = self._detect_platform(image_bytes, text)

        # ── 3. NSFW detection ─────────────────────────────────────────────
        nsfw_score = self._detect_nsfw(image_bytes)
        is_nsfw    = nsfw_score > 0.7

        # ── 4. Manipulation detection ─────────────────────────────────────
        manipulation_type = self._detect_manipulation(image_bytes, img_info)
        manipulation_det  = manipulation_type is not None

        # ── 5. Authenticity scoring ────────────────────────────────────────
        auth_score = self._calculate_authenticity(
            img_info, platform, expected_platform,
            platform_conf, manipulation_det, text,
        )

        # ── 6. Flags ──────────────────────────────────────────────────────
        if is_nsfw:
            flags.append('nsfw_content')
        if manipulation_det:
            flags.append(f'manipulation:{manipulation_type}')
        if auth_score < 0.3:
            flags.append('low_authenticity')
        if expected_platform and platform and platform != expected_platform:
            flags.append(f'platform_mismatch:{platform}_vs_{expected_platform}')

        # ── 7. Content type ───────────────────────────────────────────────
        content_type = self._determine_content_type(img_info, manipulation_type)

        return ClassificationResult(
            is_authentic          = auth_score >= 0.5 and not manipulation_det,
            authenticity_score    = round(auth_score, 3),
            platform_detected     = platform,
            content_type          = content_type,
            is_nsfw               = is_nsfw,
            nsfw_score            = round(nsfw_score, 3),
            manipulation_detected = manipulation_det,
            manipulation_type     = manipulation_type,
            labels                = img_info.get('labels', []),
            confidence            = round(platform_conf, 3),
            engine_used           = 'pillow_rule_based',
            flags                 = flags,
        )

    # ── Detection Methods ─────────────────────────────────────────────────────

    def _analyze_image_basic(self, image_bytes: bytes) -> dict:
        """Pillow দিয়ে basic image analysis।"""
        try:
            from PIL import Image
            import io
            img  = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            w, h = img.size
            return {
                'width':      w,
                'height':     h,
                'aspect_ratio': round(w/h, 3) if h > 0 else 0,
                'is_screenshot_ratio': 0.4 < (w/h) < 3.0 if h > 0 else False,
                'mode':       img.mode,
                'format':     img.format,
                'file_size':  len(image_bytes),
                'labels':     [],
            }
        except Exception as e:
            logger.debug(f'Basic image analysis failed: {e}')
            return {}

    def _detect_platform(self, image_bytes: bytes, text: str) -> tuple[Optional[str], float]:
        """Platform detect করে color + keyword analysis দিয়ে।"""
        text_lower    = text.lower()
        best_platform = None
        best_score    = 0.0

        for platform, sig in self.PLATFORM_UI_SIGNATURES.items():
            keyword_matches = sum(1 for kw in sig['keywords'] if kw in text_lower)
            keyword_score   = keyword_matches / len(sig['keywords']) if sig['keywords'] else 0

            # Color similarity check
            color_score = 0.0
            try:
                dominant = self._get_dominant_colors(image_bytes, n=10)
                for target_color in sig['colors']:
                    for dc in dominant:
                        dist = sum((a-b)**2 for a, b in zip(target_color, dc)) ** 0.5
                        if dist < 50:  # Color distance threshold
                            color_score = max(color_score, 0.3)
                            break
            except Exception:
                pass

            score = keyword_score * 0.7 + color_score * 0.3
            if score > best_score:
                best_score    = score
                best_platform = platform

        return (best_platform if best_score > 0.2 else None, best_score)

    def _detect_nsfw(self, image_bytes: bytes) -> float:
        """NSFW content detection।"""
        try:
            # NudeNet বা NSFW-detector library ব্যবহার করুন
            # from nudenet import NudeClassifier
            # classifier = NudeClassifier()
            # result = classifier.classify_image(image_bytes)
            # return result.get('unsafe', 0.0)

            # Fallback: simple skin tone ratio check
            from PIL import Image
            import io
            img   = Image.open(io.BytesIO(image_bytes)).convert('RGB').resize((100, 100))
            pixels = list(img.getdata())
            skin_count = 0
            for r, g, b in pixels:
                # Very rough skin tone detection
                if r > 95 and g > 40 and b > 20 and max(r,g,b) - min(r,g,b) > 15:
                    if abs(r - g) > 15 and r > g and r > b:
                        skin_count += 1
            skin_ratio = skin_count / len(pixels)
            # Very high skin ratio may indicate NSFW
            return min(0.5, skin_ratio)   # Conservative estimate — real NSFW detector use করুন
        except Exception:
            return 0.0

    def _detect_manipulation(self, image_bytes: bytes, img_info: dict) -> Optional[str]:
        """Image manipulation detect করে।"""
        try:
            from PIL import Image, ImageChops
            import io
            import numpy as np

            img  = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = None

            try:
                img_array = np.array(img)
            except ImportError:
                pass

            # ── Check 1: Screenshot of screenshot (double compression artifacts) ─
            if img_info.get('file_size', 0) > 0:
                compression_ratio = img_info['file_size'] / max(
                    img_info.get('width', 1) * img_info.get('height', 1), 1
                )
                if compression_ratio < 0.3:  # Over-compressed
                    return 'heavy_compression'

            # ── Check 2: Error Level Analysis (ELA) for Photoshop ─────────
            if img_array is not None:
                try:
                    # ELA: resave at quality 90 and compare
                    temp_buf = io.BytesIO()
                    img.save(temp_buf, format='JPEG', quality=90)
                    temp_buf.seek(0)
                    img_resaved = Image.open(temp_buf).convert('RGB')
                    ela_img     = ImageChops.difference(img, img_resaved)
                    ela_array   = np.array(ela_img)
                    ela_mean    = ela_array.mean()
                    if ela_mean > 15:
                        return 'photoshopped'
                except Exception:
                    pass

            # ── Check 3: Unusually perfect dimensions (AI generated) ──────
            w, h = img_info.get('width', 0), img_info.get('height', 0)
            if w > 0 and h > 0:
                perfect_sizes = [512, 768, 1024, 1536, 2048]
                if w in perfect_sizes and h in perfect_sizes:
                    return 'ai_generated_suspected'

            return None
        except Exception as e:
            logger.debug(f'Manipulation detection error: {e}')
            return None

    def _calculate_authenticity(
        self, img_info: dict, platform: Optional[str],
        expected_platform: Optional[str], platform_conf: float,
        manipulation: bool, text: str,
    ) -> float:
        """Authenticity score calculate করে।"""
        score = 0.5

        # Platform match
        if expected_platform and platform:
            if platform == expected_platform:
                score += 0.25
            else:
                score -= 0.20

        # Platform confidence
        score += platform_conf * 0.15

        # Manipulation penalty
        if manipulation:
            score -= 0.40

        # Screenshot ratio check
        if img_info.get('is_screenshot_ratio'):
            score += 0.10

        # Reasonable text found
        if len(text) > 20:
            score += 0.05

        # File size sanity check
        size = img_info.get('file_size', 0)
        if 5000 < size < 5_000_000:  # 5KB - 5MB
            score += 0.05
        elif size < 1000:  # suspiciously small
            score -= 0.20

        return max(0.0, min(1.0, score))

    def _detect_ui_elements(self, image_bytes: bytes, platform: str, text: str) -> list:
        """Platform specific UI elements detect করে।"""
        sig      = self.PLATFORM_UI_SIGNATURES.get(platform.lower(), {})
        detected = []
        for element in sig.get('ui_elements', []):
            # Text-based detection
            indicator = element.replace('_', ' ').replace('button', '').strip()
            if indicator in text:
                detected.append(element)
        return detected

    def _check_action_completed(self, text: str, platform: str, task_type: str) -> bool:
        """Task action complete হওয়ার indicator check করে।"""
        completed_indicators = {
            'subscribe': ['subscribed', 'unsubscribe'],
            'like':      ['liked', 'unlike', '1 like'],
            'follow':    ['following', 'unfollow'],
            'install':   ['open', 'uninstall', 'update'],
            'comment':   ['comment posted', 'commented'],
        }
        task_lower = task_type.lower() if task_type else ''
        for action, indicators in completed_indicators.items():
            if action in task_lower:
                return any(ind in text for ind in indicators)
        return False

    def _get_dominant_colors(self, image_bytes: bytes, n: int = 5) -> list:
        """Image এর dominant colors বের করে।"""
        try:
            from PIL import Image
            import io
            img    = Image.open(io.BytesIO(image_bytes)).convert('RGB').resize((50, 50))
            pixels = list(img.getdata())
            # Simple frequency-based dominant color
            from collections import Counter
            # Quantize to reduce noise
            quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in pixels]
            return [list(c) for c, _ in Counter(quantized).most_common(n)]
        except Exception:
            return []

    def _get_text_from_image(self, image_bytes: bytes) -> str:
        """OCREngine import করে text বের করে।"""
        try:
            from .ocr_engine import OCREngine
            result = OCREngine().extract_text(image_bytes)
            return result.text
        except Exception:
            return ''

    def _determine_content_type(self, img_info: dict, manipulation: Optional[str]) -> str:
        if manipulation == 'ai_generated_suspected':
            return 'ai_generated'
        if manipulation == 'photoshopped':
            return 'edited'
        if img_info.get('is_screenshot_ratio'):
            return 'screenshot'
        return 'photo'

    def _load_image(self, source: str | bytes) -> Optional[bytes]:
        if isinstance(source, bytes):
            return source
        if isinstance(source, str):
            if source.startswith('http'):
                try:
                    import requests
                    r = requests.get(source, timeout=10)
                    r.raise_for_status()
                    return r.content
                except Exception as e:
                    logger.error(f'Image load failed: {e}')
                    return None
            elif source and len(source) > 0:
                from pathlib import Path
                p = Path(source)
                if p.exists():
                    return p.read_bytes()
        return None

    def _error_result(self, reason: str) -> ClassificationResult:
        return ClassificationResult(
            is_authentic=False, authenticity_score=0.0,
            platform_detected=None, content_type='unknown',
            is_nsfw=False, nsfw_score=0.0,
            manipulation_detected=False, manipulation_type=None,
            labels=[], confidence=0.0,
            engine_used='error', flags=[reason],
        )
