# api/cms/services/UserService.py
from django.contrib.auth import get_user_model
User = get_user_model()

class UserService:
    @staticmethod
    def get_user(user_id):
        return User.objects.get(pk=user_id)

    @staticmethod
    def search(query, limit=20):
        return User.objects.filter(username__icontains=query)[:limit]

    @staticmethod
    def update_user_profile(user_id, data: dict):
        """Update UserProfile fields for a given user. Thread-safe via select_for_update."""
        try:
            from api.cms.models_new.withdrawal import UserProfile
            from django.db import transaction
            with transaction.atomic():
                profile, _ = UserProfile.objects.select_for_update().get_or_create(
                    user_id=user_id
                )
                for k, v in (data or {}).items():
                    if hasattr(profile, k):
                        setattr(profile, k, v)
                profile.save()
            return profile
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"update_user_profile error: {e}")
            return None

    @staticmethod
    def get_user_profile(user_id):
        """Return UserProfile for an EXISTING user, or None if user doesn't exist."""
        try:
            from api.cms.models_new.withdrawal import UserProfile
            from django.contrib.auth import get_user_model
            _User = get_user_model()
            if not _User.objects.filter(pk=user_id).exists():
                return None
            profile, _ = UserProfile.objects.get_or_create(user_id=user_id)
            return profile
        except Exception:
            return None
