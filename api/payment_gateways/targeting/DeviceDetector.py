# api/payment_gateways/targeting/DeviceDetector.py
import re

UA_REGEXES = {
    'bot':        r'(bot|crawl|slurp|spider|facebookexternalhit|WhatsApp|Googlebot|bingbot)',
    'tablet':     r'(iPad|Android.*Tablet|Kindle|Silk|PlayBook|Nexus 10)',
    'mobile':     r'(Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Mobile)',
    'ios':        r'(iPhone|iPad|iPod)',
    'android':    r'Android',
    'windows':    r'Windows NT',
    'macos':      r'(Macintosh|Mac OS X)',
    'chrome':     r'Chrome',
    'safari':     r'Safari',
    'firefox':    r'Firefox',
    'edge':       r'Edge',
}


class DeviceDetector:
    def detect(self, user_agent: str) -> dict:
        ua = user_agent or ''
        return {
            'device_type': self._device_type(ua),
            'os_name':     self._os(ua),
            'browser':     self._browser(ua),
            'is_bot':      bool(re.search(UA_REGEXES['bot'], ua, re.I)),
        }

    def _device_type(self, ua: str) -> str:
        if re.search(UA_REGEXES['bot'],    ua, re.I): return 'bot'
        if re.search(UA_REGEXES['tablet'], ua, re.I): return 'tablet'
        if re.search(UA_REGEXES['mobile'], ua, re.I): return 'mobile'
        return 'desktop'

    def _os(self, ua: str) -> str:
        if re.search(UA_REGEXES['ios'],     ua, re.I): return 'iOS'
        if re.search(UA_REGEXES['android'], ua, re.I): return 'Android'
        if re.search(UA_REGEXES['windows'], ua, re.I): return 'Windows'
        if re.search(UA_REGEXES['macos'],   ua, re.I): return 'macOS'
        return 'Other'

    def _browser(self, ua: str) -> str:
        if re.search(UA_REGEXES['edge'],    ua, re.I): return 'Edge'
        if re.search(UA_REGEXES['chrome'],  ua, re.I): return 'Chrome'
        if re.search(UA_REGEXES['firefox'], ua, re.I): return 'Firefox'
        if re.search(UA_REGEXES['safari'],  ua, re.I): return 'Safari'
        return 'Other'
