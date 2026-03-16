# api/ad_networks/serializers.py
from rest_framework import serializers
from .models import AdNetwork, Offer, OfferCategory


class AdNetworkSerializer(serializers.ModelSerializer):
    """AdNetwork মডেলের জন্য Serializer"""
    
    class Meta:
        model = AdNetwork
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'id')
    
    def validate_rating(self, value):
        """Rating validation"""
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5")
        return value
    
    def validate_commission_rate(self, value):
        """Commission rate validation"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Commission rate must be between 0 and 100")
        return value


class OfferCategorySerializer(serializers.ModelSerializer):
    """OfferCategory মডেলের জন্য Serializer"""
    
    class Meta:
        model = OfferCategory
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'id')
    
    def validate(self, data):
        """Custom validation"""
        if data.get('min_age') and data.get('max_age'):
            if data['min_age'] > data['max_age']:
                raise serializers.ValidationError({
                    'min_age': 'Minimum age cannot be greater than maximum age'
                })
        return data


class OfferSerializer(serializers.ModelSerializer):
    """Offer মডেলের জন্য Serializer"""
    
    # Nested serializers for related fields
    ad_network = AdNetworkSerializer(read_only=True)
    category = OfferCategorySerializer(read_only=True)
    
    # Write-only fields for creation/update
    ad_network_id = serializers.UUIDField(write_only=True)
    category_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Offer
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'id', 'click_count', 'conversion_rate')
    
    def validate_reward_amount(self, value):
        """Reward amount validation"""
        if value <= 0:
            raise serializers.ValidationError("Reward amount must be positive")
        return value
    
    def validate(self, data):
        """Custom validation"""
        # Check if external_id is unique
        if 'external_id' in data:
            if Offer.objects.filter(external_id=data['external_id']).exists():
                raise serializers.ValidationError({
                    'external_id': 'This external ID already exists'
                })
        
        return data


# Minimal serializers if you don't need all fields
class SimpleAdNetworkSerializer(serializers.ModelSerializer):
    """Simplified AdNetwork Serializer"""
    class Meta:
        model = AdNetwork
        fields = ('id', 'name', 'network_type', 'is_active', 'rating', 'min_payout')


class SimpleOfferSerializer(serializers.ModelSerializer):
    """Simplified Offer Serializer"""
    ad_network = SimpleAdNetworkSerializer(read_only=True)
    
    class Meta:
        model = Offer
        fields = ('id', 'title', 'reward_amount', 'reward_currency', 
                  'difficulty', 'estimated_time', 'ad_network')


class SimpleOfferCategorySerializer(serializers.ModelSerializer):
    """Simplified OfferCategory Serializer"""
    class Meta:
        model = OfferCategory
        fields = ('id', 'name', 'slug', 'icon', 'color')