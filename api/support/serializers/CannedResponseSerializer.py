from rest_framework import serializers
from api.support.models import CannedResponse
class CannedResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CannedResponse
        fields = ['id','shortcut_key','title','content','category','usage_count','is_active','is_global']
        read_only_fields = ['usage_count']