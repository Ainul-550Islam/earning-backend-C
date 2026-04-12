"""ISP Analysis — extracts and categorises ISP connection type data."""
from django.core.cache import cache

HOSTING_KEYWORDS    = ['hosting','server','vps','cloud','dedicated','datacenter',
                        'data center','colocation','colo','cdn','leaseweb','ovh',
                        'hetzner','digitalocean','linode','vultr','choopa']
MOBILE_KEYWORDS     = ['mobile','wireless','cellular','telecom','4g','lte',
                        'mvno','carrier','grameenphone','robi','banglalink',
                        'teletalk','airtel','vodafone','t-mobile','at&t']
RESIDENTIAL_KEYWORDS= ['broadband','dsl','fiber','cable','home','residential',
                        'internet service','comcast','verizon','cox','charter']
VPN_KEYWORDS        = ['vpn','nordvpn','expressvpn','mullvad','protonvpn',
                        'surfshark','cyberghost','pia','ipvanish','windscribe']


class ISPAnalyzer:
    def __init__(self, isp: str = '', org: str = '', asn: str = '',
                 connection_type: str = ''):
        self.raw_isp = isp
        self.raw_org = org
        self.asn = asn
        self.connection_type = connection_type.lower()
        self.combined = (isp + ' ' + org).lower()

    def analyze(self) -> dict:
        cache_key = f"pi:isp:{self.asn}:{self.raw_isp[:15]}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = {
            'isp':             self.raw_isp,
            'organization':    self.raw_org,
            'asn':             self.asn,
            'connection_type': self._classify(),
            'is_hosting':      self._check(HOSTING_KEYWORDS),
            'is_mobile':       self._check(MOBILE_KEYWORDS),
            'is_residential':  self._check(RESIDENTIAL_KEYWORDS),
            'is_vpn_isp':      self._check(VPN_KEYWORDS),
            'risk_contribution': self._risk(),
        }
        cache.set(cache_key, result, 3600)
        return result

    def _classify(self) -> str:
        if self.connection_type: return self.connection_type
        if self._check(HOSTING_KEYWORDS):    return 'hosting'
        if self._check(MOBILE_KEYWORDS):     return 'mobile'
        if self._check(RESIDENTIAL_KEYWORDS): return 'residential'
        if self._check(VPN_KEYWORDS):        return 'vpn'
        return 'unknown'

    def _check(self, keywords: list) -> bool:
        return any(kw in self.combined for kw in keywords)

    def _risk(self) -> int:
        if self._check(VPN_KEYWORDS):     return 25
        if self._check(HOSTING_KEYWORDS): return 10
        if self._check(MOBILE_KEYWORDS):  return 5
        return 0
