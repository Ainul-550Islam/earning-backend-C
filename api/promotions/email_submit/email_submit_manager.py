# =============================================================================
# promotions/email_submit/email_submit_manager.py
# Email Submit Campaign — CPAlead's highest volume offer type
# "Our exclusive Email Submits create direct advertiser relationships"
# User enters email → publisher earns $0.20-$2.00 instantly
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import hashlib, uuid, re, logging

logger = logging.getLogger(__name__)

DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'temp-mail.org',
    'throwaway.email', 'yopmail.com', '10minutemail.com',
    'fakeinbox.com', 'trashmail.com', 'sharklasers.com',
}

SINGLE_OPT_IN = 'SOI'    # User just enters email — instant payout
DOUBLE_OPT_IN = 'DOI'    # User must confirm email — higher payout


class EmailSubmitManager:
    """
    Email submit offer management.
    SOI: $0.20-$0.80 per email (instant, high volume)
    DOI: $0.80-$2.00 per confirmed email (slower, higher quality)
    """
    SUBMIT_PREFIX = 'email_submit:'
    DEDUP_PREFIX  = 'email_seen:'

    def create_email_submit_campaign(
        self,
        advertiser_id: int,
        campaign_name: str,
        opt_in_type: str,                # SOI or DOI
        payout: Decimal,
        target_countries: list = None,
        niche: str = 'general',          # general/finance/health/gaming
        daily_cap: int = 5000,
        redirect_url: str = '',          # Where to send user after submit
    ) -> dict:
        camp_id = str(uuid.uuid4())[:12]
        config = {
            'campaign_id': camp_id,
            'advertiser_id': advertiser_id,
            'campaign_name': campaign_name,
            'opt_in_type': opt_in_type,
            'payout': str(payout),
            'target_countries': target_countries or ['US', 'GB', 'CA', 'AU'],
            'niche': niche,
            'daily_cap': daily_cap,
            'today_submits': 0,
            'total_submits': 0,
            'redirect_url': redirect_url or '/thank-you/',
            'status': 'active',
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.SUBMIT_PREFIX}{camp_id}', config, timeout=3600 * 24 * 365)
        return {
            'campaign_id': camp_id,
            'opt_in_type': opt_in_type,
            'payout': str(payout),
            'embed_form': self._generate_form_html(camp_id, campaign_name, redirect_url),
            'api_endpoint': f'/api/promotions/email-submit/{camp_id}/submit/',
            'status': 'active',
        }

    def process_submit(
        self,
        campaign_id: str,
        email: str,
        publisher_id: int,
        country: str,
        ip: str,
        subid: str = '',
    ) -> dict:
        """Process email submission — validate, dedup, pay publisher."""

        # 1. Validate email format
        try:
            validate_email(email)
        except ValidationError:
            return {'accepted': False, 'reason': 'invalid_email'}

        # 2. Disposable email check
        domain = email.split('@')[-1].lower()
        if domain in DISPOSABLE_DOMAINS:
            return {'accepted': False, 'reason': 'disposable_email_detected'}

        # 3. Load campaign
        config = cache.get(f'{self.SUBMIT_PREFIX}{campaign_id}')
        if not config or config['status'] != 'active':
            return {'accepted': False, 'reason': 'campaign_inactive'}

        # 4. Daily cap check
        if config['today_submits'] >= config['daily_cap']:
            return {'accepted': False, 'reason': 'daily_cap_reached'}

        # 5. Country check
        if config['target_countries'] and country not in config['target_countries']:
            return {'accepted': False, 'reason': 'country_not_targeted'}

        # 6. Duplicate email check (global per campaign)
        email_hash = hashlib.sha256(f'{campaign_id}:{email.lower()}'.encode()).hexdigest()
        if cache.get(f'{self.DEDUP_PREFIX}{email_hash}'):
            return {'accepted': False, 'reason': 'duplicate_email'}

        # 7. Duplicate IP check (per day)
        ip_key = f'email_ip:{campaign_id}:{ip}:{timezone.now().date()}'
        if cache.get(ip_key):
            return {'accepted': False, 'reason': 'duplicate_ip_today'}

        # 8. Mark as seen
        cache.set(f'{self.DEDUP_PREFIX}{email_hash}', True, timeout=3600 * 24 * 365)
        cache.set(ip_key, True, timeout=3600 * 25)

        # 9. Update counters
        config['today_submits'] += 1
        config['total_submits'] += 1
        cache.set(f'{self.SUBMIT_PREFIX}{campaign_id}', config, timeout=3600 * 24 * 365)

        # 10. SOI = instant payout, DOI = pending until confirmation
        payout = Decimal(config['payout'])
        is_soi = config['opt_in_type'] == SINGLE_OPT_IN

        if is_soi:
            self._award_payout(publisher_id, campaign_id, payout, email_hash)
            payout_status = 'instant'
        else:
            # Send confirmation email and set pending state
            confirmation_token = self._create_doi_token(campaign_id, email_hash, publisher_id, payout)
            self._send_confirmation_email(email, confirmation_token, config['campaign_name'])
            payout_status = 'pending_confirmation'

        logger.info(f'Email submit: campaign={campaign_id} pub={publisher_id} type={config["opt_in_type"]} country={country}')

        return {
            'accepted': True,
            'opt_in_type': config['opt_in_type'],
            'payout_status': payout_status,
            'payout': str(payout) if is_soi else '0.00',
            'redirect_url': config['redirect_url'],
        }

    def confirm_doi(self, confirmation_token: str) -> dict:
        """Handle DOI email confirmation click."""
        token_data = cache.get(f'doi_token:{confirmation_token}')
        if not token_data:
            return {'confirmed': False, 'reason': 'token_expired'}
        if token_data.get('confirmed'):
            return {'confirmed': False, 'reason': 'already_confirmed'}
        token_data['confirmed'] = True
        token_data['confirmed_at'] = timezone.now().isoformat()
        cache.set(f'doi_token:{confirmation_token}', token_data, timeout=3600 * 24 * 7)
        # Award payout now
        self._award_payout(
            publisher_id=token_data['publisher_id'],
            campaign_id=token_data['campaign_id'],
            payout=Decimal(token_data['payout']),
            ref=confirmation_token,
        )
        return {'confirmed': True, 'payout': token_data['payout']}

    def get_email_submit_offers(self, country: str = 'US', limit: int = 10) -> list:
        """Get email submit offers for publisher offerwall."""
        # In production: query EmailSubmitCampaign model
        return [
            {
                'type': 'email_submit',
                'opt_in': 'SOI',
                'payout': '0.50',
                'description': 'Enter email to win!',
                'estimated_time': '30 seconds',
                'cta': 'Get Free Access',
            }
        ]

    def _award_payout(self, publisher_id: int, campaign_id: str, payout: Decimal, ref: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='reward',
                amount=payout,
                status='completed',
                notes=f'Email Submit — Campaign #{campaign_id[:8]}',
                metadata={'campaign_id': campaign_id, 'ref': ref, 'type': 'email_submit'},
            )
        except Exception as e:
            logger.error(f'Email submit payout failed: {e}')

    def _create_doi_token(self, campaign_id: str, email_hash: str, publisher_id: int, payout: Decimal) -> str:
        token = str(uuid.uuid4()).replace('-', '')
        cache.set(f'doi_token:{token}', {
            'campaign_id': campaign_id,
            'email_hash': email_hash,
            'publisher_id': publisher_id,
            'payout': str(payout),
            'confirmed': False,
            'created_at': timezone.now().isoformat(),
        }, timeout=3600 * 48)
        return token

    def _send_confirmation_email(self, email: str, token: str, campaign_name: str):
        from django.conf import settings
        from django.core.mail import send_mail
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        confirm_url = f'{base}/api/promotions/email-submit/confirm/{token}/'
        try:
            send_mail(
                subject=f'Confirm your email — {campaign_name}',
                message=f'Click to confirm: {confirm_url}',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourplatform.com'),
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f'DOI email send failed: {e}')

    def _generate_form_html(self, campaign_id: str, name: str, redirect: str) -> str:
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        return f'''<form class="email-submit-form" onsubmit="return submitEmail(event, '{campaign_id}')">
  <h3>{name}</h3>
  <input type="email" name="email" placeholder="Enter your email address" required>
  <button type="submit">Get Free Access →</button>
</form>
<script>
async function submitEmail(e, cid) {{
  e.preventDefault();
  const email = e.target.email.value;
  const r = await fetch('{base}/api/promotions/email-submit/' + cid + '/submit/', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{email, publisher_id: window.PUB_ID || 0}})
  }});
  const d = await r.json();
  if(d.accepted) window.location = d.redirect_url || '{redirect}';
  else alert('Please enter a valid email address.');
  return false;
}}
</script>'''


# ── Views ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def email_submit_view(request, campaign_id):
    """POST /api/promotions/email-submit/<campaign_id>/submit/"""
    import hashlib
    manager = EmailSubmitManager()
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    country = request.META.get('HTTP_CF_IPCOUNTRY', 'US')
    result = manager.process_submit(
        campaign_id=campaign_id,
        email=request.data.get('email', ''),
        publisher_id=int(request.data.get('publisher_id', 0)),
        country=country,
        ip=ip,
        subid=request.data.get('subid', ''),
    )
    return Response(result)


@api_view(['GET'])
@permission_classes([AllowAny])
def doi_confirm_view(request, token):
    """GET /api/promotions/email-submit/confirm/<token>/"""
    manager = EmailSubmitManager()
    result = manager.confirm_doi(token)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_email_submit_campaign_view(request):
    """POST /api/promotions/email-submit/create/"""
    manager = EmailSubmitManager()
    data = request.data
    result = manager.create_email_submit_campaign(
        advertiser_id=request.user.id,
        campaign_name=data.get('campaign_name', ''),
        opt_in_type=data.get('opt_in_type', 'SOI'),
        payout=Decimal(str(data.get('payout', '0.50'))),
        target_countries=data.get('target_countries', []),
        niche=data.get('niche', 'general'),
        daily_cap=int(data.get('daily_cap', 5000)),
        redirect_url=data.get('redirect_url', ''),
    )
    return Response(result, status=status.HTTP_201_CREATED)
