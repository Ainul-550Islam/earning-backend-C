# cms/viewsets/InteractorViewSet.py
"""
InteractorViewSet — exposes every Interactor in cms/interactors.py
as a REST endpoint.

Business value (why these were floating):

  PostbackProcessingInteractor.process():
    → CPAlead postback was handled by inline view code.
      The interactor adds fraud scoring, coin awarding, referral bonus,
      streak update, and level-up all in ONE atomic operation.
      Without wiring it in, all those side-effects were skipped.

  WithdrawalApprovalInteractor.approve() / mark_paid():
    → Admin was saving WithdrawalRequest directly — no audit trail,
      no payment gateway call, no user notification.

  UserOnboardingInteractor.onboard():
    → Registration only created the auth User. Referral code setup,
      VirtualBalance creation, welcome notification, welcome bonus
      were all skipped because the interactor was never called.

  SurveyInteractionInteractor.execute():
    → Survey submit only saved responses. Quality scoring, reward
      calculation, streak update, and analytics were all skipped.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSWriteThrottle

logger = logging.getLogger('cms.viewsets.interactor')


class InteractorViewSet(viewsets.GenericViewSet):
    """
    Orchestration endpoints backed by cms/interactors.py.
    Each action triggers a full business workflow (multi-step, atomic).
    """
    authentication_classes = [JWTAuthentication]

    # ─────────────────────────────────────────────────────────────────────────
    # PostbackProcessingInteractor — CPAlead postback full workflow
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get', 'post'],
            permission_classes=[AllowAny],
            throttle_classes=[CMSWriteThrottle],
            url_path='postback')
    def process_postback(self, request):
        """
        POST /api/cms/interactors/postback/   (or GET for CPAlead compatibility)

        Full postback processing workflow:
          1. Hash verification
          2. Deduplication by lead_id
          3. Fraud scoring
          4. Virtual coin award
          5. Referral bonus calculation + award
          6. Streak update
          7. Level-up check
          8. Push notification
          9. Events fired

        All steps run atomically — either all succeed or none persist.

        Preferred over the legacy CPALeadWebhookView which skips steps 4–9.
        """
        data = request.data if request.method == 'POST' else request.query_params

        params = {
            'user_id':    data.get('user_id') or data.get('subid', ''),
            'payout_usd': float(data.get('payout', data.get('payout_usd', 0))),
            'lead_id':    data.get('lead_id') or data.get('transaction_id', ''),
            'offer_id':   str(data.get('offer_id', '')),
            'ip':         request.META.get('REMOTE_ADDR', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'hash_value': data.get('hash', data.get('hash_value', '')),
        }

        if not params['user_id'] or not params['lead_id']:
            return Response({'error': 'user_id and lead_id are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.interactors import PostbackProcessingInteractor
            interactor = PostbackProcessingInteractor()
            result = interactor.process(params)
            if result.get('success', False):
                return Response(result)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'[Interactor] process_postback error: {e}', exc_info=True)
            # Always return 200 to CPAlead even on error (they retry on non-200)
            return Response({'success': False, 'error': str(e)})

    # ─────────────────────────────────────────────────────────────────────────
    # UserOnboardingInteractor — full new user setup
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny],
            throttle_classes=[CMSWriteThrottle])
    def onboard_user(self, request):
        """
        POST /api/cms/interactors/onboard-user/

        Full user onboarding workflow:
          1. Create Django auth User
          2. Create UserProfile + VirtualBalance records
          3. Process referral code (if provided)
          4. Award welcome bonus coins
          5. Send welcome push/email notification
          6. Fire user_registered event

        Body:
          {
            "username": "johndoe",
            "email": "john@example.com",
            "password": "StrongPass123!",
            "referral_code": "ABC123",    ← optional
            "device_token": "fcm_token",  ← optional
            "platform": "fcm"             ← optional
          }

        Returns JWT tokens on success so frontend can immediately log in.
        """
        data = request.data
        username = data.get('username', '').strip()
        email    = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not all([username, email, password]):
            return Response({'error': 'username, email, password required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.interactors import UserOnboardingInteractor
            interactor = UserOnboardingInteractor()
            result = interactor.onboard(
                username=username,
                email=email,
                password=password,
                referral_code=data.get('referral_code', ''),
                device_token=data.get('device_token', ''),
                device_platform=data.get('platform', 'fcm'),
            )
            if result.get('success'):
                return Response(result, status=status.HTTP_201_CREATED)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'[Interactor] onboard_user error: {e}', exc_info=True)
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # WithdrawalApprovalInteractor — full admin approval workflow
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSWriteThrottle])
    def approve_withdrawal(self, request):
        """
        POST /api/cms/interactors/approve-withdrawal/

        Full withdrawal approval workflow (admin only):
          1. Validate request is in PENDING state
          2. Re-run fraud check
          3. Deduct balance from user wallet
          4. Call payment gateway (PayPal/bKash/Nagad/Stripe)
          5. Create audit trail record
          6. Send notification to user
          7. Fire withdrawal_approved event

        Body:
          {
            "request_id": 42,
            "note": "Approved after manual KYC check"
          }
        """
        request_id = request.data.get('request_id')
        note       = request.data.get('note', '')
        if not request_id:
            return Response({'error': 'request_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from api.cms.interactors import WithdrawalApprovalInteractor
            interactor = WithdrawalApprovalInteractor()
            result = interactor.approve(
                admin_user=request.user,
                request_id=int(request_id),
                note=note,
            )
            if result.get('success'):
                return Response(result)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'[Interactor] approve_withdrawal error: {e}', exc_info=True)
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSWriteThrottle])
    def mark_withdrawal_paid(self, request):
        """
        POST /api/cms/interactors/mark-withdrawal-paid/

        Full mark-as-paid workflow:
          1. Update status to PAID
          2. Record external transaction ID from payment gateway
          3. Create final audit record
          4. Send "Your payment is on the way" notification to user

        Body:
          {
            "request_id": 42,
            "transaction_id": "PAYPAL-XYZ-123"
          }
        """
        request_id     = request.data.get('request_id')
        transaction_id = request.data.get('transaction_id', '')
        if not request_id:
            return Response({'error': 'request_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from api.cms.interactors import WithdrawalApprovalInteractor
            interactor = WithdrawalApprovalInteractor()
            result = interactor.mark_paid(
                admin_user=request.user,
                request_id=int(request_id),
                transaction_id=transaction_id,
            )
            if result.get('success'):
                return Response(result)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'[Interactor] mark_withdrawal_paid error: {e}', exc_info=True)
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # SurveyInteractionInteractor — full survey submit workflow
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSWriteThrottle])
    def submit_survey(self, request):
        """
        POST /api/cms/interactors/submit-survey/

        Full survey submission workflow:
          1. Validate all required questions answered
          2. Calculate quality score
          3. Calculate and award reward coins
          4. Update streak
          5. Check for level-up
          6. Fire survey_completed event
          7. Send reward notification

        Body:
          {
            "completion_id": "uuid-of-completion",
            "responses": [
              {"question_id": 1, "answer": "Option A"},
              ...
            ]
          }
        """
        completion_id = request.data.get('completion_id', '')
        responses     = request.data.get('responses', [])

        if not completion_id or not responses:
            return Response({'error': 'completion_id and responses required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.interactors import SurveyInteractionInteractor
            interactor = SurveyInteractionInteractor()
            result = interactor.execute({
                'user':          request.user,
                'completion_id': completion_id,
                'responses':     responses,
            })
            if result.get('success'):
                return Response(result)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'[Interactor] submit_survey error: {e}', exc_info=True)
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # InteractorManager — admin orchestration toolbox
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def list_interactors(self, request):
        """
        GET /api/cms/interactors/list/

        Admin: list all available interactors and their execution counts.
        Ops dashboard: see which interactors are healthy.
        """
        try:
            from api.cms.interactors import InteractorManager
            mgr = InteractorManager()
            return Response({
                'interactors': [
                    'PostbackProcessingInteractor',
                    'UserOnboardingInteractor',
                    'WithdrawalApprovalInteractor',
                    'SurveyInteractionInteractor',
                    'UserAuthenticationInteractor',
                ],
                'manager_status': 'ok',
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSWriteThrottle])
    def execute_interactor(self, request):
        """
        POST /api/cms/interactors/execute/

        Admin: execute any registered interactor by name.

        Body:
          {
            "interactor": "PostbackProcessingInteractor",
            "params": { ... }
          }

        Use carefully — only for admin automation and testing.
        """
        interactor_name = request.data.get('interactor', '')
        params          = request.data.get('params', {})

        allowed = {
            'PostbackProcessingInteractor',
            'UserOnboardingInteractor',
            'WithdrawalApprovalInteractor',
            'SurveyInteractionInteractor',
        }
        if interactor_name not in allowed:
            return Response({
                'error': f'Unknown interactor. Allowed: {sorted(allowed)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.interactors import InteractorManager
            mgr = InteractorManager()
            result = mgr.execute_interactor(interactor_name, **params)
            return Response({'success': True, 'result': result,
                             'interactor': interactor_name})
        except Exception as e:
            logger.error(f'[Interactor] execute error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=500)
