# kyc/integrations/providers/aws_rekognition.py  ── WORLD #1
"""
AWS Rekognition — Real Face Matching + Liveness.
Setup: pip install boto3
Credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars OR IAM role.

Pricing: ~$0.001 per image (face detection), ~$0.01 per comparison.
"""
import logging
import time
import base64

logger = logging.getLogger(__name__)


class AWSRekognitionFaceMatcher:
    """AWS Rekognition face comparison between selfie and ID document."""

    def __init__(self, region: str = 'ap-southeast-1'):
        self.region  = region
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('rekognition', region_name=self.region)
            except ImportError:
                raise ImportError("boto3 not installed. Run: pip install boto3")
        return self._client

    def compare_faces(self, selfie_file, document_file) -> dict:
        """
        Compare face in selfie vs face in ID document.
        Returns detailed match result.
        """
        start = time.time()
        result = {
            'is_matched':        False,
            'match_confidence':  0.0,
            'similarity':        0.0,
            'face_in_selfie':    False,
            'face_in_document':  False,
            'face_count_selfie': 0,
            'face_count_doc':    0,
            'bounding_box':      {},
            'provider':          'aws_rekognition',
            'processing_ms':     0,
            'error':             '',
            'raw_response':      {},
        }

        try:
            client = self._get_client()

            if hasattr(selfie_file, 'seek'):   selfie_file.seek(0)
            if hasattr(document_file, 'seek'): document_file.seek(0)
            selfie_bytes   = selfie_file.read()
            document_bytes = document_file.read()

            # Compare faces
            response = client.compare_faces(
                SourceImage={'Bytes': selfie_bytes},
                TargetImage={'Bytes': document_bytes},
                SimilarityThreshold=70.0,
            )
            result['raw_response'] = {
                'face_matches':     len(response.get('FaceMatches', [])),
                'unmatched_faces':  len(response.get('UnmatchedFaces', [])),
            }

            face_matches = response.get('FaceMatches', [])
            if face_matches:
                best_match = max(face_matches, key=lambda m: m.get('Similarity', 0))
                similarity = best_match.get('Similarity', 0) / 100.0
                result['similarity']       = round(similarity, 4)
                result['match_confidence'] = round(similarity, 4)
                result['is_matched']       = similarity >= 0.80
                result['face_in_selfie']   = True
                result['face_in_document'] = True
                result['bounding_box']     = best_match.get('Face', {}).get('BoundingBox', {})
                result['face_count_selfie'] = 1
                result['face_count_doc']    = 1
            else:
                # No match found — check if faces detected at all
                source_face = response.get('SourceImageFace', {})
                result['face_in_selfie']    = bool(source_face)
                result['face_in_document']  = len(response.get('UnmatchedFaces', [])) > 0

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"AWS Rekognition face compare error: {e}")

        finally:
            result['processing_ms'] = int((time.time() - start) * 1000)
            if hasattr(selfie_file, 'seek'):   selfie_file.seek(0)
            if hasattr(document_file, 'seek'): document_file.seek(0)

        return result

    def detect_faces(self, image_file) -> dict:
        """Detect all faces in image + attributes."""
        start = time.time()
        result = {'faces': [], 'count': 0, 'processing_ms': 0, 'error': ''}
        try:
            client = self._get_client()
            if hasattr(image_file, 'seek'): image_file.seek(0)
            content  = image_file.read()
            response = client.detect_faces(
                Image={'Bytes': content},
                Attributes=['ALL'],
            )
            faces = response.get('FaceDetails', [])
            result['count'] = len(faces)
            result['faces'] = [{
                'confidence':    round(f.get('Confidence', 0) / 100, 4),
                'age_range':     f.get('AgeRange', {}),
                'eyes_open':     f.get('EyesOpen', {}).get('Value', None),
                'mouth_open':    f.get('MouthOpen', {}).get('Value', None),
                'smile':         f.get('Smile', {}).get('Value', None),
                'sunglasses':    f.get('Sunglasses', {}).get('Value', None),
                'face_occluded': f.get('FaceOccluded', {}).get('Value', None),
            } for f in faces]
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"AWS face detection error: {e}")
        finally:
            result['processing_ms'] = int((time.time() - start) * 1000)
        return result

    def check_liveness(self, image_file) -> dict:
        """
        Basic liveness check using face quality metrics.
        For full video liveness: use AWS Rekognition Face Liveness (separate service).
        """
        face_result = self.detect_faces(image_file)
        if not face_result['faces']:
            return {'is_live': False, 'score': 0.0, 'reason': 'No face detected'}

        face       = face_result['faces'][0]
        confidence = face['confidence']

        # Heuristic: sunglasses/occlusion = possibly spoofed
        is_live = (
            confidence > 0.95 and
            not face.get('sunglasses') and
            not face.get('face_occluded')
        )
        return {
            'is_live':    is_live,
            'score':      round(confidence, 4),
            'confidence': confidence,
            'face_count': face_result['count'],
        }


class AWSTextractOCR:
    """AWS Textract — Superior OCR for structured documents like IDs."""

    def __init__(self, region: str = 'ap-southeast-1'):
        self.region  = region
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('textract', region_name=self.region)
            except ImportError:
                raise ImportError("boto3 not installed. Run: pip install boto3")
        return self._client

    def extract_text(self, image_file) -> dict:
        """Extract text using AWS Textract."""
        start = time.time()
        result = {
            'raw_text': '', 'lines': [], 'key_values': {},
            'confidence': 0.0, 'provider': 'aws_textract',
            'processing_ms': 0, 'success': False, 'error': '',
        }
        try:
            client = self._get_client()
            if hasattr(image_file, 'seek'): image_file.seek(0)
            content  = image_file.read()

            response = client.detect_document_text(Document={'Bytes': content})
            blocks   = response.get('Blocks', [])

            lines = [b['Text'] for b in blocks if b['BlockType'] == 'LINE']
            confidences = [b.get('Confidence', 0)/100 for b in blocks if b['BlockType'] == 'WORD']

            result['raw_text']   = '\n'.join(lines)
            result['lines']      = lines
            result['confidence'] = round(sum(confidences)/len(confidences), 4) if confidences else 0.0
            result['success']    = True

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"AWS Textract error: {e}")
        finally:
            result['processing_ms'] = int((time.time() - start) * 1000)
        return result
