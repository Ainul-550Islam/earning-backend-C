"""AD_CREATIVES/creative_manager.py — Creative asset lifecycle manager."""
from ..models import AdCreative
from ..services import CreativeService


class CreativeManager:
    @staticmethod
    def get_approved(ad_unit_id: int, creative_type: str = None):
        return CreativeService.get_approved_for_unit(ad_unit_id, creative_type)

    @staticmethod
    def approve(creative_id: int, reviewed_by=None):
        c = AdCreative.objects.get(pk=creative_id)
        return CreativeService.approve(c, reviewed_by)

    @staticmethod
    def reject(creative_id: int, reason: str, reviewed_by=None):
        c = AdCreative.objects.get(pk=creative_id)
        return CreativeService.reject(c, reason, reviewed_by)

    @staticmethod
    def pending():
        return AdCreative.objects.filter(status="pending").select_related("ad_unit")

    @staticmethod
    def archive(creative_id: int):
        return AdCreative.objects.filter(pk=creative_id).update(status="archived")

    @staticmethod
    def duplicate(creative_id: int) -> AdCreative:
        original = AdCreative.objects.get(pk=creative_id)
        original.pk         = None
        original.creative_id = None
        original.status     = "draft"
        original.impressions = 0
        original.clicks      = 0
        original.revenue     = 0
        original.save()
        return original
