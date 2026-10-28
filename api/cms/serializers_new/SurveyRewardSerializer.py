# api/cms/serializers_new/SurveyRewardSerializer.py
"""
Serializers for Survey Reward Management Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
from ..models_new.profile_surveys import SurveyCompletion, SurveyTemplate

User = get_user_model()


class SurveyRewardSerializer(serializers.ModelSerializer):
    """Basic survey reward serializer"""
    class Meta:
        model = SurveyReward
        fields = [
            'uuid', 'survey', 'name', 'description', 'reward_type',
            'base_amount', 'bonus_amount', 'currency', 'status',
            'start_date', 'end_date', 'total_paid', 'times_paid'
        ]
        read_only_fields = ['uuid', 'total_paid', 'times_paid', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate reward configuration"""
        if data.get('base_amount', 0) <= 0:
            raise serializers.ValidationError("Base amount must be greater than 0")
        
        if data.get('bonus_amount', 0) < 0:
            raise serializers.ValidationError("Bonus amount cannot be negative")
        
        if data.get('min_quality_for_bonus', 0) and not (0 <= data['min_quality_for_bonus'] <= 1):
            raise serializers.ValidationError("Quality for bonus must be between 0 and 1")
        
        return data


class SurveyRewardDetailSerializer(serializers.ModelSerializer):
    """Detailed survey reward serializer with relationships"""
    survey_title = serializers.CharField(source='survey.title', read_only=True)
    survey_uuid = serializers.UUIDField(source='survey.uuid', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    utilization_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = SurveyReward
        fields = [
            'uuid', 'survey', 'name', 'description', 'reward_type',
            'base_amount', 'bonus_amount', 'currency', 'currency_symbol',
            'min_quality_for_bonus', 'completion_time_threshold', 'speed_bonus_amount',
            'max_total_payout', 'daily_payout_limit', 'status',
            'start_date', 'end_date', 'total_paid', 'times_paid',
            'survey_title', 'survey_uuid', 'utilization_rate'
        ]
        read_only_fields = ['uuid', 'total_paid', 'times_paid', 'created_at', 'updated_at']
    
    def get_utilization_rate(self, obj):
        """Calculate utilization rate"""
        if obj.total_budget > 0:
            return round((obj.allocated_amount / obj.total_budget) * 100, 2)
        return 0


class RewardTransactionSerializer(serializers.ModelSerializer):
    """Basic reward transaction serializer"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    survey_title = serializers.CharField(source='survey_completion.survey.title', read_only=True)
    reward_config_name = serializers.CharField(source='reward_config.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    
    class Meta:
        model = RewardTransaction
        fields = [
            'uuid', 'user', 'user_username', 'survey_completion', 'survey_title',
            'reward_config', 'reward_config_name', 'transaction_type',
            'amount', 'currency', 'currency_symbol', 'description',
            'reference_id', 'status', 'processed_at', 'paid_at',
            'reviewed_by', 'reviewed_at', 'review_notes', 'created_at'
        ]
        read_only_fields = ['uuid', 'processed_at', 'paid_at', 'reviewed_at', 'created_at', 'updated_at']


class RewardTransactionDetailSerializer(serializers.ModelSerializer):
    """Detailed reward transaction serializer"""
    user_username = serializers.CharField(source='user.username', read_only=True)
    survey_title = serializers.CharField(source='survey_completion.survey.title', read_only=True)
    survey_uuid = serializers.UUIDField(source='survey_completion.survey.uuid', read_only=True)
    reward_config_name = serializers.CharField(source='reward_config.name', read_only=True)
    reward_config_type = serializers.CharField(source='reward_config.reward_type', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    reviewer_username = serializers.CharField(source='reviewed_by.username', read_only=True, allow_null=True, default=None)
    
    class Meta:
        model = RewardTransaction
        fields = [
            'uuid', 'user', 'user_username', 'survey_completion', 'survey_title',
            'survey_uuid', 'reward_config', 'reward_config_name', 'reward_config_type',
            'transaction_type', 'amount', 'currency', 'currency_symbol',
            'description', 'reference_id', 'status', 'processed_at', 'paid_at',
            'reviewed_by', 'reviewer_username', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'processed_at', 'paid_at', 'reviewed_at', 'created_at', 'updated_at']


class RewardPoolSerializer(serializers.ModelSerializer):
    """Basic reward pool serializer"""
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    remaining_budget = serializers.SerializerMethodField()
    available_budget = serializers.SerializerMethodField()
    utilization_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = RewardPool
        fields = [
            'uuid', 'name', 'description', 'total_budget', 'currency',
            'currency_symbol', 'allocated_amount', 'paid_amount', 'remaining_budget',
            'available_budget', 'utilization_rate', 'auto_refill',
            'refill_amount', 'refill_threshold', 'is_active',
            'start_date', 'end_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_remaining_budget(self, obj):
        """Calculate remaining budget"""
        return obj.total_budget - obj.allocated_amount
    
    def get_available_budget(self, obj):
        """Calculate available budget"""
        return obj.total_budget - obj.allocated_amount - obj.paid_amount
    
    def get_utilization_rate(self, obj):
        """Calculate utilization rate"""
        if obj.total_budget > 0:
            return round((obj.allocated_amount / obj.total_budget) * 100, 2)
        return 0


class RewardPoolDetailSerializer(serializers.ModelSerializer):
    """Detailed reward pool serializer"""
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)
    remaining_budget = serializers.SerializerMethodField()
    available_budget = serializers.SerializerMethodField()
    utilization_rate = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    
    class Meta:
        model = RewardPool
        fields = [
            'uuid', 'name', 'description', 'total_budget', 'currency',
            'currency_symbol', 'allocated_amount', 'paid_amount', 'remaining_budget',
            'available_budget', 'utilization_rate', 'auto_refill',
            'refill_amount', 'refill_threshold', 'is_active',
            'start_date', 'end_date', 'created_at', 'updated_at',
            'recent_transactions'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_remaining_budget(self, obj):
        """Calculate remaining budget"""
        return obj.total_budget - obj.allocated_amount
    
    def get_available_budget(self, obj):
        """Calculate available budget"""
        return obj.total_budget - obj.allocated_amount - obj.paid_amount
    
    def get_utilization_rate(self, obj):
        """Calculate utilization rate"""
        if obj.total_budget > 0:
            return round((obj.allocated_amount / obj.total_budget) * 100, 2)
        return 0
    
    def get_recent_transactions(self, obj):
        """Get recent transactions for this pool"""
        from ..models_new.survey_rewards import RewardTransaction
        
        recent_transactions = RewardTransaction.objects.filter(
            reward_config__survey__rewardpool=obj,
            status='paid'
        ).order_by('-created_at')[:10]
        
        return RewardTransactionSerializer(recent_transactions, many=True).data


class RewardTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reward transactions"""
    class Meta:
        model = RewardTransaction
        fields = [
            'user', 'survey_completion', 'reward_config',
            'transaction_type', 'amount', 'currency', 'description',
            'reference_id'
        ]
    
    def validate(self, data):
        """Validate transaction creation"""
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        
        if not data.get('user'):
            raise serializers.ValidationError("User is required")
        
        if not data.get('reward_config'):
            raise serializers.ValidationError("Reward configuration is required")
        
        return data


class RewardPoolCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reward pools"""
    class Meta:
        model = RewardPool
        fields = [
            'name', 'description', 'total_budget', 'currency',
            'auto_refill', 'refill_amount', 'refill_threshold',
            'start_date', 'end_date'
        ]
    
    def validate(self, data):
        """Validate pool creation"""
        if data.get('total_budget', 0) <= 0:
            raise serializers.ValidationError("Total budget must be greater than 0")
        
        if data.get('refill_amount', 0) < 0:
            raise serializers.ValidationError("Refill amount cannot be negative")
        
        if data.get('refill_threshold', 0) < 0:
            raise serializers.ValidationError("Refill threshold cannot be negative")
        
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("End date must be after start date")
        
        return data
