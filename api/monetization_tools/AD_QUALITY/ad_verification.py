"""AD_QUALITY/ad_verification.py — Ad content verification."""
from ..models import AdCreative


class AdVerificationEngine:
    REQUIRED_FIELDS = {
        "image":  ["asset_url", "width", "height"],
        "video":  ["asset_url", "duration_sec"],
        "native": ["headline", "cta_text", "advertiser_name"],
        "html5":  ["asset_url"],
        "vast":   ["asset_url"],
    }

    @classmethod
    def verify(cls, creative: AdCreative) -> dict:
        errors  = []
        ctype   = creative.creative_type
        req     = cls.REQUIRED_FIELDS.get(ctype, [])
        for field in req:
            if not getattr(creative, field, None):
                errors.append(f"Missing required field: {field}")
        if creative.file_size_kb and creative.file_size_kb > 5120:
            errors.append("File size exceeds 5MB.")
        return {"passed": len(errors) == 0, "errors": errors, "creative_type": ctype}

    @classmethod
    def auto_screen(cls, creative_id: int) -> dict:
        try:
            c = AdCreative.objects.get(pk=creative_id)
        except AdCreative.DoesNotExist:
            return {"passed": False, "errors": ["Creative not found"]}
        result = cls.verify(c)
        if not result["passed"]:
            AdCreative.objects.filter(pk=creative_id).update(status="rejected",
                                                               rejection_reason="; ".join(result["errors"]))
        return result
