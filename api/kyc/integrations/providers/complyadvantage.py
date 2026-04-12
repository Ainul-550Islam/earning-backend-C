# kyc/integrations/providers/complyadvantage.py  ── WORLD #1
"""
ComplyAdvantage — Real AML/PEP/Sanctions screening.
World's most comprehensive risk data (500M+ profiles, 1B+ records).
Pricing: ~$0.10-$0.50 per search.
Setup: Get API key at https://complyadvantage.com
"""
import logging, time
from django.conf import settings
logger = logging.getLogger(__name__)


class ComplyAdvantageClient:
    BASE_URL = 'https://api.complyadvantage.com'

    def __init__(self):
        self.api_key = getattr(settings, 'COMPLYADVANTAGE_API_KEY', '')

    def search(self, name: str, dob: str = None, country: str = None,
               entity_type: str = 'person') -> dict:
        """
        Full AML/PEP/Sanctions search.
        entity_type: 'person' | 'company'
        """
        result = {
            'is_pep':          False,
            'is_sanctioned':   False,
            'is_adverse_media': False,
            'match_count':     0,
            'match_score':     0.0,
            'matches':         [],
            'provider':        'complyadvantage',
            'search_id':       '',
            'status':          'clear',
            'error':           '',
            'processing_ms':   0,
        }
        start = time.time()

        if not self.api_key:
            result['error'] = 'COMPLYADVANTAGE_API_KEY not set in settings'
            return result

        try:
            import requests
            payload = {
                'search_term':   name,
                'fuzziness':     0.6,
                'entity_type':   entity_type,
                'filters': {
                    'types': ['sanction', 'warning', 'fitness-probity', 'pep',
                              'pep-class-1', 'pep-class-2', 'pep-class-3', 'pep-class-4',
                              'adverse-media', 'adverse-media-financial-crime',
                              'adverse-media-fraud', 'adverse-media-general'],
                },
            }
            if dob:
                payload['filters']['birth_year'] = dob[:4] if len(dob) >= 4 else None
            if country:
                payload['filters']['country_codes'] = [country[:2].upper()]

            headers = {
                'Authorization': f'Token {self.api_key}',
                'Content-Type': 'application/json',
            }
            resp = requests.post(
                f'{self.BASE_URL}/searches',
                json=payload,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            search_data = data.get('content', {}).get('data', {})
            result['search_id'] = str(search_data.get('id', ''))
            hits = search_data.get('hits', [])

            for hit in hits:
                doc   = hit.get('doc', {})
                types = doc.get('types', [])
                score = hit.get('score', 0) * 100

                if any(t in types for t in ['sanction']):
                    result['is_sanctioned'] = True
                if any(t.startswith('pep') for t in types):
                    result['is_pep'] = True
                if any(t.startswith('adverse-media') for t in types):
                    result['is_adverse_media'] = True

                result['matches'].append({
                    'name':        doc.get('name', ''),
                    'types':       types,
                    'score':       round(score, 1),
                    'entity_type': doc.get('entity_type', ''),
                    'source':      doc.get('sources', []),
                })

            result['match_count'] = len(hits)
            result['match_score'] = max((h.get('score', 0)*100 for h in hits), default=0.0)
            result['status']      = 'hit' if hits else 'clear'

        except ImportError:
            result['error'] = 'requests not installed'
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"ComplyAdvantage error: {e}")

        finally:
            result['processing_ms'] = int((time.time() - start) * 1000)

        return result

    def get_search(self, search_id: str) -> dict:
        """Retrieve a previous search result."""
        try:
            import requests
            resp = requests.get(
                f'{self.BASE_URL}/searches/{search_id}',
                headers={'Authorization': f'Token {self.api_key}'},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {'error': str(e)}
