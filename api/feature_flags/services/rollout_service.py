"""
Rollout service for Feature Flags & A/B Testing.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone

from ..models.rollout_rule import RolloutRule
from ..models.feature_flag import FeatureFlag


class RolloutService:
    """
    Service for managing rollout rules.
    """
    
    def __init__(self):
        """Initialize the rollout service."""
        pass
    
    def create_rule(self, data: Dict[str, Any]) -> RolloutRule:
        """
        Create a new rollout rule.
        
        Args:
            data: Rule data
            
        Returns:
            Created RolloutRule instance
        """
        return RolloutRule.objects.create(
            flag_id=data['flag'],
            rule_type=data['rule_type'],
            field=data['field'],
            operator=data['operator'],
            value=data['value'],
            priority=data.get('priority', 0),
            is_active=data.get('is_active', True),
            description=data.get('description', ''),
            metadata=data.get('metadata', {})
        )
    
    def get_rule(self, rule_id: int) -> Optional[RolloutRule]:
        """
        Get a rollout rule by ID.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            RolloutRule instance or None
        """
        try:
            return RolloutRule.objects.get(id=rule_id)
        except RolloutRule.DoesNotExist:
            return None
    
    def get_rules(self, flag_id: Optional[int] = None, is_active: Optional[bool] = None) -> List[RolloutRule]:
        """
        Get rollout rules with optional filters.
        
        Args:
            flag_id: Optional flag ID filter
            is_active: Optional active status filter
            
        Returns:
            List of RolloutRule instances
        """
        queryset = RolloutRule.objects.all()
        
        if flag_id:
            queryset = queryset.filter(flag_id=flag_id)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        return list(queryset.order_by('-priority', 'created_at'))
    
    def update_rule(self, rule_id: int, data: Dict[str, Any]) -> bool:
        """
        Update a rollout rule.
        
        Args:
            rule_id: Rule ID
            data: Rule data to update
            
        Returns:
            True if successful
        """
        rule = self.get_rule(rule_id)
        
        if not rule:
            return False
        
        for key, value in data.items():
            if hasattr(rule, key) and key not in ['id', 'flag', 'created_at', 'updated_at']:
                setattr(rule, key, value)
        
        rule.save()
        
        # Clear flag cache
        from ..flag_engine import FlagEngine
        engine = FlagEngine()
        engine.clear_flag_cache(rule.flag.name)
        
        return True
    
    def delete_rule(self, rule_id: int) -> bool:
        """
        Delete a rollout rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if successful
        """
        rule = self.get_rule(rule_id)
        
        if not rule:
            return False
        
        # Clear flag cache
        from ..flag_engine import FlagEngine
        engine = FlagEngine()
        engine.clear_flag_cache(rule.flag.name)
        
        rule.delete()
        
        return True
    
    def activate_rule(self, rule_id: int) -> bool:
        """
        Activate a rollout rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if successful
        """
        return self.update_rule(rule_id, {'is_active': True})
    
    def deactivate_rule(self, rule_id: int) -> bool:
        """
        Deactivate a rollout rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if successful
        """
        return self.update_rule(rule_id, {'is_active': False})
    
    def evaluate_rules(self, flag_name: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules for a flag.
        
        Args:
            flag_name: Flag name
            context: Context dictionary
            
        Returns:
            List of evaluation results
        """
        try:
            flag = FeatureFlag.objects.get(name=flag_name)
        except FeatureFlag.DoesNotExist:
            return []
        
        rules = RolloutRule.objects.filter(flag=flag, is_active=True).order_by('-priority')
        
        results = []
        
        for rule in rules:
            results.append({
                'rule_id': rule.id,
                'rule_type': rule.rule_type,
                'field': rule.field,
                'operator': rule.operator,
                'value': rule.value,
                'matched': rule.evaluate(context)
            })
        
        return results
