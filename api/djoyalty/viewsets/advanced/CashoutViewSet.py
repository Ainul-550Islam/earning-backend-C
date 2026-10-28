# api/djoyalty/viewsets/advanced/CashoutViewSet.py
"""
CashoutViewSet — DRY refactored (v3)。

DRY FIX (v3):
  Before: 18 inline error response constructions (now replaced by self.err())
  After:  self.err(), self.not_found(), self.from_service_created()
          via DjoyaltyBaseViewSet

  Before: customer = getattr(request, 'loyalty_customer', None)
          if not customer: [7-line error handling block]
  After:  customer, err = self.require_customer(request)
          if err: return err
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ...mixins import DjoyaltyBaseViewSet
from ...models.cashout import (
    CashoutRequest, CashoutRate,
    CustomerBankAccount, CustomerMobileWallet, WalletTransaction,
)
from ...serializers.CashoutSerializer import (
    CashoutRequestSerializer, CashoutRequestCreateSerializer,
    CashoutAdminActionSerializer, CashoutRateSerializer,
    CustomerBankAccountSerializer, CustomerBankAccountCreateSerializer,
    CustomerMobileWalletSerializer, CustomerMobileWalletCreateSerializer,
    WalletTransactionSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination

logger = logging.getLogger(__name__)


class CashoutViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    POST   /cashouts/request/            — initiate cashout
    GET    /cashouts/history/            — my cashout history
    GET    /cashouts/rates/              — available cashout rates
    GET    /cashouts/wallet-history/     — wallet transaction log
    GET    /cashouts/bank-accounts/      — my bank accounts
    POST   /cashouts/bank-accounts/add/  — add bank account
    GET    /cashouts/mobile-wallets/     — my mobile wallets
    POST   /cashouts/mobile-wallets/add/ — add mobile wallet
    GET    /cashouts/admin/pending/      — pending requests (admin)
    POST   /cashouts/admin/{id}/action/  — approve/reject/complete (admin)
    """
    permission_classes = [IsAuthenticated]
    pagination_class   = DjoyaltyPagePagination

    # ── Initiate Cashout ──────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='request')
    def request_cashout(self, request):
        # DRY: one-line customer resolution replaces 6-line block
        customer, err = self.require_customer(request)
        if err: return err

        serializer = CashoutRequestCreateSerializer(
            data=request.data, context={'customer': customer}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            from ...integration_system.auth_bridge import PermissionGuard
            can, reason = PermissionGuard.can_cashout(customer)
            if not can: return self.forbidden(reason)
            can_redeem, reason = PermissionGuard.can_redeem(
                customer, float(data['points_to_redeem'])
            )
            if not can_redeem: return self.err(reason)
        except Exception as e:
            logger.warning('PermissionGuard check failed: %s', e)

        from ...services.CashoutService import CashoutService
        bank_account, mobile_wallet, dest_error = CashoutService.validate_destination(
            customer=customer,
            bank_account_id=data.get('bank_account_id'),
            mobile_wallet_id=data.get('mobile_wallet_id'),
        )
        if dest_error: return self.err(dest_error)

        rate = CashoutService.get_customer_rate(
            customer=customer, cashout_method=data['cashout_method'],
        )
        if not rate:
            return self.err('Cashout not available for this method.')

        if data['points_to_redeem'] < rate.min_cashout_points:
            return self.err(f'Minimum cashout is {rate.min_cashout_points} points.')

        result = CashoutService.create_request(
            customer=customer, points_to_redeem=data['points_to_redeem'],
            cashout_method=data['cashout_method'],
            bank_account=bank_account, mobile_wallet=mobile_wallet,
            rate=rate, request=request,
        )
        if not result['success']:
            return self.err(result['error'])

        return self.created(CashoutRequestSerializer(result['cashout']).data)

    # ── Customer History ──────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        customer, err = self.require_customer(request, lookup_in_data=False)
        if err: return err
        qs         = CashoutRequest.objects.filter(customer=customer).order_by('-created_at')[:50]
        serializer = CashoutRequestSerializer(qs, many=True)
        return self.ok({'results': serializer.data})

    # ── Rates ─────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='rates')
    def rates(self, request):
        qs = CashoutRate.objects.filter(is_active=True).order_by('cashout_method')
        return self.ok({'rates': CashoutRateSerializer(qs, many=True).data})

    # ── Wallet Transaction History ────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='wallet-history')
    def wallet_history(self, request):
        customer, err = self.require_customer(request, lookup_in_data=False)
        if err: return err
        txn_type = request.query_params.get('type')
        qs = WalletTransaction.objects.filter(customer=customer).order_by('-created_at')
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        return self.ok({'results': WalletTransactionSerializer(qs[:100], many=True).data})

    # ── Bank Accounts ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='bank-accounts')
    def bank_accounts(self, request):
        customer, err = self.require_customer(request, lookup_in_data=False)
        if err: return self.ok({'accounts': []})
        qs = CustomerBankAccount.objects.filter(customer=customer, is_active=True)
        return self.ok(CustomerBankAccountSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='bank-accounts/add')
    def add_bank_account(self, request):
        customer, err = self.require_customer(request)
        if err: return err
        serializer = CustomerBankAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from ...services.CashoutService import CashoutService
        try:
            account = CashoutService.add_bank_account(
                customer=customer, data=serializer.validated_data,
                tenant=self.get_tenant(),
            )
        except Exception as e:
            logger.error('add_bank_account error for %s: %s', customer.code, e)
            return self.err(str(e))
        return self.created(CustomerBankAccountSerializer(account).data)

    # ── Mobile Wallets ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='mobile-wallets')
    def mobile_wallets(self, request):
        customer, err = self.require_customer(request, lookup_in_data=False)
        if err: return self.ok({'wallets': []})
        qs = CustomerMobileWallet.objects.filter(customer=customer, is_active=True)
        return self.ok(CustomerMobileWalletSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='mobile-wallets/add')
    def add_mobile_wallet(self, request):
        customer, err = self.require_customer(request)
        if err: return err
        serializer = CustomerMobileWalletCreateSerializer(
            data=request.data, context={'customer': customer}
        )
        serializer.is_valid(raise_exception=True)
        from ...services.CashoutService import CashoutService
        try:
            wallet = CashoutService.add_mobile_wallet(
                customer=customer, data=serializer.validated_data, tenant=self.get_tenant(),
            )
        except ValueError as e:
            return self.err(str(e))
        except Exception as e:
            logger.error('add_mobile_wallet error for %s: %s', customer.code, e)
            return self.err(str(e))
        return self.created(CustomerMobileWalletSerializer(wallet).data)

    # ── Admin: Pending List ───────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='admin/pending',
            permission_classes=[IsLoyaltyAdmin])
    def admin_pending(self, request):
        qs = CashoutRequest.objects.filter(
            status__in=['pending', 'approved']
        ).select_related('customer', 'bank_account', 'mobile_wallet').order_by('-created_at')
        if request.query_params.get('status'):
            qs = qs.filter(status=request.query_params['status'])
        if request.query_params.get('flagged') == 'true':
            qs = qs.filter(is_flagged=True)
        return self.ok({'results': CashoutRequestSerializer(qs[:100], many=True).data,
                        'count': qs.count()})

    # ── Admin: Action on Request ──────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='action',
            permission_classes=[IsLoyaltyAdmin])
    def admin_action(self, request, pk=None):
        cashout    = get_object_or_404(CashoutRequest, pk=pk)
        serializer = CashoutAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_type = serializer.validated_data['action']
        note        = serializer.validated_data.get('note', '')
        pay_ref     = serializer.validated_data.get('payment_reference', '')
        try:
            from ...services.points.WalletBridgeService import WalletBridgeService
            if action_type == 'approve':
                WalletBridgeService.approve_cashout(cashout=cashout, admin=str(request.user), note=note)
                self._fire_cashout_approved(cashout, 'approved', str(request.user), note=note)
            elif action_type == 'reject':
                WalletBridgeService.reject_cashout(cashout=cashout, admin=str(request.user), reason=note)
            elif action_type == 'complete':
                WalletBridgeService.complete_cashout(cashout=cashout, admin=str(request.user), payment_reference=pay_ref)
                self._fire_cashout_approved(cashout, 'completed', str(request.user), payment_reference=pay_ref, note=note)
            elif action_type == 'cancel':
                WalletBridgeService.cancel_cashout(cashout=cashout, admin=str(request.user))
            cashout.refresh_from_db()
            return self.ok({'status': 'action_taken', 'action': action_type,
                            'cashout': CashoutRequestSerializer(cashout).data})
        except ValueError as e:
            return self.err(str(e))
        except Exception as e:
            logger.error('admin_action cashout %s error: %s', pk, e)
            return self.err('Action failed.', http_status=500)

    @staticmethod
    def _fire_cashout_approved(cashout, action: str, admin_user: str,
                                payment_reference: str = '', note: str = ''):
        try:
            from ...signals import cashout_approved
            cashout_approved.send(
                sender=CashoutViewSet, cashout=cashout, action=action,
                admin_user=admin_user, payment_reference=payment_reference,
                note=note, timestamp=timezone.now(),
            )
        except Exception as e:
            logger.error('cashout_approved signal failed for %s: %s',
                         getattr(cashout, 'reference', cashout.pk), e)
