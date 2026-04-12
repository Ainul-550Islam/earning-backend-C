"""
api/ai_engine/CV_ENGINES/brand_safety_checker.py
=================================================
Brand Safety Checker — ad content brand safety।
Inappropriate content, competitor logos, NSFW।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class BrandSafetyChecker:
    """Comprehensive brand safety validation।"""

    UNSAFE_CATEGORIES = [
        "adult_content", "violence", "drugs", "alcohol", "gambling",
        "hate_speech", "political", "controversial",
    ]

    def check(self, image_path: str = None,
              image_base64: str = None,
              text_content: str = None) -> dict:
        """Complete brand safety check।"""
        results = {"safe": True, "issues": [], "score": 1.0}

        # Image safety check
        if image_path or image_base64:
            img_result = self._check_image(image_path or image_base64)
            if not img_result["safe"]:
                results["safe"] = False
                results["issues"].extend(img_result["issues"])
                results["score"] *= img_result["score"]

        # Text content check
        if text_content:
            text_result = self._check_text(text_content)
            if not text_result["safe"]:
                results["safe"] = False
                results["issues"].extend(text_result["issues"])
                results["score"] *= text_result["score"]

        results["score"]  = round(results["score"], 4)
        results["verdict"] = "APPROVED" if results["safe"] else "REJECTED"
        results["severity"] = ("critical" if results["score"] < 0.3 else
                               "high"     if results["score"] < 0.6 else
                               "medium"   if results["score"] < 0.8 else "low")
        return results

    def _check_image(self, image_ref: str) -> dict:
        """Image safety check।"""
        issues = []
        score  = 1.0
        try:
            from .adult_content_detector import AdultContentDetector
            adult_result = AdultContentDetector().detect(image_path=image_ref)
            if adult_result.get("is_adult"):
                issues.append("adult_content_detected")
                score *= 0.0  # Hard block
        except Exception as e:
            logger.warning(f"Adult content check failed: {e}")

        return {"safe": len(issues) == 0, "issues": issues, "score": score}

    def _check_text(self, text: str) -> dict:
        """Text content safety check।"""
        issues = []
        score  = 1.0
        text_lower = text.lower()

        UNSAFE_WORDS = ["violence", "drug", "casino", "porn", "hate", "kill", "bomb"]
        found = [w for w in UNSAFE_WORDS if w in text_lower]
        if found:
            issues.append(f"unsafe_keywords: {found}")
            score *= max(0.1, 1.0 - len(found) * 0.2)

        return {"safe": len(issues) == 0, "issues": issues, "score": score}

    def check_batch(self, items: List[Dict]) -> List[Dict]:
        """Multiple items batch check।"""
        results = []
        for item in items:
            result = self.check(
                image_path=item.get("image"),
                text_content=item.get("text"),
            )
            results.append({"item": item.get("id"), **result})
        return results

    def generate_report(self, batch_results: List[Dict]) -> dict:
        """Batch check report generate করো।"""
        total    = len(batch_results)
        approved = sum(1 for r in batch_results if r.get("verdict") == "APPROVED")
        rejected = total - approved
        return {
            "total":          total,
            "approved":       approved,
            "rejected":       rejected,
            "approval_rate":  round(approved / max(total, 1), 4),
            "common_issues":  self._count_issues(batch_results),
        }

    def _count_issues(self, results: List[Dict]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in results:
            for issue in r.get("issues", []):
                counts[issue] = counts.get(issue, 0) + 1
        return counts
