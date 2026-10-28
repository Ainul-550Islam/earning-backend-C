from rest_framework import serializers
from api.smartlink.models.extensions.smartlink_schedule import SmartLinkTemplate


class SmartLinkTemplateSerializer(serializers.ModelSerializer):
    """
    Full serializer for SmartLinkTemplate.
    Publishers save full SmartLink configs as reusable templates.
    """
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    category = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkTemplate
        fields = [
            'id',
            'publisher',
            'publisher_username',
            'name',
            'description',
            'is_public',
            'config',
            'use_count',
            'category',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'publisher',
            'publisher_username',
            'use_count',
            'created_at',
            'updated_at',
        ]

    def get_category(self, obj):
        """Extract smartlink type from the config JSON."""
        return obj.config.get('type', 'general')

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                'Template name must be at least 3 characters.'
            )
        return value.strip()

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('config must be a JSON object.')
        # Require at minimum a SmartLink type
        if 'type' not in value and 'name' not in value:
            raise serializers.ValidationError(
                'config must contain at least "name" or "type".'
            )
        return value


class SmartLinkTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight template list serializer — omits full config blob."""
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    category = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkTemplate
        fields = [
            'id',
            'publisher_username',
            'name',
            'description',
            'is_public',
            'use_count',
            'category',
            'created_at',
        ]
        read_only_fields = fields

    def get_category(self, obj):
        return obj.config.get('type', 'general')


class ApplyTemplateSerializer(serializers.Serializer):
    """
    Input serializer for the apply-template action.
    Allows the caller to override specific config keys at apply time.
    """
    override = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        default=dict,
        help_text=(
            'Optional key-value overrides applied on top of the template config. '
            'Example: {"name": "My New Link", "redirect_type": "302"}'
        ),
    )
