from rest_framework import serializers
from api.support.models import SupportAgent
class AgentSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    email      = serializers.CharField(source='user.email', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    class Meta:
        model  = SupportAgent
        fields = ['id','username','email','department','department_name','role','is_active','is_available','max_concurrent_chats','max_concurrent_tickets','skills','created_at']
        read_only_fields = ['created_at']