"""
api/ai_engine/CV_ENGINES/image_classifier.py
=============================================
Image Classifier — multi-class image classification।
Ad creative categorization, offer screenshot analysis।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class ImageClassifier:
    """Image classification engine।"""

    CATEGORIES = [
        "offer_screenshot", "product_photo", "banner_ad",
        "person", "logo", "text_heavy", "nature", "food",
        "gaming", "app_screenshot", "other",
    ]

    def classify(self, image_path: str = None, image_base64: str = None,
                 top_k: int = 3) -> dict:
        """Image classify করো।"""
        try:
            return self._torchvision_classify(image_path, top_k)
        except Exception:
            try:
                return self._openai_vision_classify(image_path or image_base64, top_k)
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                return {"predictions": [], "top_class": "unknown", "confidence": 0.0}

    def _torchvision_classify(self, image_path: str, top_k: int) -> dict:
        import torch
        from torchvision import transforms, models
        from PIL import Image
        model = models.resnet50(pretrained=True)
        model.eval()
        preprocess = transforms.Compose([
            transforms.Resize(256), transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225]),
        ])
        img    = Image.open(image_path).convert("RGB")
        tensor = preprocess(img).unsqueeze(0)
        with torch.no_grad():
            output = model(tensor)
            probs  = torch.nn.functional.softmax(output[0], dim=0)
            top    = torch.topk(probs, top_k)
        predictions = [{"class_id": int(idx), "confidence": round(float(prob), 4)}
                       for prob, idx in zip(top.values, top.indices)]
        return {"predictions": predictions, "top_class": str(predictions[0]["class_id"]),
                "confidence": predictions[0]["confidence"], "method": "resnet50"}

    def _openai_vision_classify(self, image_ref: str, top_k: int) -> dict:
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client = OpenAIIntegration()
        categories_str = ", ".join(self.CATEGORIES)
        prompt = f"Classify this image into one of these categories: {categories_str}. Return the category name and confidence (0.0-1.0) as: category:confidence"
        result = client.vision_analyze(image_ref, prompt)
        content = result.get("content", "")
        if ":" in content:
            parts = content.strip().split(":")
            cat  = parts[0].strip()
            conf = float(parts[1].strip()) if len(parts) > 1 else 0.7
        else:
            cat, conf = content.strip() or "other", 0.6
        return {"predictions": [{"class": cat, "confidence": round(conf, 4)}],
                "top_class": cat, "confidence": round(conf, 4), "method": "openai_vision"}

    def batch_classify(self, image_paths: List[str]) -> List[Dict]:
        return [{"image": p, **self.classify(image_path=p)} for p in image_paths]

    def is_appropriate(self, image_path: str) -> dict:
        """Content appropriateness check।"""
        result = self.classify(image_path, top_k=5)
        inappropriate = ["adult", "violence", "gore", "explicit"]
        top = result.get("top_class", "").lower()
        is_ok = not any(bad in top for bad in inappropriate)
        return {"appropriate": is_ok, "top_class": top, "confidence": result.get("confidence", 0)}
