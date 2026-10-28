from rest_framework import serializers
from django.utils import timezone
from api.smartlink.models.publisher import PublisherAllowList


class PublisherAllowListSerializer(serializers.ModelSerializer):
    """
    Serializer for PublisherAllowList records.
    Controls which offer categories and advertisers a publisher can access.
    Admin-only write access — publishers read their own allow list.
    """
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    granted_by_username = serializers.SerializerMethodField()
    advertiser_name = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PublisherAllowList
        fields = [
            'id',
            'publisher',
            'publisher_username',
            'category',
            'advertiser',
            'advertiser_name',
            'is_active',
            'granted_by',
            'granted_by_username',
            'created_at',
            'expires_at',
            'is_expired',
        ]
        read_only_fields = [
            'id',
            'publisher_username',
            'granted_by_username',
            'advertiser_name',
            'is_expired',
            'created_at',
        ]

    def get_granted_by_username(self, obj):
        if obj.granted_by is not None:
            return obj.granted_by.username
        return None

    def get_advertiser_name(self, obj):
        if obj.advertiser is not None:
            return getattr(obj.advertiser, 'name', str(obj.advertiser_id))
        return None

    def get_is_expired(self, obj):
        if obj.expires_at is None:
            return False
        return obj.expires_at < timezone.now()

    def validate_category(self, value):
        if not value.strip():
            raise serializers.ValidationError('Category must not be blank.')
        return value.strip().lower()

    def validate(self, attrs):
        publisher = attrs.get('publisher')
        category = attrs.get('category')
        advertiser = attrs.get('advertiser')
        qs = PublisherAllowList.objects.filter(
            publisher=publisher,
            category=category,
            advertiser=advertiser,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'An allow list entry for this publisher + category + advertiser already exists.'
            )
        return attrs


class PublisherAllowListBulkCreateSerializer(serializers.Serializer):
    """
    Bulk-create allow list entries for a publisher.
    Accepts a list of categories with optional advertiser scoping.
    """
    publisher = serializers.IntegerField(help_text='Publisher user ID.')
    categories = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=50,
        help_text='List of category names to grant access to.',
    )
    advertiser = serializers.IntegerField(
        allow_null=True,
        required=False,
        default=None,
        help_text='Advertiser ID to scope the grant. Null = all advertisers in category.',
    )
    expires_at = serializers.DateTimeField(
        allow_null=True,
        required=False,
        default=None,
        help_text='Optional expiry date. Null = never expires.',
    )
