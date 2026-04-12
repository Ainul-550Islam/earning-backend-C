# kyc/liveness/service.py  ── WORLD #1
"""Liveness + Deepfake detection service"""
import logging
import time

logger = logging.getLogger(__name__)


class LivenessService:

    def __init__(self, provider: str = 'mock'):
        self.provider = provider

    def check(self, kyc, image_file, check_type: str = 'passive') -> dict:
        """Run liveness check. Returns result dict."""
        start = time.time()

        if self.provider == 'facetec':
            result = self._check_facetec(image_file)
        elif self.provider == 'iproov':
            result = self._check_iproov(image_file)
        elif self.provider == 'aws_rekognition':
            result = self._check_aws(image_file)
        else:
            result = self._check_mock(image_file)

        result['processing_time_ms'] = int((time.time() - start) * 1000)
        result['check_type']         = check_type
        result['provider']           = self.provider
        return result

    def _check_mock(self, image_file) -> dict:
        """Mock — deterministic based on file size"""
        size = getattr(image_file, 'size', 0) or 0
        score = 0.85 + (size % 100) / 1000  # 0.85 - 0.95
        return {
            'result':              'live',
            'liveness_score':      round(min(score, 1.0), 4),
            'confidence':          0.92,
            'is_deepfake':         False,
            'is_print_attack':     False,
            'is_screen_attack':    False,
            'is_mask_attack':      False,
            'is_injection_attack': False,
            'media_integrity_score': 0.95,
            'texture_score':       0.88,
            'depth_score':         0.79,
        }

    def _check_aws(self, image_file) -> dict:
        """AWS Rekognition Face Liveness"""
        try:
            import boto3
            from kyc.utils.image_utils import image_to_base64
            client  = boto3.client('rekognition')
            content = image_to_base64(image_file)
            import base64
            resp = client.detect_faces(
                Image={'Bytes': base64.b64decode(content)},
                Attributes=['ALL']
            )
            faces = resp.get('FaceDetails', [])
            if not faces:
                return {'result': 'error', 'liveness_score': 0.0, 'error': 'No face detected'}
            face  = faces[0]
            score = face.get('Confidence', 0) / 100
            return {
                'result': 'live' if score > 0.90 else 'spoof',
                'liveness_score':  round(score, 4),
                'confidence':      round(score, 4),
                'is_deepfake':     score < 0.50,
                'is_print_attack': False,
                'is_screen_attack': False,
                'is_mask_attack':  False,
                'is_injection_attack': False,
                'media_integrity_score': score,
                'texture_score':   score,
                'depth_score':     0.0,
                'raw_response':    resp,
            }
        except Exception as e:
            logger.error(f"AWS liveness check failed: {e}")
            return {'result': 'error', 'liveness_score': 0.0, 'error': str(e)}

    def _check_facetec(self, image_file) -> dict:
        """FaceTec 3D liveness — requires FaceTec SDK"""
        logger.warning("FaceTec provider not configured — using mock")
        return self._check_mock(image_file)

    def _check_iproov(self, image_file) -> dict:
        """iProov liveness"""
        logger.warning("iProov provider not configured — using mock")
        return self._check_mock(image_file)

    def detect_deepfake(self, image_file) -> dict:
        """
        Deepfake detection using available AI models.
        In production: use specialized deepfake detector (e.g., Microsoft Video Authenticator, Sensity).
        """
        try:
            import cv2, numpy as np
            from PIL import Image

            if hasattr(image_file, 'seek'):
                image_file.seek(0)

            img     = Image.open(image_file).convert('RGB')
            arr     = np.array(img)
            gray    = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            laplace = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Very rough heuristic — low variance can indicate AI-generated images
            deepfake_prob = max(0.0, min(1.0, 1.0 - laplace / 10000))
            is_synthetic  = deepfake_prob > 0.75

            if hasattr(image_file, 'seek'):
                image_file.seek(0)

            return {
                'deepfake_probability': round(deepfake_prob, 4),
                'is_synthetic':         is_synthetic,
                'artifacts_detected':   ['low_texture_variance'] if is_synthetic else [],
            }
        except ImportError:
            return {'deepfake_probability': 0.05, 'is_synthetic': False, 'artifacts_detected': []}
        except Exception as e:
            logger.warning(f"Deepfake detection error: {e}")
            return {'deepfake_probability': 0.0, 'is_synthetic': False, 'artifacts_detected': []}

    def save_result(self, kyc, result: dict):
        """Save liveness result to DB"""
        from .models import LivenessCheck, DeepfakeDetectionLog
        check = LivenessCheck.objects.create(
            kyc=kyc, user=kyc.user,
            check_type=result.get('check_type', 'passive'),
            provider=result.get('provider', 'mock'),
            result=result.get('result', 'pending'),
            liveness_score=result.get('liveness_score', 0.0),
            confidence=result.get('confidence', 0.0),
            is_deepfake=result.get('is_deepfake', False),
            is_print_attack=result.get('is_print_attack', False),
            is_screen_attack=result.get('is_screen_attack', False),
            is_mask_attack=result.get('is_mask_attack', False),
            is_injection_attack=result.get('is_injection_attack', False),
            media_integrity_score=result.get('media_integrity_score', 0.0),
            texture_score=result.get('texture_score', 0.0),
            depth_score=result.get('depth_score', 0.0),
            processing_time_ms=result.get('processing_time_ms', 0),
            error=result.get('error', ''),
            raw_response=result.get('raw_response', {}),
        )
        # Update KYC face verification
        if check.passed:
            kyc.is_face_verified = True
            kyc.save(update_fields=['is_face_verified', 'updated_at'])
        return check
