# api/referral/resources.py
# Django import-export resources for admin bulk import/export
# pip install django-import-export
# ============================================================

import logging

logger = logging.getLogger(__name__)

try:
    from import_export import resources, fields
    from import_export.widgets import ForeignKeyWidget, DecimalWidget, DateTimeWidget

    class ReferralResource(resources.ModelResource):
        """
        Import/Export resource for Referral model.
        Allows bulk CSV import of referral relationships.
        """
        referrer_username = fields.Field(
            column_name='referrer',
            attribute='referrer',
            widget=ForeignKeyWidget(
                __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model(),
                field='username'
            )
        )
        referred_user_username = fields.Field(
            column_name='referred_user',
            attribute='referred_user',
            widget=ForeignKeyWidget(
                __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model(),
                field='username'
            )
        )

        class Meta:
            from api.referral.models import Referral
            model = Referral
            fields = (
                'id', 'referrer_username', 'referred_user_username',
                'level', 'signup_bonus_given', 'total_commission_earned',
                'is_suspicious', 'created_at',
            )
            export_order = fields
            import_id_fields = ['referred_user_username']
            skip_unchanged = True
            report_skipped = True


    class ReferralEarningResource(resources.ModelResource):
        """Export referral earnings to CSV/Excel."""
        referrer_username = fields.Field(
            column_name='referrer',
            attribute='referrer',
            widget=ForeignKeyWidget(
                __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model(),
                field='username'
            )
        )

        class Meta:
            from api.referral.models import ReferralEarning
            model = ReferralEarning
            fields = (
                'id', 'referrer_username', 'level', 'amount',
                'commission_rate', 'source_amount', 'source_type',
                'status', 'created_at',
            )
            export_order = fields


    class CommissionLogResource(resources.ModelResource):
        """Export commission logs for accounting."""

        class Meta:
            from api.referral.models import CommissionLog
            model = CommissionLog
            fields = (
                'id', 'user__username', 'referred_user__username',
                'level', 'amount', 'commission_rate', 'status',
                'action_type', 'wallet_transaction_id', 'created_at',
            )
            export_order = fields


    class ReferralCodeResource(resources.ModelResource):
        """Import/export referral codes in bulk."""

        class Meta:
            from api.referral.models import ReferralCode
            model = ReferralCode
            fields = (
                'id', 'user__username', 'code', 'custom_code',
                'clicks', 'conversions', 'is_active', 'is_primary',
                'created_at',
            )
            export_order = fields
            import_id_fields = ['code']
            skip_unchanged = True


    IMPORT_EXPORT_AVAILABLE = True
    logger.info('[Resources] django-import-export available')

except ImportError:
    # django-import-export not installed
    IMPORT_EXPORT_AVAILABLE = False
    logger.debug('[Resources] django-import-export not installed — resources disabled')

    # Stub classes for when import_export is not available
    class ReferralResource: pass
    class ReferralEarningResource: pass
    class CommissionLogResource: pass
    class ReferralCodeResource: pass