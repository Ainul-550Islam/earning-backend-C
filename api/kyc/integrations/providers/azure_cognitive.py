# kyc/integrations/providers/azure_cognitive.py  ── WORLD #1
"""
Azure Cognitive Services — OCR + Face API.
Setup: pip install azure-cognitiveservices-vision-computervision azure-cognitiveservices-vision-face
Credentials: AZURE_VISION_KEY, AZURE_VISION_ENDPOINT env vars.
"""
import logging, time
logger = logging.getLogger(__name__)


class AzureVisionOCR:
    """Azure Computer Vision OCR."""

    def __init__(self):
        import os
        self.key      = os.getenv('AZURE_VISION_KEY', '')
        self.endpoint = os.getenv('AZURE_VISION_ENDPOINT', '')

    def extract_text(self, image_file) -> dict:
        result = {'raw_text':'','confidence':0.0,'provider':'azure_vision','success':False,'error':'','processing_ms':0}
        start  = time.time()
        try:
            from azure.cognitiveservices.vision.computervision import ComputerVisionClient
            from msrest.authentication import CognitiveServicesCredentials
            import io

            client = ComputerVisionClient(self.endpoint, CognitiveServicesCredentials(self.key))
            if hasattr(image_file,'seek'): image_file.seek(0)
            stream   = io.BytesIO(image_file.read())
            response = client.read_in_stream(stream, raw=True)

            # Poll for result
            import re, time as t
            op_id = re.search(r'operationId=(.+)', response.headers.get('Operation-Location','')).group(1)
            t.sleep(1)
            read_result = client.get_read_result(op_id)
            lines = []
            for page in read_result.analyze_result.read_results:
                for line in page.lines:
                    lines.append(line.text)
            result['raw_text'] = '\n'.join(lines)
            result['success']  = True
            result['confidence'] = 0.90
        except ImportError:
            result['error'] = 'azure-cognitiveservices not installed. Run: pip install azure-cognitiveservices-vision-computervision'
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Azure Vision OCR error: {e}")
        finally:
            result['processing_ms'] = int((time.time()-start)*1000)
        return result


class AzureFaceAPI:
    """Azure Face API — face detection and verification."""

    def __init__(self):
        import os
        self.key      = os.getenv('AZURE_FACE_KEY', '')
        self.endpoint = os.getenv('AZURE_FACE_ENDPOINT', '')

    def compare_faces(self, selfie_file, doc_file) -> dict:
        result = {'is_matched':False,'confidence':0.0,'provider':'azure_face','error':'','processing_ms':0}
        start  = time.time()
        try:
            from azure.cognitiveservices.vision.face import FaceClient
            from msrest.authentication import CognitiveServicesCredentials
            import io

            client = FaceClient(self.endpoint, CognitiveServicesCredentials(self.key))
            if hasattr(selfie_file,'seek'): selfie_file.seek(0)
            if hasattr(doc_file,'seek'):    doc_file.seek(0)

            s1 = client.face.detect_with_stream(io.BytesIO(selfie_file.read()))
            s2 = client.face.detect_with_stream(io.BytesIO(doc_file.read()))
            if not s1 or not s2:
                result['error'] = 'Face not detected in one or both images'
                return result

            verify = client.face.verify_face_to_face(s1[0].face_id, s2[0].face_id)
            result['is_matched']  = verify.is_identical
            result['confidence']  = round(verify.confidence, 4)
            result['match_confidence'] = round(verify.confidence, 4)
        except ImportError:
            result['error'] = 'azure-cognitiveservices-vision-face not installed.'
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Azure Face API error: {e}")
        finally:
            result['processing_ms'] = int((time.time()-start)*1000)
        return result
