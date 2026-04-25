# api/payment_gateways/offers/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import Offer, Campaign, PublisherOfferApplication, OfferCreative

class OfferListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for offer listings."""
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    is_active          = serializers.BooleanField(read_only=True)
    payout_display     = serializers.CharField(read_only=True)
    advertiser_email   = serializers.EmailField(source='advertiser.email', read_only=True)

    class Meta:
        model  = Offer
        fields = ['id','name','slug','offer_type','offer_type_display','status',
                  'publisher_payout','advertiser_cost','currency','payout_display',
                  'category','target_countries','target_devices',
                  'total_clicks','total_conversions','conversion_rate','epc',
                  'thumbnail','app_icon_url','is_active','advertiser_email',
                  'requires_approval','is_public','created_at']

class OfferDetailSerializer(serializers.ModelSerializer):
    """Full offer detail for publishers and admins."""
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    is_active          = serializers.BooleanField(read_only=True)
    payout_display     = serializers.CharField(read_only=True)
    creatives          = serializers.SerializerMethodField()

    class Meta:
        model  = Offer
        fields = '__all__'
        read_only_fields = ['total_clicks','total_conversions','total_revenue',
                            'conversion_rate','epc','created_at','slug']

    def get_creatives(self, obj):
        return OfferCreativeSerializer(
            obj.creatives.filter(is_active=True), many=True
        ).data

class OfferCreateSerializer(serializers.ModelSerializer):
    """For advertisers creating new offers."""
    class Meta:
        model  = Offer
        fields = ['name','description','short_desc','offer_type','preview_type',
                  'destination_url','tracking_url','preview_url','postback_url',
                  'publisher_payout','advertiser_cost','currency','payout_model',
                  'target_countries','blocked_countries','target_devices','target_os',
                  'daily_cap','monthly_cap','total_cap','daily_budget','total_budget',
                  'start_date','end_date','category','is_public','requires_approval',
                  'app_name','app_store_url','app_platform','app_id']

    def validate(self, data):
        payout = data.get('publisher_payout', Decimal('0'))
        cost   = data.get('advertiser_cost', Decimal('0'))
        if payout > cost:
            raise serializers.ValidationError(
                'Publisher payout cannot exceed advertiser cost.'
            )
        return data

    def create(self, validated_data):
        validated_data['advertiser'] = self.context['request'].user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class CampaignSerializer(serializers.ModelSerializer):
    budget_remaining     = serializers.DecimalField(max_digits=12, decimal_places=2,
                           read_only=True, allow_null=True)
    advertiser_email     = serializers.EmailField(source='advertiser.email', read_only=True)
    offers_count         = serializers.SerializerMethodField()
    class Meta:
        model  = Campaign
        fields = ['id','name','advertiser_email','status','total_budget','daily_budget',
                  'spent','currency','start_date','end_date','total_clicks',
                  'total_conversions','total_revenue','budget_remaining','offers_count',
                  'description','created_at']
        read_only_fields = ['spent','total_clicks','total_conversions','total_revenue','created_at']
    def get_offers_count(self, obj):
        return obj.offers.count()

class PublisherApplicationSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True)
    offer_name      = serializers.CharField(source='offer.name', read_only=True)
    class Meta:
        model  = PublisherOfferApplication
        fields = ['id','offer','offer_name','publisher_email','status','message','admin_notes','created_at']
        read_only_fields = ['status','admin_notes','created_at']

class OfferCreativeSerializer(serializers.ModelSerializer):
    size_display = serializers.CharField(source='get_size_display', read_only=True)
    class Meta:
        model  = OfferCreative
        fields = ['id','size','size_display','image_url','html_code','click_url','alt_text','is_active']
