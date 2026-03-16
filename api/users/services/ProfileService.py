from ..models import UserProfile
from ..serializers import UserSerializer, UserProfileSerializer

class ProfileService:
    
    @staticmethod
    def update_profile(user, profile_data):
        """Update user profile"""
        profile, created = UserProfile.objects.get_or_create(user=user)
        # serializer = 'users.User'(profile, data=profile_data, partial=True)
        serializer = UserSerializer(profile, data=profile_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return serializer.data
    
    @staticmethod
    def get_profile(user):
        """Get user profile"""
        profile, created = UserProfile.objects.get_or_create(user=user)
        # serializer = 'users.User'(profile)
        serializer = UserSerializer(profile)
        return serializer.data