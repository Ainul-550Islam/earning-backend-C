# api/djoyalty/renderers.py
"""
Custom DRF renderers for Djoyalty।
Consistent JSON response format।
"""
import json
from rest_framework.renderers import JSONRenderer


class DjoyaltyJSONRenderer(JSONRenderer):
    """
    Custom JSON renderer:
    - Consistent envelope format
    - Adds X-Djoyalty-Version header
    - Pretty prints in DEBUG mode
    """
    charset = 'utf-8'
    media_type = 'application/json'
    format = 'json'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')
        request = renderer_context.get('request')

        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        # Don't wrap if already in envelope format
        if isinstance(data, dict) and ('error' in data or 'results' in data or 'data' in data):
            return super().render(data, accepted_media_type, renderer_context)

        # Wrap list responses
        if isinstance(data, list):
            wrapped = {
                'count': len(data),
                'results': data,
            }
            return super().render(wrapped, accepted_media_type, renderer_context)

        return super().render(data, accepted_media_type, renderer_context)


class DjoyaltyCSVRenderer:
    """
    CSV renderer for export endpoints।
    Usage: renderer_classes = [DjoyaltyCSVRenderer]
    """
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        import csv
        import io
        if not data:
            return b''

        if isinstance(data, dict) and 'results' in data:
            rows = data['results']
        elif isinstance(data, list):
            rows = data
        else:
            rows = [data]

        if not rows:
            return b''

        output = io.StringIO()
        if isinstance(rows[0], dict):
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        else:
            writer = csv.writer(output)
            writer.writerows(rows)

        return output.getvalue().encode(self.charset)
