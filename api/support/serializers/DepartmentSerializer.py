from rest_framework import serializers
from api.support.models import Department
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Department
        fields = ['id','name','slug','routing_rule','auto_assign','email_address','is_active','created_at']
        read_only_fields = ['created_at']