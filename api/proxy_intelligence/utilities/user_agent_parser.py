"""User-Agent Parser — extracts browser/OS/device from UA strings."""
import re
from typing import Optional

class UserAgentParser:
    def __init__(self, user_agent: str):
        self.ua = user_agent

    def parse(self) -> dict:
        return {
            'browser':        self._browser(),
            'browser_version': self._browser_version(),
            'os':             self._os(),
            'device_type':    self._device_type(),
            'is_mobile':      self._is_mobile(),
            'is_bot':         self._is_bot(),
            'is_headless':    self._is_headless(),
            'raw':            self.ua[:500],
        }

    def _browser(self) -> str:
        if 'Firefox/' in self.ua:   return 'Firefox'
        if 'Edg/' in self.ua:       return 'Edge'
        if 'OPR/' in self.ua:       return 'Opera'
        if 'Chrome/' in self.ua:    return 'Chrome'
        if 'Safari/' in self.ua:    return 'Safari'
        if 'MSIE' in self.ua or 'Trident' in self.ua: return 'IE'
        return 'Unknown'

    def _browser_version(self) -> str:
        m = re.search(r'(?:Chrome|Firefox|Safari|Edg|OPR)/(\d+\.\d+)', self.ua)
        return m.group(1) if m else ''

    def _os(self) -> str:
        if 'Windows' in self.ua:  return 'Windows'
        if 'Android' in self.ua:  return 'Android'
        if 'iPhone' in self.ua:   return 'iOS'
        if 'iPad' in self.ua:     return 'iPadOS'
        if 'Mac OS' in self.ua:   return 'macOS'
        if 'Linux' in self.ua:    return 'Linux'
        return 'Unknown'

    def _device_type(self) -> str:
        ua_lower = self.ua.lower()
        if any(k in ua_lower for k in ['iphone','android','mobile']): return 'mobile'
        if any(k in ua_lower for k in ['ipad','tablet']): return 'tablet'
        return 'desktop'

    def _is_mobile(self) -> bool:
        return self._device_type() in ('mobile', 'tablet')

    def _is_bot(self) -> bool:
        return bool(re.search(
            r'bot|crawler|spider|scraper|curl|wget|python|java|go-http',
            self.ua, re.I
        ))

    def _is_headless(self) -> bool:
        return bool(re.search(
            r'headlesschrome|phantomjs|selenium|puppeteer|playwright',
            self.ua, re.I
        ))
