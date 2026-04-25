# Webhook Event Types Reference

This document provides a comprehensive reference for all webhook event types
supported by the webhooks system across all platform domains.

## 📋 Table of Contents

- [User Events](#user-events)
- [Wallet Events](#wallet-events)
- [Withdrawal Events](#withdrawal-events)
- [Offer Events](#offer-events)
- [KYC Events](#kyc-events)
- [Payment Events](#payment-events)
- [Fraud Events](#fraud-events)
- [System Events](#system-events)
- [Analytics Events](#analytics-events)
- [Security Events](#security-events)
- [Integration Events](#integration-events)
- [Notification Events](#notification-events)
- [Campaign Events](#campaign-events)
- [Subscription Events](#subscription-events)
- [API Events](#api-events)
- [Health Events](#health-events)
- [Batch Events](#batch-events)
- [Replay Events](#replay-events)

## 👤 User Events

User-related events for account management and user lifecycle.

### `user.created`
- **Description**: Triggered when a new user account is created
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2024-01-01T00:00:00Z",
    "profile": {
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+1234567890"
    }
  }
  ```
- **Use Cases**: Welcome emails, user onboarding, analytics tracking
- **Frequency**: High (during user registration)

### `user.updated`
- **Description**: Triggered when user profile information is updated
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "email": "user@example.com",
    "updated_fields": ["email", "profile"],
    "updated_at": "2024-01-01T00:00:00Z",
    "previous_values": {
      "email": "old@example.com"
    },
    "new_values": {
      "email": "new@example.com"
    }
  }
  ```
- **Use Cases**: Profile updates, email change notifications
- **Frequency**: Medium

### `user.deleted`
- **Description**: Triggered when a user account is deleted
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "email": "user@example.com",
    "deleted_at": "2024-01-01T00:00:00Z",
    "reason": "user_request",
    "grace_period_days": 30
  }
  ```
- **Use Cases**: Account cleanup, compliance notifications
- **Frequency**: Low

### `user.login`
- **Description**: Triggered when a user successfully logs in
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "email": "user@example.com",
    "login_at": "2024-01-01T00:00:00Z",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "login_method": "password"
  }
  ```
- **Use Cases**: Security monitoring, login analytics
- **Frequency**: High

### `user.logout`
- **Description**: Triggered when a user logs out
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "email": "user@example.com",
    "logout_at": "2024-01-01T00:00:00Z",
    "session_duration_minutes": 45
  }
  ```
- **Use Cases**: Session management, security tracking
- **Frequency**: Medium

## 💰 Wallet Events

Wallet-related events for financial transactions and balance management.

### `wallet.transaction.created`
- **Description**: Triggered when a new wallet transaction is created
- **Payload Structure**:
  ```json
  {
    "transaction_id": "txn_123456789",
    "user_id": 12345,
    "wallet_id": "wallet_12345",
    "type": "credit",
    "amount": 100.00,
    "currency": "USD",
    "description": "Offer credit",
    "balance_before": 50.00,
    "balance_after": 150.00,
    "created_at": "2024-01-01T00:00:00Z",
    "metadata": {
      "source": "offer_completion",
      "reference_id": "offer_12345"
    }
  }
  ```
- **Use Cases**: Transaction logging, balance updates
- **Frequency**: High

### `wallet.balance.updated`
- **Description**: Triggered when wallet balance changes
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "wallet_id": "wallet_12345",
    "balance_before": 150.00,
    "balance_after": 125.00,
    "change_amount": -25.00,
    "updated_at": "2024-01-01T00:00:00Z",
    "triggering_transaction_id": "txn_123456789"
  }
  ```
- **Use Cases**: Balance notifications, spending alerts
- **Frequency**: High

### `wallet.frozen`
- **Description**: Triggered when a wallet is frozen
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "wallet_id": "wallet_12345",
    "frozen_at": "2024-01-01T00:00:00Z",
    "reason": "suspicious_activity",
    "frozen_by": "system",
    "balance_at_freeze": 125.00
  }
  ```
- **Use Cases**: Security alerts, compliance
- **Frequency**: Low

### `wallet.unfrozen`
- **Description**: Triggered when a wallet is unfrozen
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "wallet_id": "wallet_12345",
    "unfrozen_at": "2024-01-01T00:00:00Z",
    "unfrozen_by": "admin",
    "reason": "investigation_completed",
    "balance_at_unfreeze": 125.00
  }
  ```
- **Use Cases**: Recovery notifications, compliance
- **Frequency**: Low

## 💸 Withdrawal Events

Withdrawal-related events for fund transfers and payout processing.

### `withdrawal.requested`
- **Description**: Triggered when a withdrawal request is submitted
- **Payload Structure**:
  ```json
  {
    "withdrawal_id": "wd_123456789",
    "user_id": 12345,
    "amount": 50.00,
    "currency": "USD",
    "method": "bank_transfer",
    "status": "pending",
    "requested_at": "2024-01-01T00:00:00Z",
    "wallet_id": "wallet_12345",
    "bank_details": {
      "account_number": "****1234",
      "bank_name": "Example Bank"
    }
  }
  ```
- **Use Cases**: Withdrawal tracking, compliance
- **Frequency**: Medium

### `withdrawal.approved`
- **Description**: Triggered when a withdrawal request is approved
- **Payload Structure**:
  ```json
  {
    "withdrawal_id": "wd_123456789",
    "user_id": 12345,
    "amount": 50.00,
    "currency": "USD",
    "status": "approved",
    "approved_at": "2024-01-01T00:00:00Z",
    "approved_by": "admin_123",
    "processing_time_hours": 2
  }
  ```
- **Use Cases**: Status updates, processing notifications
- **Frequency**: Medium

### `withdrawal.rejected`
- **Description**: Triggered when a withdrawal request is rejected
- **Payload Structure**:
  ```json
  {
    "withdrawal_id": "wd_123456789",
    "user_id": 12345,
    "amount": 50.00,
    "currency": "USD",
    "status": "rejected",
    "rejected_at": "2024-01-01T00:00:00Z",
    "rejected_by": "system",
    "reason": "insufficient_balance",
    "rejection_code": "INSUFFICIENT_BALANCE"
  }
  ```
- **Use Cases**: Rejection notifications, user alerts
- **Frequency**: Medium

### `withdrawal.completed`
- **Description**: Triggered when a withdrawal is completed successfully
- **Payload Structure**:
  ```json
  {
    "withdrawal_id": "wd_123456789",
    "user_id": 12345,
    "amount": 50.00,
    "currency": "USD",
    "status": "completed",
    "completed_at": "2024-01-01T00:00:00Z",
    "transaction_id": "bank_txn_123456",
    "processing_time_hours": 24
  }
  ```
- **Use Cases**: Completion notifications, accounting
- **Frequency**: Medium

## 🎯 Offer Events

Offer-related events for marketing campaigns and user rewards.

### `offer.credited`
- **Description**: Triggered when an offer is credited to a user
- **Payload Structure**:
  ```json
  {
    "offer_id": "offer_123456789",
    "user_id": 12345,
    "amount": 5.00,
    "currency": "USD",
    "offer_type": "signup_bonus",
    "credited_at": "2024-01-01T00:00:00Z",
    "campaign_id": "campaign_12345",
    "wallet_balance_before": 25.00,
    "wallet_balance_after": 30.00
  }
  ```
- **Use Cases**: Reward notifications, marketing analytics
- **Frequency**: High

### `offer.completed`
- **Description**: Triggered when an offer is fully completed
- **Payload Structure**:
  ```json
  {
    "offer_id": "offer_123456789",
    "user_id": 12345,
    "amount": 10.00,
    "currency": "USD",
    "offer_type": "referral_bonus",
    "completed_at": "2024-01-01T00:00:00Z",
    "requirements_met": [
      "account_verified",
      "minimum_spend_achieved"
    ]
  }
  ```
- **Use Cases**: Campaign tracking, user engagement
- **Frequency**: Medium

### `offer.expired`
- **Description**: Triggered when an offer expires
- **Payload Structure**:
  ```json
  {
    "offer_id": "offer_123456789",
    "user_id": 12345,
    "amount": 15.00,
    "currency": "USD",
    "offer_type": "limited_time",
    "expired_at": "2024-01-01T00:00:00Z",
    "was_claimed": false
    "reason": "time_limit_exceeded"
  }
  ```
- **Use Cases**: Expiration notifications, cleanup
- **Frequency**: Low

### `offer.revoked`
- **Description**: Triggered when an offer is revoked
- **Payload Structure**:
  ```json
  {
    "offer_id": "offer_123456789",
    "user_id": 12345,
    "amount": 20.00,
    "currency": "USD",
    "offer_type": "promotional",
    "revoked_at": "2024-01-01T00:00:00Z",
    "revoked_by": "admin",
    "reason": "fraud_detected"
  }
  ```
- **Use Cases**: Security alerts, compliance
- **Frequency**: Low

## 🆔 KYC Events

Know Your Customer related events for identity verification.

### `kyc.submitted`
- **Description**: Triggered when KYC documents are submitted
- **Payload Structure**:
  ```json
  {
    "kyc_id": "kyc_123456789",
    "user_id": 12345,
    "document_types": ["id_card", "proof_of_address"],
    "submitted_at": "2024-01-01T00:00:00Z",
    "status": "pending_review",
    "review_priority": "normal"
  }
  ```
- **Use Cases**: Compliance tracking, user notifications
- **Frequency**: Medium

### `kyc.verified`
- **Description**: Triggered when KYC verification is completed
- **Payload Structure**:
  ```json
  {
    "kyc_id": "kyc_123456789",
    "user_id": 12345,
    "verified_at": "2024-01-01T00:00:00Z",
    "verified_by": "verifier_123",
    "verification_level": "tier_2",
    "expires_at": "2025-01-01T00:00:00Z"
  }
  ```
- **Use Cases**: Account upgrades, compliance
- **Frequency**: Medium

### `kyc.rejected`
- **Description**: Triggered when KYC verification is rejected
- **Payload Structure**:
  ```json
  {
    "kyc_id": "kyc_123456789",
    "user_id": 12345,
    "rejected_at": "2024-01-01T00:00:00Z",
    "rejected_by": "system",
    "reason": "document_unclear",
    "rejection_code": "UNCLEAR_DOCUMENTS"
  }
  ```
- **Use Cases**: Rejection notifications, user guidance
- **Frequency**: Medium

## 💳 Payment Events

Payment-related events for transactions and financial processing.

### `payment.succeeded`
- **Description**: Triggered when a payment is successfully processed
- **Payload Structure**:
  ```json
  {
    "payment_id": "pay_123456789",
    "user_id": 12345,
    "amount": 100.00,
    "currency": "USD",
    "method": "credit_card",
    "status": "completed",
    "processed_at": "2024-01-01T00:00:00Z",
    "gateway": "stripe",
    "transaction_id": "ch_123456789"
  }
  ```
- **Use Cases**: Payment confirmations, accounting
- **Frequency**: High

### `payment.failed`
- **Description**: Triggered when a payment fails
- **Payload Structure**:
  ```json
  {
    "payment_id": "pay_123456789",
    "user_id": 12345,
    "amount": 100.00,
    "currency": "USD",
    "method": "credit_card",
    "status": "failed",
    "failed_at": "2024-01-01T00:00:00Z",
    "gateway": "stripe",
    "error_code": "insufficient_funds",
    "error_message": "Insufficient funds"
  }
  ```
- **Use Cases**: Failure notifications, retry logic
- **Frequency**: Medium

### `payment.refunded`
- **Description**: Triggered when a payment is refunded
- **Payload Structure**:
  ```json
  {
    "payment_id": "pay_123456789",
    "user_id": 12345,
    "amount": 100.00,
    "currency": "USD",
    "refund_reason": "customer_request",
    "refunded_at": "2024-01-01T00:00:00Z",
    "refund_id": "ref_123456789"
  }
  ```
- **Use Cases**: Refund notifications, accounting
- **Frequency**: Low

### `payment.chargeback`
- **Description**: Triggered when a chargeback is initiated
- **Payload Structure**:
  ```json
  {
    "payment_id": "pay_123456789",
    "user_id": 12345,
    "amount": 100.00,
    "currency": "USD",
    "chargeback_reason": "fraud",
    "initiated_at": "2024-01-01T00:00:00Z",
    "case_id": "cb_123456789"
  }
  ```
- **Use Cases**: Fraud alerts, financial tracking
- **Frequency**: Low

## 🛡️ Fraud Events

Fraud detection and prevention related events.

### `fraud.detected`
- **Description**: Triggered when suspicious activity is detected
- **Payload Structure**:
  ```json
  {
    "fraud_id": "fraud_123456789",
    "user_id": 12345,
    "fraud_type": "unusual_login_pattern",
    "detected_at": "2024-01-01T00:00:00Z",
    "risk_score": 85,
    "details": {
      "ip_address": "192.168.1.1",
      "user_agent": "Suspicious Browser",
      "location": "Unknown"
    },
    "auto_actions_taken": ["account_locked", "notification_sent"]
  }
  ```
- **Use Cases**: Security alerts, fraud prevention
- **Frequency**: Low

### `fraud.reviewed`
- **Description**: Triggered when fraud case is reviewed
- **Payload Structure**:
  ```json
  {
    "fraud_id": "fraud_123456789",
    "user_id": 12345,
    "reviewed_at": "2024-01-01T00:00:00Z",
    "reviewed_by": "fraud_analyst_123",
    "outcome": "confirmed_fraud",
    "actions_taken": ["account_suspended", "law_enforcement_notified"]
  }
  ```
- **Use Cases**: Case management, compliance
- **Frequency**: Low

### `fraud.confirmed`
- **Description**: Triggered when fraud is confirmed
- **Payload Structure**:
  ```json
  {
    "fraud_id": "fraud_123456789",
    "user_id": 12345,
    "confirmed_at": "2024-01-01T00:00:00Z",
    "confirmed_by": "fraud_manager_123",
    "financial_impact": 500.00,
    "currency": "USD"
  }
  ```
- **Use Cases**: Financial impact tracking, legal compliance
- **Frequency**: Low

### `fraud.false_positive`
- **Description**: Triggered when fraud alert is false positive
- **Payload Structure**:
  ```json
  {
    "fraud_id": "fraud_123456789",
    "user_id": 12345,
    "resolved_at": "2024-01-01T00:00:00Z",
    "false_positive_reason": "legitimate_business_activity",
    "actions_taken": ["account_unlocked", "apology_sent"]
  }
  ```
- **Use Cases**: False positive tracking, user experience
- **Frequency**: Low

## 🔧 System Events

System-level events for maintenance, backups, and infrastructure.

### `system.maintenance`
- **Description**: Triggered when system maintenance is scheduled or started
- **Payload Structure**:
  ```json
  {
    "maintenance_id": "maint_123456789",
    "type": "scheduled",
    "start_time": "2024-01-01T02:00:00Z",
    "estimated_duration_minutes": 30,
    "affected_services": ["webhooks", "api", "database"],
    "notification_message": "System maintenance in progress"
  }
  ```
- **Use Cases**: Maintenance notifications, downtime alerts
- **Frequency**: Low

### `system.backup`
- **Description**: Triggered when system backup is completed
- **Payload Structure**:
  ```json
  {
    "backup_id": "backup_123456789",
    "type": "automated",
    "completed_at": "2024-01-01T00:00:00Z",
    "backup_size_gb": 15.5,
    "retention_days": 90,
    "backup_location": "s3://backups/webhooks/"
  }
  ```
- **Use Cases**: Backup monitoring, compliance
- **Frequency**: Low

### `system.restored`
- **Description**: Triggered when system is restored from backup
- **Payload Structure**:
  ```json
  {
    "restore_id": "restore_123456789",
    "backup_id": "backup_123456789",
    "restored_at": "2024-01-01T00:00:00Z",
    "restore_time_minutes": 45,
    "data_loss": false,
    "restored_services": ["webhooks", "api"]
  }
  ```
- **Use Cases**: Recovery tracking, incident management
- **Frequency**: Low

### `system.error`
- **Description**: Triggered when a system error occurs
- **Payload Structure**:
  ```json
  {
    "error_id": "error_123456789",
    "error_type": "database_connection",
    "severity": "high",
    "occurred_at": "2024-01-01T00:00:00Z",
    "error_message": "Database connection timeout",
    "service": "webhooks",
    "impact": "webhook_delivery_affected"
  }
  ```
- **Use Cases**: Error tracking, incident management
- **Frequency**: Medium

## 📊 Analytics Events

Analytics and reporting related events.

### `analytics.report.generated`
- **Description**: Triggered when an analytics report is generated
- **Payload Structure**:
  ```json
  {
    "report_id": "report_123456789",
    "type": "daily_summary",
    "period_start": "2024-01-01T00:00:00Z",
    "period_end": "2024-01-02T00:00:00Z",
    "generated_at": "2024-01-02T01:00:00Z",
    "metrics": {
      "total_webhooks": 10000,
      "success_rate": 95.5,
      "avg_response_time_ms": 150
    }
  }
  ```
- **Use Cases**: Report tracking, analytics automation
- **Frequency**: Low

### `analytics.data.exported`
- **Description**: Triggered when analytics data is exported
- **Payload Structure**:
  ```json
  {
    "export_id": "export_123456789",
    "type": "csv",
    "date_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-31T23:59:59Z"
    },
    "exported_at": "2024-01-01T00:00:00Z",
    "file_size_mb": 25.5,
    "requested_by": "admin_123"
  }
  ```
- **Use Cases**: Export tracking, compliance
- **Frequency**: Low

### `analytics.threshold.reached`
- **Description**: Triggered when an analytics threshold is reached
- **Payload Structure**:
  ```json
  {
    "threshold_id": "thresh_123456789",
    "metric": "failure_rate",
    "threshold_value": 5.0,
    "actual_value": 7.5,
    "reached_at": "2024-01-01T00:00:00Z",
    "severity": "warning",
    "recommended_actions": ["investigate_endpoints", "check_rate_limits"]
  }
  ```
- **Use Cases**: Alerting, proactive monitoring
- **Frequency**: Low

## 🔒 Security Events

Security and authentication related events.

### `security.breach`
- **Description**: Triggered when a security breach is detected
- **Payload Structure**:
  ```json
  {
    "breach_id": "breach_123456789",
    "type": "unauthorized_access",
    "detected_at": "2024-01-01T00:00:00Z",
    "affected_users": [12345, 67890],
    "severity": "critical",
    "immediate_actions": ["password_reset_all", "session_invalidation"]
  }
  ```
- **Use Cases**: Incident response, security alerts
- **Frequency**: Low

### `security.suspicious_activity`
- **Description**: Triggered when suspicious activity is detected
- **Payload Structure**:
  ```json
  {
    "activity_id": "activity_123456789",
    "user_id": 12345,
    "activity_type": "unusual_ip_access",
    "detected_at": "2024-01-01T00:00:00Z",
    "details": {
      "ip_address": "192.168.1.1",
      "location": "Unknown",
      "user_agent": "Suspicious Browser"
    }
  }
  ```
- **Use Cases**: Security monitoring, fraud prevention
- **Frequency**: Medium

### `security.login.blocked`
- **Description**: Triggered when a login attempt is blocked
- **Payload Structure**:
  ```json
  {
    "block_id": "block_123456789",
    "user_id": 12345,
    "ip_address": "192.168.1.1",
    "blocked_at": "2024-01-01T00:00:00Z",
    "reason": "too_many_attempts",
    "blocked_until": "2024-01-01T01:00:00Z"
  }
  ```
- **Use Cases**: Security monitoring, brute force protection
- **Frequency**: Medium

### `security.password.changed`
- **Description**: Triggered when a user password is changed
- **Payload Structure**:
  ```json
  {
    "user_id": 12345,
    "changed_at": "2024-01-01T00:00:00Z",
    "changed_by": "user",  # or "admin"
    "ip_address": "192.168.1.1",
    "password_strength": "strong"
  }
  ```
- **Use Cases**: Security monitoring, user notifications
- **Frequency**: Medium

## 🔗 Integration Events

Third-party integration related events.

### `integration.connected`
- **Description**: Triggered when an external integration is connected
- **Payload Structure**:
  ```json
  {
    "integration_id": "int_123456789",
    "service": "stripe",
    "connected_at": "2024-01-01T00:00:00Z",
    "configuration": {
      "webhook_url": "https://example.com/stripe-webhook",
      "events": ["payment.succeeded", "payment.failed"]
    },
    "status": "active"
  }
  ```
- **Use Cases**: Integration monitoring, connectivity tracking
- **Frequency**: Low

### `integration.disconnected`
- **Description**: Triggered when an external integration is disconnected
- **Payload Structure**:
  ```json
  {
    "integration_id": "int_123456789",
    "service": "stripe",
    "disconnected_at": "2024-01-01T00:00:00Z",
    "reason": "webhook_verification_failed",
    "downtime_minutes": 15
  }
  ```
- **Use Cases**: Integration monitoring, alerting
- **Frequency**: Low

### `integration.sync.failed`
- **Description**: Triggered when integration synchronization fails
- **Payload Structure**:
  ```json
  {
    "sync_id": "sync_123456789",
    "integration_id": "int_123456789",
    "failed_at": "2024-01-01T00:00:00Z",
    "error_code": "TIMEOUT",
    "error_message": "Connection timeout after 30 seconds",
    "retry_count": 3
  }
  ```
- **Use Cases**: Sync monitoring, error tracking
- **Frequency**: Medium

### `integration.api.limit.reached`
- **Description**: Triggered when integration API limit is reached
- **Payload Structure**:
  ```json
  {
    "limit_id": "limit_123456789",
    "integration_id": "int_123456789",
    "service": "stripe",
    "reached_at": "2024-01-01T00:00:00Z",
    "limit_type": "rate_limit",
    "limit_value": 1000,
    "current_usage": 1000,
    "reset_at": "2024-01-01T01:00:00Z"
  }
  ```
- **Use Cases**: API usage monitoring, billing
- **Frequency**: Low

## 📢 Notification Events

Notification system related events.

### `notification.sent`
- **Description**: Triggered when a notification is sent
- **Payload Structure**:
  ```json
  {
    "notification_id": "notif_123456789",
    "user_id": 12345,
    "type": "email",
    "channel": "smtp",
    "sent_at": "2024-01-01T00:00:00Z",
    "subject": "Your withdrawal has been processed",
    "delivery_status": "delivered"
  }
  ```
- **Use Cases**: Delivery tracking, analytics
- **Frequency**: High

### `notification.delivered`
- **Description**: Triggered when a notification is delivered
- **Payload Structure**:
  ```json
  {
    "notification_id": "notif_123456789",
    "user_id": 12345,
    "delivered_at": "2024-01-01T00:00:00Z",
    "delivery_method": "email",
    "delivery_time_ms": 250
  }
  ```
- **Use Cases**: Delivery analytics, performance monitoring
- **Frequency**: High

### `notification.failed`
- **Description**: Triggered when a notification delivery fails
- **Payload Structure**:
  ```json
  {
    "notification_id": "notif_123456789",
    "user_id": 12345,
    "failed_at": "2024-01-01T00:00:00Z",
    "error_code": "BOUNCE",
    "error_message": "Email address does not exist",
    "retry_count": 3
  }
  ```
- **Use Cases**: Failure tracking, retry logic
- **Frequency**: Medium

### `notification.opened`
- **Description**: Triggered when a notification is opened
- **Payload Structure**:
  ```json
  {
    "notification_id": "notif_123456789",
    "user_id": 12345,
    "opened_at": "2024-01-01T00:00:00Z",
    "open_time_ms": 5000
  }
  ```
- **Use Cases**: Engagement analytics, A/B testing
- **Frequency**: Medium

### `notification.clicked`
- **Description**: Triggered when a notification link is clicked
- **Payload Structure**:
  ```json
  {
    "notification_id": "notif_123456789",
    "user_id": 12345,
    "clicked_at": "2024-01-01T00:00:00Z",
    "click_time_ms": 3000,
    "link_url": "https://example.com/offer"
  }
  ```
- **Use Cases**: Engagement analytics, conversion tracking
- **Frequency**: Medium

## 📈 Campaign Events

Marketing campaign related events.

### `campaign.created`
- **Description**: Triggered when a marketing campaign is created
- **Payload Structure**:
  ```json
  {
    "campaign_id": "camp_123456789",
    "name": "Summer Sale 2024",
    "type": "email",
    "created_at": "2024-01-01T00:00:00Z",
    "created_by": "marketing_manager_123",
    "target_audience": "all_users",
    "scheduled_start": "2024-06-01T00:00:00Z"
  }
  ```
- **Use Cases**: Campaign tracking, marketing analytics
- **Frequency**: Low

### `campaign.started`
- **Description**: Triggered when a campaign starts
- **Payload Structure**:
  ```json
  {
    "campaign_id": "camp_123456789",
    "started_at": "2024-01-01T00:00:00Z",
    "total_recipients": 50000,
    "estimated_duration_hours": 24
  }
  ```
- **Use Cases**: Campaign monitoring, performance tracking
- **Frequency**: Low

### `campaign.paused`
- **Description**: Triggered when a campaign is paused
- **Payload Structure**:
  ```json
  {
    "campaign_id": "camp_123456789",
    "paused_at": "2024-01-01T12:00:00Z",
    "reason": "high_bounce_rate",
    "sent_count": 25000,
    "delivered_count": 20000
  }
  ```
- **Use Cases**: Campaign management, performance optimization
- **Frequency**: Low

### `campaign.resumed`
- **Description**: Triggered when a campaign is resumed
- **Payload Structure**:
  ```json
  {
    "campaign_id": "camp_123456789",
    "resumed_at": "2024-01-01T18:00:00Z",
    "reason": "issue_resolved",
    "remaining_recipients": 25000
  }
  ```
- **Use Cases**: Campaign management, recovery
- **Frequency**: Low

### `campaign.completed`
- **Description**: Triggered when a campaign completes
- **Payload Structure**:
  ```json
  {
    "campaign_id": "camp_123456789",
    "completed_at": "2024-01-02T00:00:00Z",
    "total_sent": 50000,
    "delivered_count": 45000,
    "open_rate": 0.35,
    "click_rate": 0.08,
    "conversion_rate": 0.02
  }
  ```
- **Use Cases**: Campaign analytics, ROI tracking
- **Frequency**: Low

## 🔄 Subscription Events

Subscription management related events.

### `subscription.created`
- **Description**: Triggered when a subscription is created
- **Payload Structure**:
  ```json
  {
    "subscription_id": "sub_123456789",
    "user_id": 12345,
    "plan_id": "premium_monthly",
    "plan_name": "Premium Monthly",
    "amount": 29.99,
    "currency": "USD",
    "created_at": "2024-01-01T00:00:00Z",
    "billing_cycle": "monthly",
    "auto_renew": true
  }
  ```
- **Use Cases**: Subscription tracking, revenue analytics
- **Frequency**: Medium

### `subscription.updated`
- **Description**: Triggered when a subscription is updated
- **Payload Structure**:
  ```json
  {
    "subscription_id": "sub_123456789",
    "user_id": 12345,
    "updated_at": "2024-01-01T00:00:00Z",
    "previous_plan": "basic_monthly",
    "new_plan": "premium_monthly",
    "price_change": "+10.00",
    "updated_by": "user"
  }
  ```
- **Use Cases**: Plan change tracking, revenue analytics
- **Frequency**: Low

### `subscription.cancelled`
- **Description**: Triggered when a subscription is cancelled
- **Payload Structure**:
  ```json
  {
    "subscription_id": "sub_123456789",
    "user_id": 12345,
    "cancelled_at": "2024-01-01T00:00:00Z",
    "reason": "cost_too_high",
    "cancellation_type": "voluntary",
    "refund_amount": 15.00,
    "pro-rated_days": 15
  }
  ```
- **Use Cases**: Churn analytics, revenue tracking
- **Frequency**: Medium

### `subscription.renewed`
- **Description**: Triggered when a subscription is renewed
- **Payload Structure**:
  ```json
  {
    "subscription_id": "sub_123456789",
    "user_id": 12345,
    "renewed_at": "2024-01-01T00:00:00Z",
    "renewal_period": "monthly",
    "next_billing_date": "2024-02-01T00:00:00Z"
  }
  ```
- **Use Cases**: Retention analytics, revenue forecasting
- **Frequency**: Medium

### `subscription.expired`
- **Description**: Triggered when a subscription expires
- **Payload Structure**:
  ```json
  {
    "subscription_id": "sub_123456789",
    "user_id": 12345,
    "expired_at": "2024-01-01T00:00:00Z",
    "grace_period_days": 7,
    "auto_renewal_attempted": false
  }
  ```
- **Use Cases**: Expiration tracking, retention efforts
- **Frequency**: Medium

## 🌐 API Events

API usage and system level events.

### `api.request`
- **Description**: Triggered when an API request is made
- **Payload Structure**:
  ```json
  {
    "request_id": "req_123456789",
    "endpoint": "/api/v1/webhooks",
    "method": "POST",
    "user_id": 12345,
    "ip_address": "192.168.1.1",
    "user_agent": "WebhooksClient/1.0",
    "requested_at": "2024-01-01T00:00:00Z",
    "response_time_ms": 150
  }
  ```
- **Use Cases**: API monitoring, usage analytics
- **Frequency**: High

### `api.response`
- **Description**: Triggered when an API response is sent
- **Payload Structure**:
  ```json
  {
    "request_id": "req_123456789",
    "status_code": 200,
    "response_time_ms": 150,
    "response_size_bytes": 1024,
    "cache_hit": false
  }
  ```
- **Use Cases**: Performance monitoring, analytics
- **Frequency**: High

### `api.error`
- **Description**: Triggered when an API error occurs
- **Payload Structure**:
  ```json
  {
    "error_id": "error_123456789",
    "request_id": "req_123456789",
    "error_code": "VALIDATION_ERROR",
    "error_message": "Invalid webhook URL format",
    "status_code": 400,
    "occurred_at": "2024-01-01T00:00:00Z",
    "user_id": 12345
  }
  ```
- **Use Cases**: Error tracking, debugging
- **Frequency**: Medium

### `api.rate_limit`
- **Description**: Triggered when API rate limit is reached
- **Payload Structure**:
  ```json
  {
    "limit_id": "limit_123456789",
    "user_id": 12345,
    "endpoint": "/api/v1/webhooks",
    "limit_type": "per_minute",
    "limit_value": 100,
    "current_usage": 100,
    "reset_at": "2024-01-01T01:00:00Z"
  }
  ```
- **Use Cases**: Rate limiting monitoring, abuse prevention
- **Frequency**: Medium

### `api.quota.exceeded`
- **Description**: Triggered when API quota is exceeded
- **Payload Structure**:
  ```json
  {
    "quota_id": "quota_123456789",
    "user_id": 12345,
    "quota_type": "monthly_requests",
    "quota_value": 10000,
    "current_usage": 10000,
    "reset_date": "2024-02-01T00:00:00Z"
  }
  ```
- **Use Cases**: Quota monitoring, billing alerts
- **Frequency**: Low

## 🏥 Health Events

Health monitoring and system health related events.

### `health.check.passed`
- **Description**: Triggered when a health check passes
- **Payload Structure**:
  ```json
  {
    "check_id": "check_123456789",
    "endpoint_id": "webhook_12345",
    "checked_at": "2024-01-01T00:00:00Z",
    "response_time_ms": 150,
    "status_code": 200,
    "next_check_at": "2024-01-01T05:00:00Z"
  }
  ```
- **Use Cases**: Health monitoring, uptime tracking
- **Frequency**: High

### `health.check.failed`
- **Description**: Triggered when a health check fails
- **Payload Structure**:
  ```json
  {
    "check_id": "check_123456789",
    "endpoint_id": "webhook_12345",
    "checked_at": "2024-01-01T00:00:00Z",
    "error": "Connection timeout",
    "response_time_ms": 5000,
    "status_code": null,
    "consecutive_failures": 3
  }
  ```
- **Use Cases**: Health monitoring, alerting
- **Frequency**: Medium

### `health.endpoint.up`
- **Description**: Triggered when an endpoint comes back online
- **Payload Structure**:
  ```json
  {
    "endpoint_id": "webhook_12345",
    "up_at": "2024-01-01T00:00:00Z",
    "downtime_minutes": 15,
    "resolution": "network_issue_resolved"
    "health_score": 95
  }
  ```
- **Use Cases**: Uptime monitoring, SLA tracking
- **Frequency**: Low

### `health.endpoint.down`
- **Description**: Triggered when an endpoint goes offline
- **Payload Structure**:
  ```json
  {
    "endpoint_id": "webhook_12345",
    "down_at": "2024-01-01T00:00:00Z",
    "last_check_at": "2024-01-01T00:00:00Z",
    "issue_type": "server_error",
    "auto_suspend_triggered": true
  }
  ```
- **Use Cases**: Downtime monitoring, incident response
- **Frequency**: Low

## 📦 Batch Events

Batch processing related events.

### `batch.created`
- **Description**: Triggered when a webhook batch is created
- **Payload Structure**:
  ```json
  {
    "batch_id": "batch_123456789",
    "endpoint_id": "webhook_12345",
    "event_count": 100,
    "created_at": "2024-01-01T00:00:00Z",
    "created_by": "system",
    "priority": "normal"
  }
  ```
- **Use Cases**: Batch tracking, processing monitoring
- **Frequency**: Medium

### `batch.started`
- **Description**: Triggered when batch processing starts
- **Payload Structure**:
  ```json
  {
    "batch_id": "batch_123456789",
    "started_at": "2024-01-01T00:00:00Z",
    "estimated_duration_minutes": 30,
    "processing_mode": "sequential"
  }
  ```
- **Use Cases**: Processing monitoring, performance tracking
- **Frequency**: Medium

### `batch.completed`
- **Description**: Triggered when a batch is completed
- **Payload Structure**:
  ```json
  {
    "batch_id": "batch_123456789",
    "completed_at": "2024-01-01T00:00:00Z",
    "total_items": 100,
    "successful_items": 95,
    "failed_items": 5,
    "processing_time_minutes": 28
  }
  ```
- **Use Cases**: Batch analytics, performance monitoring
- **Frequency**: Medium

### `batch.failed`
- **Description**: Triggered when a batch fails
- **Payload Structure**:
  ```json
  {
    "batch_id": "batch_123456789",
    "failed_at": "2024-01-01T00:00:00Z",
    "error_code": "RATE_LIMIT_EXCEEDED",
    "error_message": "Batch processing failed due to rate limiting",
    "processed_items": 50,
    "remaining_items": 50
  }
  ```
- **Use Cases**: Error tracking, retry logic
- **Frequency**: Low

### `batch.cancelled`
- **Description**: Triggered when a batch is cancelled
- **Payload Structure**:
  ```json
  {
    "batch_id": "batch_123456789",
    "cancelled_at": "2024-01-01T00:00:00Z",
    "reason": "user_request",
    "cancelled_by": "admin_123",
    "processed_items": 25,
    "remaining_items": 75
  }
  ```
- **Use Cases**: Batch management, user notifications
- **Frequency**: Low

## 🔄 Replay Events

Webhook replay related events.

### `replay.started`
- **Description**: Triggered when a webhook replay starts
- **Payload Structure**:
  ```json
  {
    "replay_id": "replay_123456789",
    "batch_id": "batch_123456789",
    "started_at": "2024-01-01T00:00:00Z",
    "event_count": 50,
    "replay_reason": "delivery_failure_investigation"
  }
  ```
- **Use Cases**: Replay tracking, debugging
- **Frequency**: Medium

### `replay.completed`
- **Description**: Triggered when a webhook replay completes
- **Payload Structure**:
  ```json
  {
    "replay_id": "replay_123456789",
    "completed_at": "2024-01-01T00:00:00Z",
    "success_count": 45,
    "failure_count": 5,
    "processing_time_minutes": 15
  }
  ```
- **Use Cases**: Replay analytics, success tracking
- **Frequency**: Medium

### `replay.failed`
- **Description**: Triggered when a webhook replay fails
- **Payload Structure**:
  ```json
  {
    "replay_id": "replay_123456789",
    "failed_at": "2024-01-01T00:00:00Z",
    "error_code": "ENDPOINT_UNAVAILABLE",
    "error_message": "Webhook endpoint not responding",
    "attempted_count": 3
  }
  ```
- **Use Cases**: Error tracking, retry logic
- **Frequency**: Low

### `replay.cancelled`
- **Description**: Triggered when a webhook replay is cancelled
- **Payload Structure**:
  ```json
  {
    "replay_id": "replay_123456789",
    "cancelled_at": "2024-01-01T00:00:00Z",
    "reason": "user_request",
    "cancelled_by": "admin_123",
    "remaining_events": 25
  }
  ```
- **Use Cases**: Replay management, user control
- **Frequency**: Low

## 📝 Event Type Best Practices

### Naming Conventions
- Use lowercase with dots separating domains: `user.created`, `wallet.transaction.created`
- Be descriptive and consistent across the platform
- Use past tense for completed actions: `created`, `updated`, `deleted`
- Use present tense for ongoing states: `login`, `logout`

### Payload Structure Guidelines
- Include unique identifiers: `user_id`, `transaction_id`, `webhook_id`
- Include timestamps: `created_at`, `updated_at`, `completed_at`
- Include relevant metadata: `ip_address`, `user_agent`, `status_code`
- Use consistent data types: strings, numbers, booleans, nested objects

### Event Frequency Guidelines
- **High Frequency**: User actions, transactions, payments (multiple per minute)
- **Medium Frequency**: Profile updates, withdrawals, subscriptions (few per day)
- **Low Frequency**: System events, batch operations, replays (few per week)

### Security Considerations
- Never include sensitive data in webhook payloads
- Use IP addresses and user agents for security monitoring
- Implement rate limiting for high-frequency events
- Log all events for audit trails

### Integration Guidelines
- All events should be configurable per webhook endpoint
- Use event filtering to reduce unnecessary webhook calls
- Implement retry logic for failed deliveries
- Monitor event processing performance

## 🔧 Implementation Notes

### Webhook Configuration
```python
# Example webhook endpoint configuration
webhook = WebhookEndpoint.objects.create(
    url='https://example.com/webhook',
    secret='your-secret-key',
    event_types=['user.created', 'wallet.transaction.created'],
    status='active'
)
```

### Event Emission
```python
# Example event emission
from api.webhooks.signals import emit_webhook_event

# Emit user creation event
emit_webhook_event(
    event_type='user.created',
    payload={
        'user_id': user.id,
        'email': user.email,
        'created_at': user.created_at.isoformat()
    }
)
```

### Event Handling
```python
# Example webhook event handler
@receiver(user_created_signal)
def handle_user_created(sender, **kwargs):
    user = kwargs.get('user')
    # Process user creation event
    send_welcome_email(user)
    update_user_analytics(user)
```

## 📚 Additional Resources

- [Webhooks API Reference](api_reference.md)
- [Signature Verification Guide](signature_guide.md)
- [Inbound Webhook Setup](inbound_setup.md)
- [Webhook Replay Guide](replay_guide.md)
- [Management Commands](../management/commands/)

## 📞 Support

For questions about webhook events or implementation:
- Check the [API Documentation](api_reference.md)
- Review the [Management Commands](../management/commands/)
- Contact the development team

---

*Last updated: January 1, 2026*
