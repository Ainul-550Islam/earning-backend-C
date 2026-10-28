from rest_framework import serializers


class TikTokIntegrationSerializer(serializers.Serializer):
    """
    Configuration serializer for a TikTok Events API integration.
    Validates pixel_id + access_token before saving.
    Stored per-SmartLink in the SmartLink's config JSON field.
    """
    pixel_id = serializers.CharField(
        max_length=50,
        help_text='TikTok Pixel ID (numeric string).',
    )
    access_token = serializers.CharField(
        max_length=500,
        write_only=True,
        help_text='TikTok Events API access token.',
    )
    fire_click_event = serializers.BooleanField(
        default=True,
        help_text='Fire ClickButton on every SmartLink click.',
    )
    fire_lead_event = serializers.BooleanField(
        default=True,
        help_text='Fire SubmitForm on lead conversion.',
    )
    fire_purchase_event = serializers.BooleanField(
        default=True,
        help_text='Fire CompletePayment on sale conversion.',
    )
    is_active = serializers.BooleanField(default=True)

    def validate_pixel_id(self, value):
        if not value.strip().isdigit():
            raise serializers.ValidationError(
                'TikTok Pixel ID must be a numeric string.'
            )
        return value.strip()


class SnapchatIntegrationSerializer(serializers.Serializer):
    """Configuration for Snapchat Conversions API per-SmartLink."""
    pixel_id = serializers.CharField(max_length=100)
    access_token = serializers.CharField(max_length=500, write_only=True)
    fire_page_view = serializers.BooleanField(default=True)
    fire_sign_up = serializers.BooleanField(default=True)
    fire_purchase = serializers.BooleanField(default=True)
    is_active = serializers.BooleanField(default=True)

    def validate_pixel_id(self, value):
        if not value.strip():
            raise serializers.ValidationError('Snapchat Pixel ID must not be blank.')
        return value.strip()


class FacebookPixelIntegrationSerializer(serializers.Serializer):
    """Configuration for Facebook/Meta Conversions API (CAPI) per-SmartLink."""
    pixel_id = serializers.CharField(
        max_length=50,
        help_text='Facebook Pixel ID (numeric string).',
    )
    access_token = serializers.CharField(max_length=500, write_only=True)
    fire_page_view = serializers.BooleanField(
        default=True,
        help_text='Fire PageView on SmartLink click.',
    )
    fire_lead = serializers.BooleanField(default=True)
    fire_purchase = serializers.BooleanField(default=True)
    test_event_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default='',
        help_text='Facebook test event code for development/staging.',
    )
    is_active = serializers.BooleanField(default=True)

    def validate_pixel_id(self, value):
        if not value.strip().isdigit():
            raise serializers.ValidationError(
                'Facebook Pixel ID must be a numeric string.'
            )
        return value.strip()


class GoogleAdsIntegrationSerializer(serializers.Serializer):
    """Configuration for Google Ads Conversion Tracking per-SmartLink."""
    google_ads_id = serializers.CharField(
        max_length=20,
        help_text='Google Ads Account ID (e.g. 123-456-7890).',
    )
    conversion_label = serializers.CharField(
        max_length=100,
        help_text='Google Ads conversion action label.',
    )
    measurement_id = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        default='',
        help_text='GA4 Measurement ID (G-XXXXXXXXXX).',
    )
    api_secret = serializers.CharField(max_length=100, write_only=True, required=False, allow_blank=True)
    default_conversion_value = serializers.FloatField(
        default=0.0,
        help_text='Default conversion value when payout is not available.',
    )
    currency = serializers.CharField(max_length=3, default='USD')
    is_active = serializers.BooleanField(default=True)


class PushNetworkIntegrationSerializer(serializers.Serializer):
    """
    Configuration for push network sub-ID extraction.
    Tells the router which URL params map to which sub IDs for each push network.
    """
    SUPPORTED_NETWORKS = [
        ('propellerads', 'PropellerAds'),
        ('zeropark', 'Zeropark'),
        ('richadz', 'RichAds'),
        ('evadav', 'EvaDav'),
        ('adsterra', 'Adsterra'),
        ('custom', 'Custom'),
    ]
    network = serializers.ChoiceField(choices=SUPPORTED_NETWORKS)
    click_id_param = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        help_text='Query param name for click ID (required for custom network).',
    )
    sub1_param = serializers.CharField(max_length=50, required=False, allow_blank=True)
    sub2_param = serializers.CharField(max_length=50, required=False, allow_blank=True)
    sub3_param = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if attrs.get('network') == 'custom' and not attrs.get('click_id_param'):
            raise serializers.ValidationError(
                'click_id_param is required for custom push network.'
            )
        return attrs


class TwitterAdsIntegrationSerializer(serializers.Serializer):
    """Configuration for Twitter / X Ads Conversion API per-SmartLink."""
    pixel_id        = serializers.CharField(
        max_length=50,
        help_text='Twitter Ads pixel ID from Ads Manager.',
    )
    access_token    = serializers.CharField(max_length=500, write_only=True)
    fire_page_view  = serializers.BooleanField(default=True)
    fire_lead       = serializers.BooleanField(default=True)
    fire_purchase   = serializers.BooleanField(default=True)
    fire_sign_up    = serializers.BooleanField(default=False)
    is_active       = serializers.BooleanField(default=True)


class GA4IntegrationSerializer(serializers.Serializer):
    """Configuration for GA4 Measurement Protocol per-SmartLink."""
    measurement_id    = serializers.CharField(
        max_length=20,
        help_text='GA4 Measurement ID — starts with G- (e.g. G-XXXXXXXXXX).',
    )
    api_secret        = serializers.CharField(max_length=100, write_only=True)
    fire_page_view    = serializers.BooleanField(default=True)
    fire_generate_lead = serializers.BooleanField(default=True)
    fire_purchase     = serializers.BooleanField(default=True)
    fire_sign_up      = serializers.BooleanField(default=False)
    is_active         = serializers.BooleanField(default=True)

    def validate_measurement_id(self, value):
        if not value.upper().startswith('G-'):
            raise serializers.ValidationError(
                "GA4 Measurement ID must start with 'G-'."
            )
        return value.upper()


class AllIntegrationsSerializer(serializers.Serializer):
    """
    Umbrella serializer — returns all integrations configured for a SmartLink.
    Each key is optional (only configured integrations are present).
    """
    tiktok       = TikTokIntegrationSerializer(required=False, allow_null=True)
    snapchat     = SnapchatIntegrationSerializer(required=False, allow_null=True)
    facebook     = FacebookPixelIntegrationSerializer(required=False, allow_null=True)
    google_ads   = GoogleAdsIntegrationSerializer(required=False, allow_null=True)
    twitter      = TwitterAdsIntegrationSerializer(required=False, allow_null=True)
    ga4          = GA4IntegrationSerializer(required=False, allow_null=True)
    push_network = PushNetworkIntegrationSerializer(required=False, allow_null=True)


class IntegrationTestResultSerializer(serializers.Serializer):
    """Result returned by the test-integration action."""
    integration = serializers.CharField()
    success = serializers.BooleanField()
    http_status = serializers.IntegerField(allow_null=True)
    message = serializers.CharField()
    latency_ms = serializers.FloatField(allow_null=True)
