from rest_framework import serializers
from api.support.models import AutomationRule, AutomationCondition, AutomationAction
class AutomationConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AutomationCondition
        fields = ['id','field','operator','value']
class AutomationActionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AutomationAction
        fields = ['id','action_type','value','order']
class AutomationRuleSerializer(serializers.ModelSerializer):
    conditions = AutomationConditionSerializer(many=True, read_only=True)
    actions    = AutomationActionSerializer(many=True, read_only=True)
    class Meta:
        model  = AutomationRule
        fields = ['id','name','description','trigger','conditions_logic','is_active','priority','stop_on_match','run_count','conditions','actions','created_at']
        read_only_fields = ['run_count','created_at']