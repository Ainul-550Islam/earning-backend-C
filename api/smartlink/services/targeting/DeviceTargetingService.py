import logging
from ...choices import DeviceType, OSType, BrowserType

logger = logging.getLogger('smartlink.targeting.device')


class DeviceTargetingService:
    """User-Agent parse → device type → match targeting rule."""

    def matches(self, device_targeting, device_type: str) -> bool:
        if device_targeting is None:
            return True
        return device_targeting.matches(device_type)

    def parse_user_agent(self, user_agent: str) -> dict:
        """
        Parse User-Agent string into device_type, os, browser.
        Uses user-agents library for fast parsing.
        Returns dict with device_type, os, browser, is_mobile, is_bot.
        """
        result = {
            'device_type': DeviceType.UNKNOWN,
            'os': OSType.UNKNOWN,
            'browser': BrowserType.OTHER,
            'is_mobile': False,
            'is_tablet': False,
            'is_bot': False,
            'ua_string': user_agent,
        }

        if not user_agent:
            return result

        try:
            from user_agents import parse as ua_parse
            ua = ua_parse(user_agent)

            result['is_bot'] = ua.is_bot

            if ua.is_mobile:
                result['device_type'] = DeviceType.MOBILE
                result['is_mobile'] = True
            elif ua.is_tablet:
                result['device_type'] = DeviceType.TABLET
                result['is_tablet'] = True
            elif ua.is_pc:
                result['device_type'] = DeviceType.DESKTOP
            else:
                result['device_type'] = DeviceType.UNKNOWN

            # OS detection
            os_family = ua.os.family.lower()
            if 'android' in os_family:
                result['os'] = OSType.ANDROID
            elif 'ios' in os_family or 'iphone' in os_family or 'ipad' in os_family:
                result['os'] = OSType.IOS
            elif 'windows' in os_family:
                result['os'] = OSType.WINDOWS
            elif 'mac' in os_family or 'macos' in os_family:
                result['os'] = OSType.MAC
            elif 'linux' in os_family:
                result['os'] = OSType.LINUX

            # Browser detection
            browser_family = ua.browser.family.lower()
            if 'chrome' in browser_family and 'edge' not in browser_family:
                result['browser'] = BrowserType.CHROME
            elif 'firefox' in browser_family:
                result['browser'] = BrowserType.FIREFOX
            elif 'safari' in browser_family and 'chrome' not in browser_family:
                result['browser'] = BrowserType.SAFARI
            elif 'edge' in browser_family:
                result['browser'] = BrowserType.EDGE
            elif 'opera' in browser_family:
                result['browser'] = BrowserType.OPERA

        except Exception as e:
            logger.debug(f"UA parse error: {e}")

        return result
