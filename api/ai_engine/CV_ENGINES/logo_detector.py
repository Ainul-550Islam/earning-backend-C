"""
api/ai_engine/CV_ENGINES/logo_detector.py
==========================================
Logo Detector — brand logos detect ও identify।
Ad creative brand safety, competitor detection।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class LogoDetector:
    """Logo detection and brand identification।"""

    KNOWN_BRANDS = [
        "bkash", "nagad", "rocket", "upay", "dbbl", "dutch-bangla",
        "grameenphone", "robi", "banglalink", "teletalk",
        "facebook", "google", "youtube", "instagram", "whatsapp",
        "amazon", "alibaba", "daraz", "shohoz", "pathao",
    ]

    def detect(self, image_path: str = None,
               image_base64: str = None) -> dict:
        """Image এ logos detect করো।"""
        try:
            return self._google_vision_detect(image_path or image_base64)
        except Exception:
            pass
        try:
            return self._openai_vision_detect(image_path or image_base64)
        except Exception as e:
            logger.error(f"Logo detection failed: {e}")
            return {"logos": [], "brands": [], "count": 0}

    def _google_vision_detect(self, image_ref: str) -> dict:
        """Google Vision API logo detection।"""
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            if image_ref.startswith("http"):
                image = vision.Image(source=vision.ImageSource(image_uri=image_ref))
            else:
                with open(image_ref, "rb") as f:
                    content = f.read()
                image = vision.Image(content=content)
            response = client.logo_detection(image=image)
            logos = [{
                "name":       a.description,
                "confidence": round(a.score, 4),
                "known_brand": a.description.lower() in self.KNOWN_BRANDS,
            } for a in response.logo_annotations]
            return {"logos": logos, "brands": [l["name"] for l in logos],
                    "count": len(logos), "method": "google_vision"}
        except ImportError:
            raise Exception("google-cloud-vision not installed")

    def _openai_vision_detect(self, image_ref: str) -> dict:
        """OpenAI Vision logo detection fallback।"""
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client = OpenAIIntegration()
        prompt = "Identify all brand logos visible in this image. List each logo name, one per line."
        result = client.vision_analyze(image_ref, prompt)
        content = result.get("content", "")
        logos = []
        for line in content.strip().split("\n"):
            name = line.strip().strip("-").strip()
            if name:
                logos.append({
                    "name": name,
                    "confidence": 0.75,
                    "known_brand": name.lower() in self.KNOWN_BRANDS,
                })
        return {"logos": logos, "brands": [l["name"] for l in logos],
                "count": len(logos), "method": "openai_vision"}

    def check_brand_safety(self, image_path: str,
                            prohibited_brands: List[str] = None) -> dict:
        """Ad creative তে prohibited brands আছে কিনা check।"""
        prohibited = prohibited_brands or ["competitor_brand"]
        result = self.detect(image_path=image_path)
        detected_brands = [b.lower() for b in result.get("brands", [])]
        violations = [b for b in prohibited if b.lower() in detected_brands]
        return {
            "is_safe":        len(violations) == 0,
            "detected_brands": result.get("brands", []),
            "violations":      violations,
            "approved":        len(violations) == 0,
        }

    def batch_detect(self, image_paths: List[str]) -> List[Dict]:
        """Multiple images এর logos detect।"""
        return [{"image": p, **self.detect(image_path=p)} for p in image_paths]
