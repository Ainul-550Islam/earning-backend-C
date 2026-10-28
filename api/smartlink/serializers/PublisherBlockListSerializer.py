from rest_framework import serializers
from api.smartlink.models.publisher import PublisherBlockList


class PublisherBlockListSerializer(serializers.ModelSerializer):
    """
    Serializer for PublisherBlockList records.
    Prevents specific advertisers or offer categories from serving
    to a publisher's traffic. Admin-write, publisher-read.
    """
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    blocked_by_username = serializers.SerializerMethodField()
    advertiser_name = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = PublisherBlockList
        fields = [
            'id',
            'publisher',
            'publisher_username',
            'advertiser',
            'advertiser_name',
            'category',
            'reason',
            'blocked_by',
            'blocked_by_username',
            'is_active',
            'created_at',
            'target_label',
        ]
        read_only_fields = [
            'id',
            'publisher_username',
            'blocked_by_username',
            'advertiser_name',
            'target_label',
            'created_at',
        ]

    def get_blocked_by_username(self, obj):
        if obj.blocked_by is not None:
            return obj.blocked_by.username
        return None

    def get_advertiser_name(self, obj):
        if obj.advertiser is not None:
            return getattr(obj.advertiser, 'name', str(obj.advertiser_id))
        return None

    def get_target_label(self, obj):
        """Human-readable description of what is blocked."""
        if obj.advertiser is not None:
            name = getattr(obj.advertiser, 'name', f'Advertiser #{obj.advertiser_id}')
            return f'Advertiser: {name}'
        if obj.category:
            return f'Category: {obj.category}'
        return 'Unknown target'

    def validate(self, attrs):
        advertiser = attrs.get('advertiser')
        category = attrs.get('category', '')
        if not advertiser and not category:
            raise serializers.ValidationError(
                'At least one of advertiser or category must be specified.'
            )
        return attrs


class PublisherBlockListBulkSerializer(serializers.Serializer):
    """
    Bulk-apply block list entries for a publisher.
    Accepts a list of advertiser IDs or category names.
    """
    publisher = serializers.IntegerField(help_text='Publisher user ID.')
    advertiser_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='List of advertiser IDs to block.',
    )
    categories = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
        help_text='List of offer category names to block.',
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default='',
        help_text='Internal reason for the block.',
    )

    def validate(self, attrs):
        if not attrs.get('advertiser_ids') and not attrs.get('categories'):
            raise serializers.ValidationError(
                'Provide at least one advertiser_id or category to block.'
            )
        return attrs
