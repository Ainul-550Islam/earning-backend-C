from .WalletSerializer import WalletSerializer
from .WalletTransactionSerializer import WalletTransactionSerializer
from .WithdrawalRequestSerializer import WithdrawalRequestSerializer
from .WithdrawalMethodSerializer import WithdrawalMethodSerializer
from .WithdrawalFeeSerializer import WithdrawalFeeSerializer
from .BalanceHistorySerializer import BalanceHistorySerializer
from .BalanceBonusSerializer import BalanceBonusSerializer
from .LedgerEntrySerializer import LedgerEntrySerializer
from .EarningRecordSerializer import EarningRecordSerializer
from .EarningSummarySerializer import EarningSummarySerializer
from .WalletInsightSerializer import WalletInsightSerializer
from .LiabilityReportSerializer import LiabilityReportSerializer
from .AdminWalletSerializer import AdminWalletSerializer

from rest_framework import serializers
from ..models import Withdrawal

class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = '__all__'
from ..models import UserPaymentMethod
from ..models_webhook import WalletWebhookLog

class UserPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPaymentMethod
        fields = '__all__'

class WalletWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletWebhookLog
        fields = '__all__'
