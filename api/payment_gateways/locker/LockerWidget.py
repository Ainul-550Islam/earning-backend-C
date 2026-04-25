# api/payment_gateways/locker/LockerWidget.py
# Generates embeddable JavaScript widget code for content lockers & offerwalls

from django.conf import settings


class LockerWidget:
    """
    Generates JavaScript embed code for publisher websites.

    Generates:
        1. Content locker script (locks URL/file/overlay)
        2. Offerwall widget (inline or popup)
        3. SmartLink button (one-click monetization)
        4. Android SDK config

    Output:
        - JavaScript snippet for <head> or <body>
        - JSON configuration object
        - Full HTML example page

    Usage:
        widget = LockerWidget()
        code   = widget.generate_locker_script(locker)
        embed  = widget.generate_offerwall_embed(offerwall, user_id='{{user_id}}')
    """

    CDN_URL = getattr(settings, 'LOCKER_CDN_URL', 'https://cdn.yourdomain.com/locker')

    def generate_locker_script(self, locker, placement: str = 'body') -> str:
        """
        Generate JavaScript embed code for a content locker.

        Args:
            locker:    ContentLocker instance
            placement: 'head' | 'body' (where to embed)

        Returns:
            str: JavaScript code to embed on publisher's page
        """
        config = {
            'key':           locker.locker_key,
            'type':          locker.locker_type,
            'title':         locker.title,
            'description':   locker.description,
            'theme':         locker.theme,
            'primaryColor':  locker.primary_color,
            'logoUrl':       locker.logo_url,
            'offerCount':    locker.show_offer_count,
            'unlockDuration':locker.unlock_duration_hours,
        }

        import json
        config_json = json.dumps(config, indent=2)

        script = f'''<!-- {locker.name} — Content Locker by YourDomain.com -->
<script>
  window.__LOCKER_CONFIG__ = {config_json};
</script>
<script src="{self.CDN_URL}/locker.min.js" async></script>'''

        if locker.locker_type == 'overlay':
            script += f'''
<style>
  .locker-overlay {{ display: none; }}
  body.locker-active .locker-overlay {{ display: flex; }}
  {locker.overlay_selector or '.protected-content'} {{ 
    filter: blur(8px); 
    pointer-events: none; 
    user-select: none;
  }}
  body.locker-unlocked {locker.overlay_selector or '.protected-content'} {{
    filter: none;
    pointer-events: auto;
    user-select: auto;
  }}
</style>'''

        return script

    def generate_locker_html_example(self, locker) -> str:
        """Generate a full HTML example page showing how to use the locker."""
        script = self.generate_locker_script(locker)
        example = f'''<!DOCTYPE html>
<html>
<head>
  <title>Locker Example — {locker.name}</title>
  {script if 'head' in locker.locker_type else ''}
</head>
<body>

<!-- YOUR CONTENT HERE -->
<div class="{locker.overlay_selector.lstrip('.') if locker.overlay_selector else 'protected-content'}">
  <h1>Premium Content</h1>
  <p>This content is locked. Complete an offer to unlock.</p>
</div>

<!-- LOCKER EMBED (add before closing body tag) -->
{script}

</body>
</html>'''
        return example

    def generate_offerwall_embed(self, offerwall, user_id: str = '{{USER_ID}}',
                                   container_id: str = 'offerwall-container',
                                   height: int = 600) -> str:
        """
        Generate embeddable offerwall widget code.

        Args:
            offerwall:     OfferWall instance
            user_id:       Publisher's user ID (replace with actual user ID)
            container_id:  HTML element ID to render into
            height:        Widget height in pixels

        Returns:
            str: JavaScript + HTML embed code
        """
        import json
        config = {
            'wallKey':       offerwall.wall_key,
            'userId':        user_id,
            'currencyName':  offerwall.currency_name,
            'exchangeRate':  float(offerwall.exchange_rate),
            'primaryColor':  offerwall.primary_color,
            'theme':         offerwall.theme,
            'containerId':   container_id,
            'height':        height,
            'postbackUrl':   offerwall.postback_url,
        }
        config_json = json.dumps(config)

        return f'''<!-- {offerwall.name} — OfferWall by YourDomain.com -->
<div id="{container_id}" style="width:100%;height:{height}px;"></div>
<script>
  window.__OFFERWALL_CONFIG__ = {config_json};
</script>
<script src="{self.CDN_URL}/offerwall.min.js" async></script>

<!-- 
  HOW IT WORKS:
  1. Replace {user_id} with your user's actual ID
  2. User completes an offer  
  3. We fire your postback URL: {offerwall.postback_url}?user_id={{user_id}}&amount={{amount}}&currency={offerwall.currency_name}
  4. You credit the user in your system
-->'''

    def generate_android_sdk_config(self, offerwall) -> dict:
        """
        Generate Android SDK configuration JSON.
        Publisher integrates this in their Android app.
        """
        return {
            'sdk_version':    '2.0',
            'wall_key':       offerwall.wall_key,
            'app_id':         offerwall.android_app_id,
            'currency_name':  offerwall.currency_name,
            'exchange_rate':  float(offerwall.exchange_rate),
            'postback_url':   offerwall.postback_url,
            'api_endpoint':   f'https://yourdomain.com/api/payment/locker/offerwalls/offers/{offerwall.wall_key}/',
            'user_id_param':  offerwall.android_user_id_param,
            'theme':          offerwall.theme,
            'primary_color':  offerwall.primary_color,
            'integration_guide': {
                'step1': f'Add to build.gradle: implementation "com.yourdomain:offerwall:{offerwall.wall_key}"',
                'step2': 'Initialize: OfferWall.init(context, config)',
                'step3': 'Show: OfferWall.show(activity, userId)',
                'step4': 'Handle reward: OfferWall.setRewardCallback((reward) -> creditUser(reward.amount))',
            },
            'generated_at': __import__('django.utils.timezone', fromlist=['timezone']).timezone.now().isoformat(),
        }

    def generate_smartlink_button(self, smart_link, button_text: str = 'Earn Rewards',
                                   button_style: str = 'default') -> str:
        """
        Generate a SmartLink button embed for publishers.
        One click monetization — no offer selection needed.
        """
        STYLES = {
            'default': 'background:#635BFF;color:white;padding:12px 24px;border:none;border-radius:6px;font-size:16px;cursor:pointer;',
            'green':   'background:#3B6D11;color:white;padding:12px 24px;border:none;border-radius:6px;font-size:16px;cursor:pointer;',
            'black':   'background:#111;color:white;padding:12px 24px;border:none;border-radius:6px;font-size:16px;cursor:pointer;',
        }
        style = STYLES.get(button_style, STYLES['default'])

        return f'''<!-- SmartLink Button — {smart_link.name} -->
<a href="{smart_link.url}" target="_blank" rel="noopener">
  <button style="{style}">{button_text}</button>
</a>
<!-- URL: {smart_link.url} -->
<!-- Auto-routes visitor to best offer for their country/device -->'''
