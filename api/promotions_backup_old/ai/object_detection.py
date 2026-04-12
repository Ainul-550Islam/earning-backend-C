# api/promotions/ai/object_detection.py
# Object Detection — Screenshot Content Validation
# YOLO / DETR দিয়ে object detect করে proof validate করে
# =============================================================================

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('ai.object_detection')


@dataclass
class DetectedObject:
    label:      str
    confidence: float
    bbox:       list    # [x, y, width, height]


@dataclass
class ObjectDetectionResult:
    objects:          list[DetectedObject]
    total_count:      int
    labels_found:     list
    relevant_objects: list    # task এর জন্য relevant objects
    scene_type:       str     # 'mobile_screenshot', 'desktop_screenshot', 'photo', 'unknown'
    engine_used:      str
    processing_ms:    float   = 0.0


class ObjectDetector:
    """
    Object Detection — Screenshot এ relevant objects identify করে।

    Use cases:
    - App install proof: Play Store UI elements
    - Survey completion: Survey form elements
    - Social media task: Platform-specific buttons

    Engines: YOLOv8 → DETR (transformers) → Google Vision fallback
    """

    # Task-relevant object categories
    TASK_RELEVANT_OBJECTS = {
        'play_store':  ['button', 'star', 'text', 'icon', 'screenshot'],
        'youtube':     ['button', 'video', 'thumbnail', 'person', 'text'],
        'survey':      ['form', 'checkbox', 'radio_button', 'text_field'],
        'facebook':    ['button', 'profile', 'text', 'image'],
    }

    def detect(
        self,
        image_source: str | bytes,
        task_context: str = None,
        confidence_threshold: float = 0.4,
    ) -> ObjectDetectionResult:
        """Image এ objects detect করে।"""
        import time
        start = time.monotonic()

        image_bytes = self._load_image(image_source)
        if not image_bytes:
            return self._empty_result('image_load_failed')

        result = None
        for engine_fn in [self._try_yolo, self._try_transformers, self._try_google_vision]:
            try:
                result = engine_fn(image_bytes, confidence_threshold)
                if result and result.total_count >= 0:
                    break
            except Exception as e:
                logger.debug(f'Object detection engine failed: {e}')
                continue

        if not result:
            result = self._empty_result('no_engine')

        # Relevant objects filter
        if task_context:
            relevant_labels = self.TASK_RELEVANT_OBJECTS.get(task_context.lower(), [])
            result.relevant_objects = [
                obj for obj in result.objects
                if any(rl in obj.label.lower() for rl in relevant_labels)
            ]

        result.processing_ms = round((time.monotonic() - start) * 1000, 2)
        return result

    def _try_yolo(self, image_bytes: bytes, threshold: float) -> Optional[ObjectDetectionResult]:
        """YOLOv8 — fast, accurate object detection।"""
        from ultralytics import YOLO
        import numpy as np
        from PIL import Image
        import io

        # Model cache
        if not hasattr(self, '_yolo_model'):
            self._yolo_model = YOLO('yolov8n.pt')  # nano model — fastest

        img    = Image.open(io.BytesIO(image_bytes))
        results = self._yolo_model(img, verbose=False)[0]

        objects = []
        for box in results.boxes:
            conf  = float(box.conf[0])
            if conf < threshold:
                continue
            label = results.names[int(box.cls[0])]
            bbox  = box.xywh[0].tolist()
            objects.append(DetectedObject(label=label, confidence=round(conf, 3), bbox=bbox))

        return ObjectDetectionResult(
            objects          = objects,
            total_count      = len(objects),
            labels_found     = list({o.label for o in objects}),
            relevant_objects = [],
            scene_type       = self._classify_scene(objects),
            engine_used      = 'yolov8',
        )

    def _try_transformers(self, image_bytes: bytes, threshold: float) -> Optional[ObjectDetectionResult]:
        """HuggingFace DETR।"""
        from transformers import pipeline
        from PIL import Image
        import io

        if not hasattr(self, '_detr_pipeline'):
            self._detr_pipeline = pipeline('object-detection', model='facebook/detr-resnet-50')

        img     = Image.open(io.BytesIO(image_bytes))
        results = self._detr_pipeline(img)

        objects = [
            DetectedObject(
                label=r['label'],
                confidence=round(r['score'], 3),
                bbox=[r['box']['xmin'], r['box']['ymin'],
                      r['box']['xmax'] - r['box']['xmin'],
                      r['box']['ymax'] - r['box']['ymin']],
            )
            for r in results if r['score'] >= threshold
        ]
        return ObjectDetectionResult(
            objects=objects, total_count=len(objects),
            labels_found=list({o.label for o in objects}),
            relevant_objects=[], scene_type=self._classify_scene(objects),
            engine_used='detr_resnet50',
        )

    def _try_google_vision(self, image_bytes: bytes, threshold: float) -> Optional[ObjectDetectionResult]:
        """Google Vision API object localization।"""
        from django.conf import settings
        api_key = getattr(settings, 'GOOGLE_VISION_API_KEY', None)
        if not api_key:
            return None

        import requests, base64
        payload = {'requests': [{
            'image': {'content': base64.b64encode(image_bytes).decode()},
            'features': [{'type': 'OBJECT_LOCALIZATION', 'maxResults': 20}],
        }]}
        resp = requests.post(
            f'https://vision.googleapis.com/v1/images:annotate?key={api_key}',
            json=payload, timeout=10,
        )
        resp.raise_for_status()
        annotations = resp.json()['responses'][0].get('localizedObjectAnnotations', [])
        objects     = [
            DetectedObject(
                label=a['name'], confidence=round(a['score'], 3),
                bbox=[a['boundingPoly']['normalizedVertices'][0].get('x', 0),
                      a['boundingPoly']['normalizedVertices'][0].get('y', 0), 0, 0],
            )
            for a in annotations if a['score'] >= threshold
        ]
        return ObjectDetectionResult(
            objects=objects, total_count=len(objects),
            labels_found=list({o.label for o in objects}),
            relevant_objects=[], scene_type='unknown',
            engine_used='google_vision',
        )

    @staticmethod
    def _classify_scene(objects: list[DetectedObject]) -> str:
        labels = {o.label.lower() for o in objects}
        if 'cell phone' in labels or 'mobile phone' in labels:
            return 'mobile_screenshot'
        if 'laptop' in labels or 'monitor' in labels or 'keyboard' in labels:
            return 'desktop_screenshot'
        if 'person' in labels or 'face' in labels:
            return 'photo'
        return 'screenshot'

    def _empty_result(self, reason: str) -> ObjectDetectionResult:
        return ObjectDetectionResult(
            objects=[], total_count=0, labels_found=[],
            relevant_objects=[], scene_type='unknown', engine_used=reason,
        )

    def _load_image(self, source) -> Optional[bytes]:
        if isinstance(source, bytes):
            return source
        if isinstance(source, str) and source.startswith('http'):
            try:
                import requests
                r = requests.get(source, timeout=10)
                r.raise_for_status()
                return r.content
            except Exception:
                return None
        return None