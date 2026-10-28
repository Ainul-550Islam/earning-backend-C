"""
Rollout manager for Feature Flags & A/B Testing.
"""
from django.db import models

from ..models.rollout_rule import RolloutRule


class RolloutManager(models.Manager):
    """
    Custom manager for RolloutRule model.
    """
    
    def by_flag(self, flag_id):
        """
        Get rules by flag.
        
        Args:
            flag_id: Flag ID
            
        Returns:
            QuerySet
        """
        return self.filter(flag_id=flag_id)
    
    def by_type(self, rule_type):
        """
        Get rules by type.
        
        Args:
            rule_type: Rule type
            
        Returns:
            QuerySet
        """
        return self.filter(rule_type=rule_type)
    
    def by_field(self, field):
        """
        Get rules by field.
        
        Args:
            field: Field name
            
        Returns:
            QuerySet
        """
        return self.filter(field=field)
    
    def active(self):
        """
        Get active rules.
        
        Returns:
            QuerySet
        """
        return self.filter(is_active=True)
    
    def inactive(self):
        """
        Get inactive rules.
        
        Returns:
            QuerySet
        """
        return self.filter(is_active=False)
    
    def by_priority(self, priority):
        """
        Get rules by priority.
        
        Args:
            priority: Priority value
            
        Returns:
            QuerySet
        """
        return self.filter(priority=priority)
    
    def search(self, query):
        """
        Search rules by description.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet
        """
        return self.filter(description__icontains=query)
