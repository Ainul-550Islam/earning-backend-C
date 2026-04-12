import logging

logger = logging.getLogger('smartlink.targeting.os')


class OSTargetingService:
    """OS type targeting: Android, iOS, Windows, Mac, Linux."""

    def matches(self, os_targeting, os_type: str) -> bool:
        if os_targeting is None:
            return True
        return os_targeting.matches(os_type)
