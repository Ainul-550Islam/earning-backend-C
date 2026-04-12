# api/promotions/tracking/utm_builder.py
# UTM Parameter Builder & Parser
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

@dataclass
class UTMParams:
    source: str; medium: str; campaign: str; term: str = ''; content: str = ''

class UTMBuilder:
    def build(self, url: str, params: UTMParams) -> str:
        utm = {'utm_source': params.source, 'utm_medium': params.medium, 'utm_campaign': params.campaign}
        if params.term:    utm['utm_term']    = params.term
        if params.content: utm['utm_content'] = params.content
        p = urlparse(url); q = parse_qs(p.query); q.update({k: [v] for k, v in utm.items()})
        return urlunparse(p._replace(query=urlencode({k: v[0] if isinstance(v,list) else v for k,v in q.items()})))

    def for_campaign(self, campaign_id: int, name: str, platform: str, url: str) -> str:
        return self.build(url, UTMParams(platform.lower(), 'cpc', f'{campaign_id}_{name[:30].replace(" ","_").lower()}'))

    def parse(self, url: str) -> UTMParams | None:
        q = parse_qs(urlparse(url).query)
        s = q.get('utm_source', [None])[0]
        return None if not s else UTMParams(s, q.get('utm_medium',[''])[0], q.get('utm_campaign',[''])[0],
               q.get('utm_term',[''])[0], q.get('utm_content',[''])[0])
