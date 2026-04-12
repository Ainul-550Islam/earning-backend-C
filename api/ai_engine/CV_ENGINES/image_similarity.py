"""
api/ai_engine/CV_ENGINES/image_similarity.py
=============================================
Image Similarity — দুটো image কতটা similar সেটা measure করো।
Duplicate image detection, brand safety, plagiarism।
"""
import logging, math
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class ImageSimilarity:
    """Image similarity measurement engine।"""

    def compare(self, image_a: str, image_b: str,
                method: str = "perceptual") -> dict:
        """দুটো image compare করো।"""
        if method == "perceptual":
            return self._perceptual_hash(image_a, image_b)
        elif method == "embedding":
            return self._embedding_similarity(image_a, image_b)
        return self._perceptual_hash(image_a, image_b)

    def _perceptual_hash(self, img_a: str, img_b: str) -> dict:
        """pHash based similarity।"""
        try:
            from PIL import Image
            import imagehash
            hash_a = imagehash.phash(Image.open(img_a))
            hash_b = imagehash.phash(Image.open(img_b))
            diff   = hash_a - hash_b
            similarity = max(0.0, 1.0 - diff / 64.0)
            return {
                "similarity": round(similarity, 4),
                "distance":   diff,
                "is_duplicate": similarity >= 0.95,
                "is_similar":   similarity >= 0.80,
                "method": "perceptual_hash",
            }
        except ImportError:
            logger.warning("Pillow or imagehash not installed — using fallback")
            return {"similarity": 0.5, "method": "fallback", "error": "library missing"}

    def _embedding_similarity(self, img_a: str, img_b: str) -> dict:
        """CLIP embedding based similarity।"""
        try:
            import torch
            from PIL import Image
            from transformers import CLIPProcessor, CLIPModel
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            images = [Image.open(img_a), Image.open(img_b)]
            inputs = processor(images=images, return_tensors="pt")
            with torch.no_grad():
                features = model.get_image_features(**inputs)
            f_a, f_b = features[0], features[1]
            cos_sim = float(torch.nn.functional.cosine_similarity(f_a.unsqueeze(0), f_b.unsqueeze(0)))
            return {"similarity": round(cos_sim, 4), "method": "clip_embedding",
                    "is_duplicate": cos_sim >= 0.98, "is_similar": cos_sim >= 0.85}
        except Exception as e:
            logger.error(f"Embedding similarity error: {e}")
            return {"similarity": 0.5, "method": "error", "error": str(e)}

    def find_duplicates(self, image_paths: List[str],
                        threshold: float = 0.95) -> List[Dict]:
        """Image list এ duplicates খুঁজো।"""
        duplicates = []
        for i in range(len(image_paths)):
            for j in range(i + 1, len(image_paths)):
                result = self.compare(image_paths[i], image_paths[j])
                if result.get("similarity", 0) >= threshold:
                    duplicates.append({
                        "image_a": image_paths[i],
                        "image_b": image_paths[j],
                        "similarity": result["similarity"],
                    })
        return duplicates

    def cosine_similarity_vectors(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Vector cosine similarity utility।"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot  = sum(a * b for a, b in zip(vec_a, vec_b))
        na   = math.sqrt(sum(a**2 for a in vec_a))
        nb   = math.sqrt(sum(b**2 for b in vec_b))
        return round(dot / (na * nb), 6) if na and nb else 0.0
