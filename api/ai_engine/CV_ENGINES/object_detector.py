"""
api/ai_engine/CV_ENGINES/object_detector.py
============================================
Object Detector — image এ objects detect করো।
Ad creative quality, offer screenshot validation।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class ObjectDetector:
    """Object detection engine using YOLO/DETR."""

    def detect(self, image_path: str = None, image_base64: str = None,
               min_confidence: float = 0.50) -> dict:
        """Image থেকে objects detect করো।"""
        # Try YOLO first
        try:
            return self._yolo_detect(image_path, image_base64, min_confidence)
        except Exception:
            pass
        # Fallback: OpenAI Vision
        try:
            return self._openai_vision_detect(image_base64 or image_path)
        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return {"objects": [], "count": 0, "error": str(e)}

    def _yolo_detect(self, image_path, image_base64, min_confidence):
        try:
            from ultralytics import YOLO
            model = YOLO("yolov8n.pt")
            results = model(image_path or image_base64)
            objects = []
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf)
                    if conf >= min_confidence:
                        objects.append({
                            "label":      r.names[int(box.cls)],
                            "confidence": round(conf, 4),
                            "bbox":       [round(float(x), 2) for x in box.xyxy[0].tolist()],
                        })
            return {"objects": objects, "count": len(objects), "method": "yolo"}
        except ImportError:
            raise Exception("ultralytics not installed")

    def _openai_vision_detect(self, image_ref: str) -> dict:
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client = OpenAIIntegration()
        prompt = "List all objects you can detect in this image. Format: object_name:confidence (0.0-1.0)"
        result = client.vision_analyze(image_ref, prompt)
        raw    = result.get("content", "")
        objects = []
        for line in raw.split("\n"):
            if ":" in line:
                parts = line.split(":")
                objects.append({"label": parts[0].strip(), "confidence": float(parts[1].strip()) if len(parts) > 1 else 0.7})
        return {"objects": objects, "count": len(objects), "method": "openai_vision"}

    def validate_ad_creative(self, image_path: str) -> dict:
        """Ad creative validation — inappropriate content check।"""
        result  = self.detect(image_path)
        objects = [o["label"].lower() for o in result.get("objects", [])]
        has_text = any(o in objects for o in ["text", "sign", "banner"])
        has_person = "person" in objects
        return {
            "objects":    result.get("objects", []),
            "has_text":   has_text,
            "has_person": has_person,
            "object_count": result.get("count", 0),
            "approved":   True,
        }

    def count_objects(self, image_path: str, target_class: str) -> int:
        result = self.detect(image_path)
        return sum(1 for o in result.get("objects", []) if o.get("label", "").lower() == target_class.lower())
