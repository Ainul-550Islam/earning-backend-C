# ==================== SETUP FILE ====================
# api/tests/__init__.py এ এটা paste করো:

WALLET_TEST_APPS = [
    'test_wallet.WalletModelTest',
    'test_wallet.WalletTransactionModelTest',
    'test_wallet.UserPaymentMethodTest',
    'test_wallet.WithdrawalTest',
    'test_wallet.WalletAPITest',
    'test_wallet.WalletWebhookLogTest',
]

OTHER_APPS_TESTS = [
    'test_all_apps.UserModelTest',
    'test_all_apps.UserAPITest',
    'test_all_apps.ReferralModelTest',
    'test_all_apps.TaskModelTest',
    'test_all_apps.KYCModelTest',
    'test_all_apps.SupportTicketTest',
    'test_all_apps.AnalyticsTest',
    'test_all_apps.AuditLogTest',
    'test_all_apps.RateLimitTest',
    'test_all_apps.EngagementTest',
    'test_all_apps.NotificationTest',
    'test_all_apps.PaymentGatewayTest',
    'test_all_apps.OfferwallTest',
    'test_all_apps.SecurityTest',
]
