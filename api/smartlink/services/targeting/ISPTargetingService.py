import logging

logger = logging.getLogger('smartlink.targeting.isp')


class ISPTargetingService:
    """Carrier/ISP detection and targeting evaluation."""

    def matches(self, isp_targeting, isp_name: str = '', asn: str = '') -> bool:
        if isp_targeting is None:
            return True
        return isp_targeting.matches(isp_name=isp_name, asn=asn)
