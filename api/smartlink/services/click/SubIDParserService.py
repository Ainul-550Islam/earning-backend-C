import logging
from ...utils import sanitize_sub_id
from ...constants import MAX_SUB_PARAMS, MAX_CUSTOM_PARAMS

logger = logging.getLogger('smartlink.sub_id')


class SubIDParserService:
    """
    Parse sub1-sub5 tracking parameters from request context.
    Sanitizes values and builds clean sub ID dict for click metadata.
    """

    # Standard sub ID parameter names accepted from URL
    SUB_PARAMS = ['sub1', 'sub2', 'sub3', 'sub4', 'sub5']
    ALIAS_MAP = {
        # Common aliases used by traffic sources
        's1': 'sub1', 's2': 'sub2', 's3': 'sub3', 's4': 'sub4', 's5': 'sub5',
        'source': 'sub1', 'campaign': 'sub2', 'adgroup': 'sub3',
        'keyword': 'sub4', 'placement': 'sub5',
        'aff_sub': 'sub1', 'aff_sub2': 'sub2', 'aff_sub3': 'sub3',
        'aff_sub4': 'sub4', 'aff_sub5': 'sub5',
    }

    def parse(self, context: dict) -> dict:
        """
        Parse sub IDs from request context.

        Args:
            context: request context dict, may include sub1-sub5, query_params dict, etc.

        Returns:
            {
                'sub1': str, 'sub2': str, ..., 'sub5': str,
                'custom': {'param_name': 'value', ...}
            }
        """
        result = {f'sub{i}': '' for i in range(1, MAX_SUB_PARAMS + 1)}
        custom = {}

        # Direct sub1-sub5 from context
        for param in self.SUB_PARAMS:
            val = context.get(param, '')
            if val:
                result[param] = sanitize_sub_id(str(val))

        # Check aliases
        query_params = context.get('query_params', {})
        for alias, target in self.ALIAS_MAP.items():
            if alias in query_params and not result[target]:
                result[target] = sanitize_sub_id(str(query_params[alias]))

        # Collect extra custom params (not sub1-sub5)
        reserved = set(self.SUB_PARAMS) | set(self.ALIAS_MAP.keys()) | {
            'ip', 'user_agent', 'country', 'region', 'city', 'device_type',
            'os', 'browser', 'isp', 'asn', 'language', 'referrer',
            'is_fraud', 'is_bot', 'fraud_score', 'final_url',
        }
        count = 0
        for k, v in query_params.items():
            if k not in reserved and count < MAX_CUSTOM_PARAMS:
                custom[sanitize_sub_id(k)] = sanitize_sub_id(str(v))
                count += 1

        result['custom'] = custom
        return result

    def build_url_params(self, sub_ids: dict) -> dict:
        """
        Convert sub ID dict back to URL query parameters.
        Used by URLBuilderService to append to offer URL.
        """
        params = {}
        for i in range(1, MAX_SUB_PARAMS + 1):
            key = f'sub{i}'
            if sub_ids.get(key):
                params[key] = sub_ids[key]
        return params
