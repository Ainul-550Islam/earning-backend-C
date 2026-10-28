from rest_framework import serializers
from api.smartlink.models.redirect import RedirectChain


class RedirectHopSerializer(serializers.Serializer):
    """
    Single hop in a redirect chain.
    Mirrors the JSON structure stored in RedirectChain.chain.
    """
    step = serializers.IntegerField(help_text='1-based hop index.')
    type = serializers.CharField(
        help_text='Hop type: smartlink | pre_lander | landing_page | offer',
    )
    url = serializers.URLField(max_length=2048)
    ts = serializers.DateTimeField(help_text='ISO-8601 timestamp of this hop.')


class RedirectChainSerializer(serializers.ModelSerializer):
    """
    Full serializer for RedirectChain records.
    Shows the complete multi-hop journey from SmartLink to final offer URL.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)
    hops = RedirectHopSerializer(source='chain', many=True, read_only=True)
    click_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = RedirectChain
        fields = [
            'id',
            'smartlink',
            'smartlink_slug',
            'click',
            'click_id',
            'hops',
            'hop_count',
            'total_time_ms',
            'completed',
            'final_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class RedirectChainListSerializer(serializers.ModelSerializer):
    """
    Compact serializer for redirect chain lists — omits full hop detail.
    """
    smartlink_slug = serializers.CharField(source='smartlink.slug', read_only=True)

    class Meta:
        model = RedirectChain
        fields = [
            'id',
            'smartlink_slug',
            'click',
            'hop_count',
            'total_time_ms',
            'completed',
            'final_url',
            'created_at',
        ]
        read_only_fields = fields
