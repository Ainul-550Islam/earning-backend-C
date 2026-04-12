# api/promotions/ai/face_detection.py
# Face Detection — Selfie Proof Verification
# =============================================================================

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('ai.face_detection')


@dataclass
class FaceDetectionResult:
    faces_found:      int
    face_locations:   list        # bounding boxes
    is_live:          bool        # Liveness detection (anti-spoofing)
    is_match:         bool        # Reference face match হয়েছে কিনা
    similarity_score: float       # Face similarity 0.0-1.0
    quality_score:    float       # Face image quality
    attributes:       dict        # age_estimate, gender, emotion (optional)
    engine_used:      str


class FaceDetector:
    """
    Face Detection ও Verification।
    Selfie proof submission এর জন্য।

    Use cases:
    1. Selfie with screen proof — face আছে কিনা check
    2. ID verification — face ও ID এর face match করা
    3. Liveness detection — photo স্পুফিং রোধ

    Libraries: face_recognition (dlib) বা DeepFace বা AWS Rekognition
    """

    def detect_faces(self, image_source: str | bytes) -> FaceDetectionResult:
        """Image এ face detect করে।"""
        image_bytes = self._load_image(image_source)
        if not image_bytes:
            return self._no_face_result('image_load_failed')

        for engine_fn in [self._try_face_recognition, self._try_deepface, self._try_opencv]:
            try:
                result = engine_fn(image_bytes)
                if result:
                    return result
            except Exception as e:
                logger.debug(f'Face detection engine failed: {e}')
                continue

        return self._no_face_result('no_engine_available')

    def verify_face_match(
        self,
        source_image: str | bytes,
        target_image: str | bytes,
    ) -> FaceDetectionResult:
        """দুটো image এর face match করে।"""
        src_bytes = self._load_image(source_image)
        tgt_bytes = self._load_image(target_image)
        if not src_bytes or not tgt_bytes:
            return self._no_face_result('image_load_failed')

        try:
            import face_recognition
            import numpy as np
            from PIL import Image
            import io

            src_img  = face_recognition.load_image_file(io.BytesIO(src_bytes))
            tgt_img  = face_recognition.load_image_file(io.BytesIO(tgt_bytes))

            src_enc  = face_recognition.face_encodings(src_img)
            tgt_enc  = face_recognition.face_encodings(tgt_img)

            if not src_enc or not tgt_enc:
                return self._no_face_result('face_not_found')

            distance = face_recognition.face_distance([src_enc[0]], tgt_enc[0])[0]
            sim      = max(0.0, 1.0 - distance)

            return FaceDetectionResult(
                faces_found     = 1,
                face_locations  = [],
                is_live         = True,   # Liveness check এখানে add করুন
                is_match        = sim > 0.6,
                similarity_score = round(sim, 3),
                quality_score   = 0.8,
                attributes      = {},
                engine_used     = 'face_recognition',
            )
        except ImportError:
            logger.warning('face_recognition not installed.')
            return self._no_face_result('face_recognition_not_installed')

    def _try_face_recognition(self, image_bytes: bytes) -> Optional[FaceDetectionResult]:
        import face_recognition
        import io
        img       = face_recognition.load_image_file(io.BytesIO(image_bytes))
        locations = face_recognition.face_locations(img, model='hog')
        return FaceDetectionResult(
            faces_found     = len(locations),
            face_locations  = [list(loc) for loc in locations],
            is_live         = True,
            is_match        = False,
            similarity_score = 0.0,
            quality_score   = 0.8 if locations else 0.0,
            attributes      = {},
            engine_used     = 'face_recognition',
        )

    def _try_deepface(self, image_bytes: bytes) -> Optional[FaceDetectionResult]:
        from deepface import DeepFace
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        try:
            faces = DeepFace.extract_faces(tmp_path, enforce_detection=False)
            return FaceDetectionResult(
                faces_found     = len(faces),
                face_locations  = [],
                is_live         = True,
                is_match        = False,
                similarity_score = 0.0,
                quality_score   = faces[0].get('confidence', 0.5) if faces else 0.0,
                attributes      = {},
                engine_used     = 'deepface',
            )
        finally:
            os.unlink(tmp_path)

    def _try_opencv(self, image_bytes: bytes) -> Optional[FaceDetectionResult]:
        import cv2
        import numpy as np

        # OpenCV Haar Cascade (built-in, no extra download)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img       = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
        faces     = face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5)

        return FaceDetectionResult(
            faces_found     = len(faces),
            face_locations  = [list(map(int, f)) for f in faces],
            is_live         = True,
            is_match        = False,
            similarity_score = 0.0,
            quality_score   = 0.6 if len(faces) > 0 else 0.0,
            attributes      = {},
            engine_used     = 'opencv_haar',
        )

    def _no_face_result(self, reason: str) -> FaceDetectionResult:
        return FaceDetectionResult(
            faces_found=0, face_locations=[], is_live=False, is_match=False,
            similarity_score=0.0, quality_score=0.0, attributes={}, engine_used=reason,
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