# api/cms/services_new/UserSegmentService.py
"""
User Segmentation Service for Survey Targeting
Provides intelligent user segmentation and targeting capabilities
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Set
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Min, Max, F
from django.contrib.auth import get_user_model
from django.db import transaction

from ..models_new.user_profile import UserProfile, UserSegment
from ..models_new.profile_surveys import SurveyCompletion, SurveyTemplate

logger = logging.getLogger(__name__)
User = get_user_model()


class UserSegmentService:
    """
    Service for managing user segmentation and targeting
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    def create_segment(self, segment_data: Dict[str, Any]) -> UserSegment:
        """Create a new user segment"""
        segment = UserSegment.objects.create(**segment_data)
        
        # Update user count
        segment.update_user_count()
        
        # Clear relevant caches
        self._clear_segment_caches()
        
        return segment
    
    def update_segment(self, segment_uuid: str, segment_data: Dict[str, Any]) -> UserSegment:
        """Update an existing user segment"""
        try:
            segment = UserSegment.objects.get(uuid=segment_uuid)
        except UserSegment.DoesNotExist:
            raise ValueError("Segment not found")
        
        for key, value in segment_data.items():
            if hasattr(segment, key):
                setattr(segment, key, value)
        
        segment.save()
        segment.update_user_count()
        
        # Clear relevant caches
        self._clear_segment_caches()
        
        return segment
    
    def get_segment_users(self, segment_uuid: str, limit: int = None) -> List[User]:
        """Get users in a specific segment"""
        cache_key = f"segment_users_{segment_uuid}_{limit or 'all'}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            segment = UserSegment.objects.get(uuid=segment_uuid)
        except UserSegment.DoesNotExist:
            return []
        
        users = segment.get_matching_users().select_related('user')
        user_list = [profile.user for profile in users]
        
        if limit:
            user_list = user_list[:limit]
        
        cache.set(cache_key, user_list, self.cache_timeout)
        return user_list
    
    def get_user_segments(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all segments a user belongs to"""
        cache_key = f"user_segments_{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            user_profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return []
        
        segments = UserSegment.objects.filter(is_active=True)
        user_segments = []
        
        for segment in segments:
            if segment.get_matching_users().filter(user=user_profile.user).exists():
                user_segments.append({
                    'uuid': str(segment.uuid),
                    'name': segment.name,
                    'description': segment.description,
                    'user_count': segment.user_count
                })
        
        cache.set(cache_key, user_segments, self.cache_timeout)
        return user_segments
    
    def get_segment_analytics(self, segment_uuid: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific user segment"""
        cache_key = f"segment_analytics_{segment_uuid}_{days}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            segment = UserSegment.objects.get(uuid=segment_uuid)
        except UserSegment.DoesNotExist:
            return {}
        
        start_date = timezone.now() - timedelta(days=days)
        users = segment.get_matching_users().values_list('user', flat=True)
        
        if not users:
            return {
                'segment_uuid': str(segment.uuid),
                'segment_name': segment.name,
                'user_count': 0,
                'period_days': days,
                'survey_activity': {},
                'earnings': {},
                'quality_metrics': {},
                'demographics': {}
            }
        
        # Survey activity
        survey_activity = self._get_segment_survey_activity(users, start_date)
        
        # Earnings analysis
        earnings_analysis = self._get_segment_earnings(users, start_date)
        
        # Quality metrics
        quality_metrics = self._get_segment_quality_metrics(users, start_date)
        
        # Demographics
        demographics = self._get_segment_demographics(users)
        
        analytics = {
            'segment_uuid': str(segment.uuid),
            'segment_name': segment.name,
            'user_count': len(users),
            'period_days': days,
            'survey_activity': survey_activity,
            'earnings': earnings_analysis,
            'quality_metrics': quality_metrics,
            'demographics': demographics,
            'generated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_recommended_surveys_for_segment(self, segment_uuid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recommended surveys for a user segment"""
        cache_key = f"segment_surveys_{segment_uuid}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            segment = UserSegment.objects.get(uuid=segment_uuid)
        except UserSegment.DoesNotExist:
            return []
        
        # Get active surveys
        active_surveys = SurveyTemplate.objects.filter(status='active').select_related('category')
        
        recommendations = []
        segment_users = segment.get_matching_users().values_list('user', flat=True)
        
        for survey in active_surveys:
            # Calculate segment match score
            match_score = self._calculate_segment_match_score(survey, segment)
            
            if match_score > 0:
                # Get segment-specific metrics
                segment_stats = self._get_survey_segment_stats(survey, segment_users)
                
                recommendations.append({
                    'survey': survey,
                    'match_score': match_score,
                    'segment_completion_rate': segment_stats['completion_rate'],
                    'segment_avg_quality': segment_stats['avg_quality'],
                    'estimated_reward': float(survey.base_reward + survey.bonus_reward),
                    'estimated_minutes': survey.estimated_minutes
                })
        
        # Sort by match score and segment performance
        recommendations.sort(key=lambda x: (x['match_score'], x['segment_completion_rate']), reverse=True)
        
        result = recommendations[:limit]
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def auto_create_segments(self) -> List[UserSegment]:
        """Automatically create segments based on user behavior patterns"""
        segments_created = []
        
        # High-value users segment
        high_value_segment = self._create_high_value_segment()
        if high_value_segment:
            segments_created.append(high_value_segment)
        
        # Active users segment
        active_segment = self._create_active_users_segment()
        if active_segment:
            segments_created.append(active_segment)
        
        # Quality responders segment
        quality_segment = self._create_quality_responders_segment()
        if quality_segment:
            segments_created.append(quality_segment)
        
        # Geographic segments
        geo_segments = self._create_geographic_segments()
        segments_created.extend(geo_segments)
        
        # Clear caches
        self._clear_segment_caches()
        
        return segments_created
    
    def get_segment_overlap_analysis(self, segment_uuids: List[str]) -> Dict[str, Any]:
        """Analyze overlap between multiple segments"""
        cache_key = f"segment_overlap_{'_'.join(sorted(segment_uuids))}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        if len(segment_uuids) < 2:
            return {'error': 'Need at least 2 segments for overlap analysis'}
        
        segments = UserSegment.objects.filter(uuid__in=segment_uuids, is_active=True)
        if segments.count() != len(segment_uuids):
            return {'error': 'One or more segments not found'}
        
        # Get users for each segment
        segment_users = {}
        for segment in segments:
            users = set(segment.get_matching_users().values_list('user', flat=True))
            segment_users[str(segment.uuid)] = users
        
        # Calculate overlaps
        overlap_analysis = {
            'segments': [
                {
                    'uuid': str(segment.uuid),
                    'name': segment.name,
                    'user_count': len(segment_users[str(segment.uuid)])
                }
                for segment in segments
            ],
            'pairwise_overlaps': {},
            'total_overlap': None,
            'unique_users': set()
        }
        
        # Calculate pairwise overlaps
        segment_list = list(segment_uuids)
        for i in range(len(segment_list)):
            for j in range(i + 1, len(segment_list)):
                seg1, seg2 = segment_list[i], segment_list[j]
                overlap = segment_users[seg1] & segment_users[seg2]
                overlap_analysis['pairwise_overlaps'][f"{seg1}_{seg2}"] = {
                    'count': len(overlap),
                    'percentage': round(len(overlap) / max(min(len(segment_users[seg1]), len(segment_users[seg2])), 1) * 100, 2)
                }
        
        # Calculate total overlap (users in all segments)
        if len(segment_uuids) > 2:
            total_overlap = set.intersection(*segment_users.values())
            overlap_analysis['total_overlap'] = {
                'count': len(total_overlap),
                'percentage': round(len(total_overlap) / min(len(users) for users in segment_users.values()) * 100, 2)
            }
        
        # Calculate unique users across all segments
        all_users = set.union(*segment_users.values())
        overlap_analysis['unique_users'] = len(all_users)
        
        cache.set(cache_key, overlap_analysis, self.cache_timeout)
        return overlap_analysis
    
    def _get_segment_survey_activity(self, users: List[int], start_date: datetime) -> Dict[str, Any]:
        """Get survey activity for segment users"""
        completions = SurveyCompletion.objects.filter(
            user_id__in=users,
            started_at__gte=start_date
        )
        
        total_started = completions.count()
        total_completed = completions.filter(status='completed').count()
        total_approved = completions.filter(status='approved').count()
        
        return {
            'total_started': total_started,
            'total_completed': total_completed,
            'total_approved': total_approved,
            'completion_rate': round((total_completed / total_started * 100) if total_started > 0 else 0, 2),
            'approval_rate': round((total_approved / total_completed * 100) if total_completed > 0 else 0, 2)
        }
    
    def _get_segment_earnings(self, users: List[int], start_date: datetime) -> Dict[str, Any]:
        """Get earnings analysis for segment users"""
        earnings = SurveyCompletion.objects.filter(
            user_id__in=users,
            started_at__gte=start_date,
            status='approved'
        ).aggregate(
            total=Sum('total_reward_earned'),
            avg=Avg('total_reward_earned'),
            min=Min('total_reward_earned'),
            max=Max('total_reward_earned')
        )
        
        return {
            'total_earnings': float(earnings['total'] or 0),
            'avg_earnings_per_user': round(float(earnings['avg'] or 0), 2),
            'min_earnings': float(earnings['min'] or 0),
            'max_earnings': float(earnings['max'] or 0)
        }
    
    def _get_segment_quality_metrics(self, users: List[int], start_date: datetime) -> Dict[str, Any]:
        """Get quality metrics for segment users"""
        quality_stats = SurveyCompletion.objects.filter(
            user_id__in=users,
            started_at__gte=start_date,
            status='approved'
        ).aggregate(
            avg_quality=Avg('quality_score'),
            min_quality=Min('quality_score'),
            max_quality=Max('quality_score')
        )
        
        return {
            'avg_quality_score': round(float(quality_stats['avg_quality'] or 0), 2),
            'min_quality_score': float(quality_stats['min_quality'] or 0),
            'max_quality_score': float(quality_stats['max_quality'] or 0)
        }
    
    def _get_segment_demographics(self, users: List[int]) -> Dict[str, Any]:
        """Get demographic breakdown for segment users"""
        profiles = UserProfile.objects.filter(user_id__in=users)
        
        demographics = {
            'age_groups': {},
            'genders': {},
            'countries': {},
            'education_levels': {},
            'income_levels': {}
        }
        
        for profile in profiles:
            # Age groups
            if profile.age:
                age_group = self._get_age_group(profile.age)
                demographics['age_groups'][age_group] = demographics['age_groups'].get(age_group, 0) + 1
            
            # Gender
            if profile.gender:
                demographics['genders'][profile.gender] = demographics['genders'].get(profile.gender, 0) + 1
            
            # Country
            if profile.country:
                demographics['countries'][profile.country] = demographics['countries'].get(profile.country, 0) + 1
            
            # Education
            if profile.education:
                demographics['education_levels'][profile.education] = demographics['education_levels'].get(profile.education, 0) + 1
            
            # Income
            if profile.income_level:
                demographics['income_levels'][profile.income_level] = demographics['income_levels'].get(profile.income_level, 0) + 1
        
        return demographics
    
    def _calculate_segment_match_score(self, survey: SurveyTemplate, segment: UserSegment) -> float:
        """Calculate how well a survey matches a segment.

        Uses getattr(segment, field, []) for optional fields that exist in the
        service's targeting logic but may not be columns on the UserSegment model
        (genders, education_levels, income_levels are stored in criteria JSON).
        """
        score = 0.0
        max_score = 0.0

        # Pull optional targeting fields — fall back to criteria JSON dict
        criteria       = getattr(segment, 'criteria', {}) or {}
        seg_genders    = getattr(segment, 'genders',          criteria.get('genders', []))    or []
        seg_edu        = getattr(segment, 'education_levels',  criteria.get('education_levels', [])) or []
        seg_income     = getattr(segment, 'income_levels',     criteria.get('income_levels', [])) or []
        seg_countries  = getattr(segment, 'countries',         []) or []
        seg_interests  = getattr(segment, 'interests',         []) or []
        seg_min_age    = getattr(segment, 'min_age', None)
        seg_max_age    = getattr(segment, 'max_age', None)

        # Survey targeting fields — also use getattr for safety
        sv_min_age     = getattr(survey, 'min_age', None)
        sv_max_age     = getattr(survey, 'max_age', None)
        sv_genders     = getattr(survey, 'target_genders',       []) or []
        sv_countries   = getattr(survey, 'target_countries',     []) or []
        sv_edu         = getattr(survey, 'target_education',     []) or []
        sv_interests   = getattr(survey, 'target_interests',     []) or []
        sv_income      = getattr(survey, 'target_income_levels', []) or []

        # Age matching (20 points)
        if seg_min_age or seg_max_age:
            max_score += 20
            age_ok = (
                (not seg_min_age or (sv_min_age is not None and sv_min_age >= seg_min_age)) and
                (not seg_max_age or (sv_max_age is not None and sv_max_age <= seg_max_age))
            )
            if age_ok:
                score += 20

        # Gender matching (15 points)
        if seg_genders:
            max_score += 15
            if any(g in sv_genders for g in seg_genders):
                score += 15

        # Country matching (20 points)
        if seg_countries:
            max_score += 20
            if any(c in sv_countries for c in seg_countries):
                score += 20

        # Education matching (15 points)
        if seg_edu:
            max_score += 15
            if any(e in sv_edu for e in seg_edu):
                score += 15

        # Interest matching (20 points)
        if seg_interests:
            max_score += 20
            matching = len(set(seg_interests) & set(sv_interests))
            score += (matching / len(seg_interests)) * 20

        # Income matching (10 points)
        if seg_income:
            max_score += 10
            if any(i in sv_income for i in seg_income):
                score += 10

        # When neither segment nor survey has any targeting criteria → neutral 50% match
        return min((score / max_score * 100), 100.0) if max_score > 0 else 50.0
    
    def _get_survey_segment_stats(self, survey: SurveyTemplate, segment_users: List[int]) -> Dict[str, Any]:
        """Get survey statistics for a specific segment"""
        segment_completions = SurveyCompletion.objects.filter(
            survey=survey,
            user_id__in=segment_users
        )
        
        total_started = segment_completions.count()
        total_approved = segment_completions.filter(status='approved').count()
        
        avg_quality = segment_completions.filter(status='approved').aggregate(
            avg=Avg('quality_score')
        )['avg'] or 0
        
        return {
            'completion_rate': round((total_approved / total_started * 100) if total_started > 0 else 0, 2),
            'avg_quality': round(float(avg_quality), 2)
        }
    
    def _get_age_group(self, age: int) -> str:
        """Get age group category"""
        if age < 18:
            return 'Under 18'
        elif age < 25:
            return '18-24'
        elif age < 35:
            return '25-34'
        elif age < 45:
            return '35-44'
        elif age < 55:
            return '45-54'
        else:
            return '55+'
    
    def _create_high_value_segment(self) -> Optional[UserSegment]:
        """Create segment for high-value users (high earnings + good quality)."""
        # quality_score lives on SurveyCompletion, not UserProfile
        from django.db.models import Q as _Q
        # High value: users with quality completions OR high participation_score in profile
        high_value_user_ids = SurveyCompletion.objects.filter(
            status='approved',
            quality_score__gte=0.8,
        ).values_list('user_id', flat=True).distinct()

        # Also include users with high participation score directly on profile
        from api.cms.models_new.withdrawal import UserProfile as _UP
        high_profile_ids = _UP.objects.filter(
            survey_participation_score__gte=80
        ).values_list('user_id', flat=True)

        combined_ids = set(list(high_value_user_ids) + list(high_profile_ids))

        if combined_ids:
            high_value_user_ids = type('_QS', (), {'exists': lambda self: bool(combined_ids)})()
            segment, created = UserSegment.objects.get_or_create(
                name="High Value Users",
                defaults={
                    'description': "Users with high participation and quality scores",
                    'criteria': {'min_quality_score': '0.80'},
                }
            )
            if created:
                segment.update_user_count()
                return segment
        return None

    def _create_active_users_segment(self) -> Optional[UserSegment]:
        """Create segment for recently active users."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_user_ids = SurveyCompletion.objects.filter(
            started_at__gte=thirty_days_ago,
        ).values_list('user_id', flat=True).distinct()

        if active_user_ids.exists():
            segment, created = UserSegment.objects.get_or_create(
                name="Active Users",
                defaults={'description': "Users active in the last 30 days"},
            )
            if created:
                segment.update_user_count()
                return segment
        return None

    def _create_quality_responders_segment(self) -> Optional[UserSegment]:
        """Create segment for consistently high-quality responders."""
        quality_user_ids = SurveyCompletion.objects.filter(
            status='approved',
            quality_score__gte=0.9,
        ).values_list('user_id', flat=True).distinct()

        if quality_user_ids.exists():
            segment, created = UserSegment.objects.get_or_create(
                name="Quality Responders",
                defaults={
                    'description': "Users with consistently high quality scores",
                    'criteria': {'min_quality_score': '0.90'},
                }
            )
            if created:
                segment.update_user_count()
                return segment
        
        return None
    
    def _create_geographic_segments(self) -> List[UserSegment]:
        """Create geographic segments"""
        segments = []
        
        # Get top countries by user count
        top_countries = UserProfile.objects.values('country').annotate(
            count=Count('id')
        ).filter(
            country__isnull=False
        ).order_by('-count')[:5]
        
        for country_data in top_countries:
            country = country_data['country']
            segment, created = UserSegment.objects.get_or_create(
                name=f"Users in {country}",
                defaults={
                    'description': f"Users located in {country}",
                    'countries': [country]
                }
            )
            
            if created:
                segment.update_user_count()
                segments.append(segment)
        
        return segments
    
    def _clear_segment_caches(self):
        """Clear all segment-related caches"""
        # This is a simplified cache clearing
        # In production, you might want to use cache keys pattern matching
        pass
