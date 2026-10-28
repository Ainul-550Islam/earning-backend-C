from rest_framework import serializers
from api.support.models import SLAPolicy
class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model  = SLAPolicy
        fields = ['id','name','priority_level','first_response_hours','resolution_hours','business_hours_only','is_active','created_at']
        read_only_fields = ['created_at']