from rest_framework import serializers
from api.support.models import FAQ

class FAQSerializer(serializers.ModelSerializer):
    helpful_ratio = serializers.ReadOnlyField()
    class Meta:
        model  = FAQ
        fields = ['id','question','answer','category','is_active','order','helpful_yes','helpful_no','helpful_ratio','view_count','tags','created_at']
        read_only_fields = ['created_at','helpful_yes','helpful_no','view_count']