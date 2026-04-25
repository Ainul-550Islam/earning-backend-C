# api/payment_gateways/resources.py
# Django Import-Export resources for bulk admin operations
# pip install django-import-export

import logging
logger = logging.getLogger(__name__)

try:
    from import_export import resources, fields
    from import_export.widgets import ForeignKeyWidget, DateTimeWidget
    IMPORT_EXPORT_AVAILABLE = True
except ImportError:
    IMPORT_EXPORT_AVAILABLE = False
    logger.debug('django-import-export not installed. Bulk import/export disabled.')


if IMPORT_EXPORT_AVAILABLE:

    class GatewayTransactionResource(resources.ModelResource):
        """
        Import/Export resource for GatewayTransaction.
        Allows bulk export of transactions as CSV/XLSX.
        Admin: Payment Gateways > Gateway Transactions > Export
        """
        user_email = fields.Field(
            column_name='user_email',
            attribute='user',
            widget=ForeignKeyWidget(model='auth.User', field='email'),
        )

        class Meta:
            model        = 'payment_gateways.GatewayTransaction'
            import_id_fields = ('reference_id',)
            fields       = (
                'id', 'user_email', 'transaction_type', 'gateway',
                'amount', 'fee', 'net_amount', 'currency', 'status',
                'reference_id', 'gateway_reference', 'completed_at', 'created_at',
            )
            export_order = fields

        def get_export_queryset(self, *args, **kwargs):
            return super().get_queryset(*args, **kwargs).select_related('user')

        def dehydrate_amount(self, obj):
            return float(obj.amount)

        def dehydrate_fee(self, obj):
            return float(obj.fee)

        def dehydrate_net_amount(self, obj):
            return float(obj.net_amount)


    class PayoutRequestResource(resources.ModelResource):
        """
        Import/Export resource for PayoutRequest.
        Allows bulk export of payout requests.
        Admin: Payment Gateways > Payout Requests > Export
        """
        user_email = fields.Field(
            column_name='user_email',
            attribute='user',
            widget=ForeignKeyWidget(model='auth.User', field='email'),
        )

        class Meta:
            model        = 'payment_gateways.PayoutRequest'
            import_id_fields = ('reference_id',)
            fields       = (
                'id', 'user_email', 'amount', 'fee', 'net_amount', 'currency',
                'payout_method', 'account_number', 'status', 'reference_id',
                'gateway_reference', 'processed_at', 'created_at', 'admin_notes',
            )
            export_order = fields

        def get_export_queryset(self, *args, **kwargs):
            return super().get_queryset(*args, **kwargs).select_related('user')

        def dehydrate_amount(self, obj):
            return float(obj.amount)

        def dehydrate_net_amount(self, obj):
            return float(obj.net_amount)


    class DepositRequestResource(resources.ModelResource):
        """Export deposit requests for reconciliation and reporting."""
        user_email = fields.Field(
            column_name='user_email',
            attribute='user',
            widget=ForeignKeyWidget(model='auth.User', field='email'),
        )

        class Meta:
            model   = 'payment_gateways.DepositRequest'
            fields  = (
                'id', 'user_email', 'gateway', 'amount', 'fee', 'net_amount',
                'currency', 'status', 'reference_id', 'gateway_ref',
                'initiated_at', 'completed_at',
            )

        def dehydrate_amount(self, obj):
            return float(obj.amount)


    class ConversionResource(resources.ModelResource):
        """Export conversions for publisher earnings reports."""
        publisher_email = fields.Field(
            column_name='publisher_email',
            attribute='publisher',
            widget=ForeignKeyWidget(model='auth.User', field='email'),
        )
        offer_name = fields.Field(
            column_name='offer_name',
            attribute='offer',
            widget=ForeignKeyWidget(model='payment_gateways_offers.Offer', field='name'),
        )

        class Meta:
            model  = 'payment_gateways_tracking.Conversion'
            fields = (
                'id', 'publisher_email', 'offer_name', 'conversion_id',
                'conversion_type', 'status', 'payout', 'cost', 'revenue',
                'currency', 'country_code', 'publisher_paid', 'created_at',
            )

        def dehydrate_payout(self, obj):
            return float(obj.payout)

else:
    # Stub classes when django-import-export is not installed
    class GatewayTransactionResource: pass
    class PayoutRequestResource: pass
    class DepositRequestResource: pass
    class ConversionResource: pass
