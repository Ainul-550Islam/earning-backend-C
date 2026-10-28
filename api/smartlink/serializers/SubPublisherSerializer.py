"""
SmartLink SubPublisher Serializer
==================================
Serializes the SubPublisher referral chain model.
Used by SubPublisherViewSet for the publisher self-serve referral API.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from api.smartlink.models.publisher import SubPublisher

User = get_user_model()


class SubPublisherReadSerializer(serializers.ModelSerializer):
    """
    Read-only view of a SubPublisher relationship.
    Returns the parent's perspective: who did they refer, what commission do they earn.
    """
    parent_username = serializers.SerializerMethodField()
    child_username  = serializers.SerializerMethodField()
    child_email     = serializers.SerializerMethodField()

    class Meta:
        model = SubPublisher
        fields = [
            'id',
            'parent_username',
            'child_username',
            'child_email',
            'commission_type',
            'commission_pct',
            'commission_flat',
            'is_active',
            'referral_code',
            'notes',
            'lifetime_earned',
            'created_at',
            'approved_at',
        ]
        read_only_fields = fields

    def get_parent_username(self, obj):
        return obj.parent_publisher.username

    def get_child_username(self, obj):
        return obj.child_publisher.username

    def get_child_email(self, obj):
        # Only expose to admin or the parent publisher themselves
        request = self.context.get('request')
        if request and (
            request.user.is_staff
            or request.user.pk == obj.parent_publisher_id
        ):
            return obj.child_publisher.email
        return '***@***'


class SubPublisherCreateSerializer(serializers.Serializer):
    """
    Input for a publisher to register a referral relationship
    (child publisher uses parent's referral_code during registration).
    """
    referral_code = serializers.CharField(max_length=20)

    def validate_referral_code(self, value):
        if not SubPublisher.objects.filter(
            referral_code=value, is_active=True
        ).exists():
            raise serializers.ValidationError(
                'Invalid or inactive referral code.'
            )
        return value


class SubPublisherAdminSerializer(serializers.ModelSerializer):
    """
    Admin serializer: full read/write on SubPublisher relationships.
    Allows setting commission rates and approving referral chains.
    """
    parent_username = serializers.SerializerMethodField()
    child_username  = serializers.SerializerMethodField()

    class Meta:
        model = SubPublisher
        fields = [
            'id',
            'parent_publisher',
            'parent_username',
            'child_publisher',
            'child_username',
            'commission_type',
            'commission_pct',
            'commission_flat',
            'is_active',
            'referral_code',
            'notes',
            'lifetime_earned',
            'created_at',
            'approved_at',
        ]
        read_only_fields = [
            'id', 'referral_code', 'lifetime_earned',
            'created_at', 'approved_at',
            'parent_username', 'child_username',
        ]

    def get_parent_username(self, obj):
        return obj.parent_publisher.username

    def get_child_username(self, obj):
        return obj.child_publisher.username


class SubPublisherEarningsSerializer(serializers.Serializer):
    """
    Summary of earnings from sub-publisher referrals.
    Returned by the /my-referrals/earnings/ endpoint.
    """
    total_referred       = serializers.IntegerField()
    active_referred      = serializers.IntegerField()
    lifetime_commission  = serializers.DecimalField(max_digits=14, decimal_places=4)
    pending_commission   = serializers.DecimalField(max_digits=14, decimal_places=4)
    this_month_commission = serializers.DecimalField(max_digits=14, decimal_places=4)
    referral_code        = serializers.CharField()
    referral_link        = serializers.URLField()
