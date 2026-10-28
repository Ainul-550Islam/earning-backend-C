# api/wallet/tests/__init__.py
"""
Wallet test suite.
Run all tests:
    python manage.py test api.wallet.tests --verbosity=2

Run specific test file:
    python manage.py test api.wallet.tests.test_wallet_service

Run with coverage:
    coverage run manage.py test api.wallet
    coverage report --include="api/wallet/*"

Test categories:
    Unit:        test_wallet_service, test_transaction_service, test_ledger,
                 test_withdrawal, test_withdrawal_fees, test_withdrawal_limits,
                 test_idempotency, test_balance_types, test_earning_caps,
                 test_serializers, test_signals, test_tasks, test_currency,
                 test_rate_limiter, test_audit_log, test_notifications
    Integration: test_integration, test_integration_gateway, test_integration_cpalead,
                 test_event_bus, test_reporting
    End-to-End:  test_views, test_admin
    Performance: test_performance
"""
