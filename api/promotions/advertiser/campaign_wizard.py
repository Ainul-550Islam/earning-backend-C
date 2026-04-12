# =============================================================================
# promotions/advertiser/campaign_wizard.py
# Campaign Creation Wizard — Step-by-step campaign builder
# MaxBounty / CPAlead style campaign setup
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class CampaignWizard:
    """
    Multi-step campaign creation:
    Step 1: Basic info (title, description, category)
    Step 2: Offer details (reward, proof type, steps)
    Step 3: Targeting (geo, device, OS)
    Step 4: Budget & Schedule
    Step 5: Review & Submit
    """
    WIZARD_PREFIX = 'campaign_wizard:'
    WIZARD_TTL = 3600 * 2  # 2 hours to complete wizard

    def __init__(self, advertiser_id: int):
        self.advertiser_id = advertiser_id
        self.wizard_key = f'{self.WIZARD_PREFIX}{advertiser_id}'

    def start_wizard(self) -> dict:
        """Initialize a new campaign wizard session."""
        session = {
            'advertiser_id': self.advertiser_id,
            'current_step': 1,
            'total_steps': 5,
            'started_at': timezone.now().isoformat(),
            'step_1': {},
            'step_2': {},
            'step_3': {},
            'step_4': {},
            'completed': False,
        }
        cache.set(self.wizard_key, session, timeout=self.WIZARD_TTL)
        return self._step_response(session, step=1)

    def save_step(self, step: int, data: dict) -> dict:
        """Save data for a wizard step."""
        session = cache.get(self.wizard_key, {})
        if not session:
            return {'error': 'Wizard session expired. Please start again.'}
        validators = {
            1: self._validate_step1,
            2: self._validate_step2,
            3: self._validate_step3,
            4: self._validate_step4,
        }
        if step in validators:
            errors = validators[step](data)
            if errors:
                return {'error': errors, 'step': step}
        session[f'step_{step}'] = data
        session['current_step'] = min(step + 1, 5)
        cache.set(self.wizard_key, session, timeout=self.WIZARD_TTL)
        return self._step_response(session, step=session['current_step'])

    def submit_campaign(self) -> dict:
        """Final step: create the campaign in DB."""
        session = cache.get(self.wizard_key, {})
        if not session:
            return {'error': 'Wizard session expired'}
        try:
            campaign = self._create_campaign_from_session(session)
            cache.delete(self.wizard_key)
            return {
                'success': True,
                'campaign_id': campaign.id,
                'campaign_title': campaign.title,
                'status': campaign.status,
                'message': 'Campaign submitted for review. Expected approval within 24 hours.',
                'next_steps': [
                    'Fund your campaign budget via Advertiser > Billing',
                    'Track performance in your Advertiser Dashboard',
                    'Our team will review and approve within 24 hours',
                ],
            }
        except Exception as e:
            return {'error': str(e)}

    def get_current_state(self) -> dict:
        session = cache.get(self.wizard_key, {})
        if not session:
            return {'error': 'No active wizard session'}
        return self._step_response(session, step=session.get('current_step', 1))

    def _validate_step1(self, data: dict) -> str:
        if not data.get('title') or len(data['title']) < 5:
            return 'Campaign title must be at least 5 characters'
        if not data.get('category'):
            return 'Category is required'
        return None

    def _validate_step2(self, data: dict) -> str:
        try:
            reward = Decimal(str(data.get('per_task_reward', '0')))
            if reward < Decimal('0.01'):
                return 'Per task reward must be at least $0.01'
        except Exception:
            return 'Invalid reward amount'
        if not data.get('proof_type'):
            return 'Proof type is required'
        return None

    def _validate_step3(self, data: dict) -> str:
        return None  # Targeting is optional

    def _validate_step4(self, data: dict) -> str:
        try:
            budget = Decimal(str(data.get('total_budget', '0')))
            if budget < Decimal('10.00'):
                return 'Minimum campaign budget is $10.00'
        except Exception:
            return 'Invalid budget amount'
        return None

    def _step_response(self, session: dict, step: int) -> dict:
        step_info = {
            1: {'name': 'Basic Info', 'fields': ['title', 'description', 'category', 'platform']},
            2: {'name': 'Offer Details', 'fields': ['per_task_reward', 'proof_type', 'steps', 'max_tasks_per_user']},
            3: {'name': 'Targeting', 'fields': ['target_countries', 'target_devices', 'target_os']},
            4: {'name': 'Budget & Schedule', 'fields': ['total_budget', 'daily_budget', 'start_date', 'end_date']},
            5: {'name': 'Review & Submit', 'fields': []},
        }
        return {
            'current_step': step,
            'total_steps': 5,
            'step_info': step_info.get(step, {}),
            'saved_data': session,
            'progress_pct': round((step - 1) / 5 * 100),
        }

    def _create_campaign_from_session(self, session: dict):
        from api.promotions.models import Campaign, PromotionCategory, RewardPolicy
        s1 = session.get('step_1', {})
        s2 = session.get('step_2', {})
        s4 = session.get('step_4', {})
        cat = PromotionCategory.objects.get(id=s1.get('category'))
        rp, _ = RewardPolicy.objects.get_or_create(
            name=f'Auto Policy {self.advertiser_id}',
            defaults={
                'base_reward': Decimal(str(s2.get('per_task_reward', '1.00'))),
                'min_reward': Decimal('0.01'),
                'max_reward': Decimal('1000.00'),
                'platform_commission_rate': Decimal('0.20'),
            }
        )
        campaign = Campaign.objects.create(
            title=s1.get('title', ''),
            description=s1.get('description', ''),
            advertiser_id=self.advertiser_id,
            category=cat,
            reward_policy=rp,
            per_task_reward=Decimal(str(s2.get('per_task_reward', '1.00'))),
            max_tasks_per_user=int(s2.get('max_tasks_per_user', 1)),
            total_budget=Decimal(str(s4.get('total_budget', '100.00'))),
            status='pending',
        )
        return campaign


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wizard_start_view(request):
    wizard = CampaignWizard(advertiser_id=request.user.id)
    return Response(wizard.start_wizard(), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wizard_step_view(request, step):
    wizard = CampaignWizard(advertiser_id=request.user.id)
    result = wizard.save_step(step=int(step), data=request.data)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wizard_submit_view(request):
    wizard = CampaignWizard(advertiser_id=request.user.id)
    result = wizard.submit_campaign()
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wizard_state_view(request):
    wizard = CampaignWizard(advertiser_id=request.user.id)
    return Response(wizard.get_current_state())
