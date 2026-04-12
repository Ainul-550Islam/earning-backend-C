# kyc/aml/screening_service.py  ── WORLD #1
"""
AML Screening Service — PEP + Sanctions + Adverse Media.
Supports: ComplyAdvantage, Refinitiv World-Check, Mock (dev/test).
"""
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class AMLScreeningService:
    """
    World #1 AML screening engine.
    Run after every KYC submission and periodically thereafter.
    """

    def __init__(self, provider: str = 'mock'):
        self.provider = provider

    def screen(self, kyc) -> 'ScreeningResult':
        """
        Main entry point.
        Returns ScreeningResult with PEP/sanctions/adverse media flags.
        """
        name    = kyc.full_name or kyc.extracted_name or ''
        dob     = kyc.date_of_birth
        country = kyc.country or 'Bangladesh'
        nid     = kyc.document_number or ''

        if self.provider == 'complyadvantage':
            return self._screen_complyadvantage(name, dob, country, nid)
        elif self.provider == 'refinitiv':
            return self._screen_refinitiv(name, dob, country, nid)
        else:
            return self._screen_local(name, dob, country, nid)

    # ── Providers ────────────────────────────────────────────

    def _screen_complyadvantage(self, name, dob, country, nid) -> 'ScreeningResult':
        """ComplyAdvantage API integration."""
        try:
            import requests
            from django.conf import settings

            api_key = getattr(settings, 'COMPLYADVANTAGE_API_KEY', '')
            if not api_key:
                logger.warning("COMPLYADVANTAGE_API_KEY not set — falling back to local")
                return self._screen_local(name, dob, country, nid)

            payload = {
                'search_term':    name,
                'fuzziness':      0.6,
                'filters': {
                    'types': ['sanction', 'pep', 'warning', 'adverse-media'],
                    'birth_year': dob.year if dob else None,
                },
            }
            headers = {'Authorization': f'Token {api_key}', 'Content-Type': 'application/json'}
            resp = requests.post(
                'https://api.complyadvantage.com/searches',
                json=payload, headers=headers, timeout=10
            )
            resp.raise_for_status()
            data  = resp.json()
            hits  = data.get('content', {}).get('data', {}).get('hits', [])
            return self._parse_complyadvantage_result(hits, data)
        except Exception as e:
            logger.error(f"ComplyAdvantage screening failed: {e}")
            return ScreeningResult(error=str(e))

    def _screen_refinitiv(self, name, dob, country, nid) -> 'ScreeningResult':
        """Refinitiv World-Check API integration."""
        try:
            import requests
            from django.conf import settings

            base_url = getattr(settings, 'REFINITIV_API_URL', '')
            api_key  = getattr(settings, 'REFINITIV_API_KEY', '')
            if not base_url or not api_key:
                return self._screen_local(name, dob, country, nid)

            payload = {
                'entityType': 'INDIVIDUAL',
                'name':       name,
                'dateOfBirth': str(dob) if dob else '',
                'countryCode': country[:2].upper(),
            }
            resp = requests.post(
                f'{base_url}/v1/search',
                json=payload,
                headers={'X-API-Key': api_key},
                timeout=15
            )
            resp.raise_for_status()
            return self._parse_refinitiv_result(resp.json())
        except Exception as e:
            logger.error(f"Refinitiv screening failed: {e}")
            return ScreeningResult(error=str(e))

    def _screen_local(self, name, dob, country, nid) -> 'ScreeningResult':
        """
        Local DB screening against cached sanctions + PEP lists.
        Fast, free, works offline.
        """
        from .models import SanctionsList, PEPDatabase

        result = ScreeningResult(provider='local')
        matches = []

        # ── Sanctions check ───────────────────────────────
        for entry in SanctionsList.objects.filter(is_active=True):
            score = self._name_similarity(name, entry.entry_name)
            if score >= 0.80:
                result.is_sanctioned = True
                matches.append({
                    'type':        'sanctions',
                    'list':        entry.source,
                    'matched_name': entry.entry_name,
                    'score':       round(score * 100, 1),
                })

            # Check aliases
            for alias in (entry.aliases or []):
                alias_score = self._name_similarity(name, alias)
                if alias_score >= 0.80:
                    result.is_sanctioned = True
                    matches.append({
                        'type':        'sanctions_alias',
                        'list':        entry.source,
                        'matched_name': alias,
                        'score':       round(alias_score * 100, 1),
                    })

        # ── PEP check ────────────────────────────────────
        for pep in PEPDatabase.objects.filter(is_current=True):
            score = self._name_similarity(name, pep.full_name)
            if score >= 0.80:
                result.is_pep = True
                matches.append({
                    'type':        'pep',
                    'category':    pep.category,
                    'matched_name': pep.full_name,
                    'position':    pep.position,
                    'country':     pep.country,
                    'score':       round(score * 100, 1),
                })

            for alias in (pep.aliases or []):
                alias_score = self._name_similarity(name, alias)
                if alias_score >= 0.80:
                    result.is_pep = True
                    matches.append({
                        'type':        'pep_alias',
                        'category':    pep.category,
                        'matched_name': alias,
                        'score':       round(alias_score * 100, 1),
                    })

        result.matches     = matches
        result.match_count = len(matches)
        result.match_score = max((m['score'] for m in matches), default=0.0)
        result.status      = 'hit' if matches else 'clear'
        return result

    # ── Parsers ───────────────────────────────────────────

    def _parse_complyadvantage_result(self, hits, raw) -> 'ScreeningResult':
        result = ScreeningResult(provider='complyadvantage', raw_response=raw)
        for hit in hits:
            doc  = hit.get('doc', {})
            types = doc.get('types', [])
            score = hit.get('score', 0) * 100
            if 'sanction' in types:
                result.is_sanctioned = True
            if 'pep' in types:
                result.is_pep = True
            if 'adverse-media' in types:
                result.is_adverse_media = True
            result.matches.append({'type': types, 'name': doc.get('name',''), 'score': score})
        result.match_count = len(hits)
        result.match_score = max((h.get('score',0)*100 for h in hits), default=0.0)
        result.status      = 'hit' if hits else 'clear'
        return result

    def _parse_refinitiv_result(self, data) -> 'ScreeningResult':
        result  = ScreeningResult(provider='refinitiv', raw_response=data)
        results = data.get('results', [])
        for r in results:
            category = r.get('category', '')
            if 'SANCTION' in category.upper():   result.is_sanctioned = True
            if 'PEP'      in category.upper():   result.is_pep = True
            result.matches.append({'category': category, 'name': r.get('primaryName','')})
        result.match_count = len(results)
        result.status      = 'hit' if results else 'clear'
        return result

    def _name_similarity(self, name1: str, name2: str) -> float:
        if not name1 or not name2: return 0.0
        return SequenceMatcher(
            None, name1.strip().lower(), name2.strip().lower()
        ).ratio()

    def save_result(self, kyc, result: 'ScreeningResult'):
        """Persist screening result to DB."""
        from .models import PEPSanctionsScreening
        screening = PEPSanctionsScreening.objects.create(
            kyc=kyc,
            user=kyc.user,
            tenant=getattr(kyc, 'tenant', None),
            provider=result.provider,
            status=result.status,
            screened_name=kyc.full_name or '',
            screened_dob=kyc.date_of_birth,
            screened_country=kyc.country or '',
            screened_nid=kyc.document_number or '',
            is_pep=result.is_pep,
            is_sanctioned=result.is_sanctioned,
            is_adverse_media=result.is_adverse_media,
            match_count=result.match_count,
            match_score=result.match_score,
            matches=result.matches,
            raw_response=result.raw_response,
            error=result.error or '',
        )
        # Update KYC risk score if hit found
        if result.is_sanctioned or result.is_pep:
            kyc.risk_score = min(100, kyc.risk_score + 50)
            kyc.risk_factors = list(set(kyc.risk_factors or []) | {'pep_or_sanctions_hit'})
            kyc.save(update_fields=['risk_score', 'risk_factors', 'updated_at'])
        return screening


class ScreeningResult:
    def __init__(self, provider='mock', raw_response=None, error=None):
        self.provider        = provider
        self.status          = 'clear'
        self.is_pep          = False
        self.is_sanctioned   = False
        self.is_adverse_media = False
        self.match_count     = 0
        self.match_score     = 0.0
        self.matches         = []
        self.raw_response    = raw_response or {}
        self.error           = error or ''

    @property
    def is_clear(self):   return not (self.is_pep or self.is_sanctioned or self.is_adverse_media)
    @property
    def is_hit(self):     return not self.is_clear

    def to_dict(self):
        return {
            'provider':         self.provider,
            'status':           self.status,
            'is_pep':           self.is_pep,
            'is_sanctioned':    self.is_sanctioned,
            'is_adverse_media': self.is_adverse_media,
            'match_count':      self.match_count,
            'match_score':      self.match_score,
        }
