# =============================================================================
# promotions/offerwall/embed_generator.py
# Offerwall Embed Generator — JS snippet for publishers to embed
# =============================================================================
from django.conf import settings


class OfferwallEmbedGenerator:
    """Generate embed code for publisher's website."""

    def get_iframe_embed(self, publisher_id: int, width: str = '100%', height: str = '600px',
                         theme: str = 'light', category: str = '') -> str:
        base_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = f'pub={publisher_id}&theme={theme}'
        if category:
            params += f'&category={category}'
        return f'''<!-- Offerwall Embed - YourPlatform -->
<iframe
  src="{base_url}/offerwall/embed/?{params}"
  width="{width}"
  height="{height}"
  frameborder="0"
  scrolling="auto"
  allow="clipboard-write"
  style="border: none; border-radius: 8px; overflow: hidden;">
</iframe>
<!-- End Offerwall Embed -->'''

    def get_js_sdk_embed(self, publisher_id: int, container_id: str = 'offerwall',
                         theme: str = 'light') -> str:
        base_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return f'''<!-- Offerwall SDK Embed -->
<div id="{container_id}"></div>
<script>
(function(w, d, s, o, f, js, fjs) {{
  w[o] = w[o] || function() {{ (w[o].q = w[o].q || []).push(arguments) }};
  js = d.createElement(s); fjs = d.getElementsByTagName(s)[0];
  js.id = o; js.src = f; js.async = 1; fjs.parentNode.insertBefore(js, fjs);
}})(window, document, 'script', 'OW', '{base_url}/static/promotions/js/offerwall-sdk.js');

OW('init', {{
  publisherId: {publisher_id},
  container: '{container_id}',
  theme: '{theme}',
  apiBase: '{base_url}/api/promotions/',
  onConversion: function(offer) {{
    console.log('Conversion recorded:', offer);
  }},
  onError: function(err) {{
    console.error('Offerwall error:', err);
  }}
}});
</script>
<!-- End Offerwall SDK -->'''

    def get_all_embed_formats(self, publisher_id: int) -> dict:
        return {
            'iframe': self.get_iframe_embed(publisher_id),
            'javascript_sdk': self.get_js_sdk_embed(publisher_id),
            'publisher_id': publisher_id,
            'documentation_url': '/docs/offerwall/',
        }
