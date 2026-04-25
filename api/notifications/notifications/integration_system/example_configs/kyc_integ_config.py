# api/kyc/integ_config.py
"""
KYC Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"

FIXES the critical violation in kyc/signals.py:

  ❌ OLD (VIOLATION in kyc/signals.py):
      from api.notifications.models import Notification
      Notification.objects.create(
          user=instance.user,
          title='KYC Verified ✅',
          notification_type='kyc'
      )

  ✅ NEW (clean — this file does the wiring automatically):
      event_bus.publish('kyc.verified', {...})
      → AutoDiscovery reads this config
      → Notification sent automatically via EventBus

No import of notifications module needed anywhere in kyc/.
"""

from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)


class KYCIntegConfig(ModuleConfig):
    module_name = 'kyc'
    version = '1.0.0'
    description = 'KYC Verification — Identity Management'

    signal_maps = [
        SignalMap(
            model_path='kyc.KYC',
            field='status',
            value='verified',
            event_type='kyc.approved',
            user_field='user_id',
            data_fields=['kyc_id', 'verified_at', 'verification_level'],
            on_created=False,
            on_update=True,
        ),
        SignalMap(
            model_path='kyc.KYC',
            field='status',
            value='rejected',
            event_type='kyc.rejected',
            user_field='user_id',
            data_fields=['kyc_id', 'rejection_reason', 'rejected_at'],
            on_created=False,
            on_update=True,
        ),
        SignalMap(
            model_path='kyc.KYC',
            field='status',
            value='expired',
            event_type='kyc.expired',
            user_field='user_id',
            data_fields=['kyc_id', 'expired_at'],
        ),
        SignalMap(
            model_path='kyc.KYCSubmission',
            field='status',
            value='submitted',
            event_type='kyc.submitted',
            user_field='user_id',
            data_fields=['submission_id', 'document_type'],
            on_created=True,
            on_update=False,
        ),
        SignalMap(
            model_path='kyc.KYCSubmission',
            field='status',
            value='resubmit_required',
            event_type='kyc.resubmit_required',
            user_field='user_id',
            data_fields=['submission_id', 'reason'],
        ),
        # High-risk flag — notify admin
        SignalMap(
            model_path='kyc.KYCRiskProfile',
            field='risk_level',
            value='high',
            event_type='kyc.high_risk_flagged',
            user_field='user_id',
            data_fields=['risk_score', 'risk_factors'],
            notify_admin=True,
        ),
    ]

    event_maps = [
        EventMap(
            event_type='kyc.approved',
            notification_type='kyc_approved',
            title_template='KYC Verified ✅',
            message_template='আপনার পরিচয় সফলভাবে verified হয়েছে। এখন সব সুবিধা ব্যবহার করুন।',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='kyc.rejected',
            notification_type='kyc_rejected',
            title_template='KYC Rejected ❌',
            message_template='আপনার KYC reject হয়েছে। কারণ: {rejection_reason}. আবার submit করুন।',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='kyc.submitted',
            notification_type='kyc_submitted',
            title_template='KYC Documents Submitted',
            message_template='আপনার KYC documents পাওয়া গেছে। সাধারণত ১-২ কার্যদিবসের মধ্যে verified হবে।',
            channel='in_app',
            priority='medium',
        ),
        EventMap(
            event_type='kyc.expired',
            notification_type='kyc_expired',
            title_template='KYC Expired — পুনরায় Submit করুন',
            message_template='আপনার KYC মেয়াদ শেষ হয়েছে। নিরবচ্ছিন্ন সেবার জন্য আবার submit করুন।',
            channel='in_app',
            priority='high',
            send_email=True,
        ),
        EventMap(
            event_type='kyc.resubmit_required',
            notification_type='kyc_resubmit',
            title_template='KYC Resubmission Required',
            message_template='আপনার KYC documents পুনরায় জমা দিতে হবে। কারণ: {reason}',
            channel='in_app',
            priority='high',
        ),
    ]

    health_checks = [
        HealthCheck(name='kyc_db', model_path='kyc.KYC'),
        HealthCheck(name='kyc_submission_db', model_path='kyc.KYCSubmission'),
    ]

    allowed_targets = ['notifications', 'users', 'wallet', 'analytics']
