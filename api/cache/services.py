
from api.cache.decorators import cache_data
from django.contrib.auth import get_user_model  # পরিবর্তন করুন এখানে
from api.cache.keys.CacheKeyGenerator import cache_key_generator

# User model এখানে define করুন না
# from api.users.models import User  # [ERROR] এই লাইন সরিয়ে দিন

class UserService:
    @cache_data(timeout=300, key_prefix='user_profile')
    def get_user_profile(self, user_id):
        """Cached user profile with 5 minute TTL"""
        User = get_user_model()  # [OK] ডাইনামিকভাবে User model নিন
        user = User.objects.get(id=user_id)
        return {
            'id': user.id,
            'username': user.username,
            'balance': user.wallet_balance,
            'stats': user.get_stats()
        }
    
    @cache_data(timeout=60, invalidate_on=['user_update'])
    def get_user_stats(self, user_id):
        """Cached user stats with automatic invalidation"""
        # UserStats model import
        from api.users.models import UserStats  # [OK] ফাংশনের ভিতরে import করুন
        return UserStats.objects.filter(user_id=user_id).first()
    
    def update_user_balance(self, user_id, amount):
        """Update user balance and invalidate cache"""
        User = get_user_model()  # [OK] ডাইনামিকভাবে User model নিন
        user = User.objects.get(id=user_id)
        user.wallet_balance += amount
        user.save()
        
        # Invalidate cache
        from api.cache.keys import key_patterns
        key_patterns.invalidate_user_keys(user_id)
        
        return user.wallet_balance

class TaskService:
    @staticmethod
    @cache_data(timeout=30, key_func=lambda *args, **kwargs: 
               cache_key_generator.generate('task_detail', task_id=kwargs['task_id']))
    def get_task_detail(task_id):
        """Cached task detail with custom key"""
        # Task model import
        from api.tasks.models import Task  # [OK] ফাংশনের ভিতরে import করুন
        return Task.objects.get(id=task_id)