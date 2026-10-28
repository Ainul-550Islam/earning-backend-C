# api/cms/viewsets_new/UserProfileViewSet.py
"""
API ViewSets for User Profile and Segmentation Management
"""
from django.db.models import Case
from django.db.models import CharField
from django.db.models import Value
from django.db.models import When
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from django.utils import timezone

from ..models_new.user_profile import UserProfile, UserSegment
from ..services_new.UserSegmentService import UserSegmentService


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Profile management
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['gender', 'country', 'education', 'income_level']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return UserProfile.objects.all().select_related('user')
        return UserProfile.objects.filter(user=user).select_related('user')
    
    def get_serializer_class(self):
        from ..serializers_new.UserProfileSerializer import UserProfileSerializer, UserProfileDetailSerializer
        if self.action == 'list':
            return UserProfileSerializer
        return UserProfileDetailSerializer
    
    def perform_create(self, serializer):
        # Only allow users to create their own profile
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        try:
            profile = request.user.profile
            from ..serializers_new.UserProfileSerializer import UserProfileDetailSerializer
            serializer = UserProfileDetailSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
    
    @action(detail=True, methods=['post'])
    def update_survey_stats(self, request, pk=None):
        """Update survey statistics (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            profile = self.get_object()
            completion_time = request.data.get('completion_time')
            quality_score = request.data.get('quality_score')
            
            if completion_time and quality_score:
                profile.update_survey_stats(
                    completion_time=int(completion_time),
                    quality_score=float(quality_score)
                )
                return Response({'message': 'Survey stats updated'})
            else:
                return Response({'error': 'completion_time and quality_score required'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def demographics(self, request):
        """Get demographic breakdown (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        demographics = {
            'genders': UserProfile.objects.values('gender').annotate(count=Count('id')),
            'countries': UserProfile.objects.values('country').annotate(count=Count('id')).order_by('-count')[:20],
            'education_levels': UserProfile.objects.values('education').annotate(count=Count('id')),
            'income_levels': UserProfile.objects.values('income_level').annotate(count=Count('id')),
            'age_distribution': self._get_age_distribution(),
            'profile_completeness': self._get_completeness_distribution()
        }
        
        return Response(demographics)
    
    def _get_age_distribution(self):
        """Get age group distribution"""
        from django.db.models import Case, When, Value, IntegerField
        from datetime import date
        
        today = date.today()
        
        return UserProfile.objects.annotate(
            age_group=Case(
                When(date_of_birth__year__gte=today.year-18, then=Value('Under 18')),
                When(date_of_birth__year__gte=today.year-25, then=Value('18-24')),
                When(date_of_birth__year__gte=today.year-35, then=Value('25-34')),
                When(date_of_birth__year__gte=today.year-45, then=Value('35-44')),
                When(date_of_birth__year__gte=today.year-55, then=Value('45-54')),
                default=Value('55+'),
                output_field=CharField()
            )
        ).values('age_group').annotate(count=Count('id'))
    
    def _get_completeness_distribution(self):
        """Get profile completeness distribution"""
        return UserProfile.objects.annotate(
            completeness_range=Case(
                When(profile_completeness__lt=25, then=Value('0-25%')),
                When(profile_completeness__lt=50, then=Value('25-50%')),
                When(profile_completeness__lt=75, then=Value('50-75%')),
                default=Value('75-100%'),
                output_field=CharField()
            )
        ).values('completeness_range').annotate(count=Count('id'))


class UserSegmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Segment management
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'name']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return UserSegment.objects.all().prefetch_related('depends_on')
        return UserSegment.objects.filter(is_active=True).prefetch_related('depends_on')
    
    def get_serializer_class(self):
        from ..serializers_new.UserSegmentSerializer import UserSegmentSerializer, UserSegmentDetailSerializer
        if self.action == 'list':
            return UserSegmentSerializer
        return UserSegmentDetailSerializer
    
    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can create segments")
        segment = serializer.save()
        segment.update_user_count()
    
    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can update segments")
        segment = serializer.save()
        segment.update_user_count()
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get users in this segment"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            segment = self.get_object()
            users = segment.get_matching_users().select_related('user')
            
            from ..serializers_new.UserProfileSerializer import UserProfileSerializer
            serializer = UserProfileSerializer(users, many=True)
            return Response({
                'segment': {
                    'uuid': str(segment.uuid),
                    'name': segment.name,
                    'user_count': segment.user_count
                },
                'users': serializer.data
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get analytics for this segment"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            segment = self.get_object()
            service = UserSegmentService()
            
            days = int(request.query_params.get('days', 30))
            analytics = service.get_segment_analytics(str(segment.uuid), days)
            
            return Response(analytics)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def survey_recommendations(self, request, pk=None):
        """Get survey recommendations for this segment"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            segment = self.get_object()
            service = UserSegmentService()
            
            limit = min(int(request.query_params.get('limit', 10)), 50)
            recommendations = service.get_recommended_surveys_for_segment(str(segment.uuid), limit)
            
            from ..serializers_new.profile_surveys import SurveyTemplateSerializer
            survey_data = []
            for rec in recommendations:
                serializer = SurveyTemplateSerializer(rec['survey'])
                survey_data.append({
                    **serializer.data,
                    'match_score': rec['match_score'],
                    'segment_completion_rate': rec['segment_completion_rate'],
                    'segment_avg_quality': rec['segment_avg_quality'],
                    'estimated_reward': rec['estimated_reward']
                })
            
            return Response({
                'segment': {
                    'uuid': str(segment.uuid),
                    'name': segment.name,
                    'user_count': segment.user_count
                },
                'recommendations': survey_data
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['post'])
    def auto_create(self, request):
        """Auto-create segments based on user behavior"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            service = UserSegmentService()
            segments = service.auto_create_segments()
            
            from ..serializers_new.UserSegmentSerializer import UserSegmentSerializer
            serializer = UserSegmentSerializer(segments, many=True)
            
            return Response({
                'message': f'Created {len(segments)} segments',
                'segments': serializer.data
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['post'])
    def overlap_analysis(self, request):
        """Analyze overlap between multiple segments"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        segment_uuids = request.data.get('segments', [])
        if len(segment_uuids) < 2:
            return Response({'error': 'At least 2 segments required'}, status=400)
        
        try:
            service = UserSegmentService()
            analysis = service.get_segment_overlap_analysis(segment_uuids)
            
            return Response(analysis)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def update_user_count(self, request, pk=None):
        """Update user count for this segment"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            segment = self.get_object()
            segment.update_user_count()
            
            return Response({
                'message': 'User count updated',
                'user_count': segment.user_count
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall segment statistics (admin only)"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        stats = {
            'total_segments': UserSegment.objects.count(),
            'active_segments': UserSegment.objects.filter(is_active=True).count(),
            'total_segmented_users': UserSegment.objects.filter(is_active=True).aggregate(
                total=Count('userprofile', distinct=True)
            )['total'] or 0,
            'avg_users_per_segment': UserSegment.objects.filter(is_active=True).aggregate(
                avg=Avg('user_count')
            )['avg'] or 0,
            'segments_by_size': list(
                UserSegment.objects.filter(is_active=True)
                .values('name', 'user_count')
                .order_by('-user_count')[:10]
            )
        }
        
        return Response(stats)
