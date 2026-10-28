# api/djoyalty/serializers/SocialSerializer.py
"""
Djoyalty Social Serializers -- NEW।
SocialShareReward, CustomerSocialAction, ReviewReward, CustomerReview,
QRCodeEarn, QRCodeScan -- all had ZERO serializers।
"""
from rest_framework import serializers
from django.utils import timezone


# ─── Social Share ─────────────────────────────────────────────────────────────

class SocialShareRewardSerializer(serializers.Serializer):
    """Read-only rule config shown to customers."""
    id             = serializers.IntegerField()
    name           = serializers.CharField()
    platform       = serializers.CharField()
    share_type     = serializers.CharField()
    points_reward  = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_per_day    = serializers.IntegerField()
    requires_proof = serializers.BooleanField()
    is_active      = serializers.BooleanField()
    valid_from     = serializers.DateTimeField(allow_null=True)
    valid_until    = serializers.DateTimeField(allow_null=True)


class CustomerSocialActionSerializer(serializers.Serializer):
    """Customer's logged social share record."""
    id             = serializers.IntegerField()
    platform       = serializers.SerializerMethodField()
    points_awarded = serializers.DecimalField(max_digits=10, decimal_places=2)
    share_url      = serializers.CharField()
    is_verified    = serializers.BooleanField()
    created_at     = serializers.DateTimeField()

    def get_platform(self, obj) -> str:
        return obj.share_reward.platform if obj.share_reward else ''


# ─── Review ───────────────────────────────────────────────────────────────────

class ReviewRewardSerializer(serializers.Serializer):
    """Review earn rule -- shown to customers."""
    id                    = serializers.IntegerField()
    name                  = serializers.CharField()
    review_type           = serializers.CharField()
    points_reward         = serializers.DecimalField(max_digits=10, decimal_places=2)
    bonus_for_photo       = serializers.DecimalField(max_digits=10, decimal_places=2)
    bonus_for_verified    = serializers.DecimalField(max_digits=10, decimal_places=2)
    min_review_length     = serializers.IntegerField()
    max_per_month         = serializers.IntegerField()
    requires_approval     = serializers.BooleanField()
    is_active             = serializers.BooleanField()


class CustomerReviewSerializer(serializers.Serializer):
    """Customer's submitted review record."""
    id              = serializers.IntegerField()
    product_id      = serializers.CharField()
    product_name    = serializers.CharField()
    rating          = serializers.IntegerField()
    title           = serializers.CharField()
    body            = serializers.CharField()
    has_photo       = serializers.BooleanField()
    status          = serializers.CharField()
    points_awarded  = serializers.DecimalField(max_digits=10, decimal_places=2)
    rejection_reason = serializers.CharField(allow_blank=True)
    created_at      = serializers.DateTimeField()


class CustomerReviewCreateSerializer(serializers.Serializer):
    """POST /reviews/submit/ body."""
    review_reward_id = serializers.IntegerField()
    product_id       = serializers.CharField(max_length=200)
    product_name     = serializers.CharField(max_length=200)
    order_id         = serializers.CharField(required=False, allow_blank=True)
    rating           = serializers.IntegerField(min_value=1, max_value=5)
    title            = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body             = serializers.CharField(min_length=20)
    photo_url        = serializers.URLField(required=False, allow_blank=True)

    def validate_body(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError('Review must be at least 20 characters.')
        return value.strip()


# ─── QR Code ─────────────────────────────────────────────────────────────────

class QRCodeEarnSerializer(serializers.Serializer):
    """QR code earn campaign -- public fields only (no code in list view)."""
    id             = serializers.IntegerField()
    name           = serializers.CharField()
    description    = serializers.CharField(allow_blank=True)
    earn_type      = serializers.CharField()
    points_value   = serializers.DecimalField(max_digits=10, decimal_places=2)
    single_use     = serializers.BooleanField()
    max_scans      = serializers.IntegerField(allow_null=True)
    is_active      = serializers.BooleanField()
    valid_from     = serializers.DateTimeField(allow_null=True)
    valid_until    = serializers.DateTimeField(allow_null=True)
    # 'code' field intentionally excluded from list -- returned only on generate


class QRCodeEarnAdminSerializer(QRCodeEarnSerializer):
    """Admin view includes raw code string."""
    code        = serializers.CharField()
    total_scans = serializers.IntegerField(default=0)  # annotated


class QRCodeScanSerializer(serializers.Serializer):
    """Customer's scan record."""
    id             = serializers.IntegerField()
    qr_name        = serializers.SerializerMethodField()
    points_awarded = serializers.DecimalField(max_digits=10, decimal_places=2)
    location       = serializers.CharField(allow_blank=True)
    scanned_at     = serializers.DateTimeField()

    def get_qr_name(self, obj) -> str:
        return obj.qr_code.name if obj.qr_code else ''


class QRCodeScanSubmitSerializer(serializers.Serializer):
    """POST /qr/scan/ body."""
    code     = serializers.CharField(max_length=100)
    location = serializers.CharField(required=False, allow_blank=True, max_length=200)
