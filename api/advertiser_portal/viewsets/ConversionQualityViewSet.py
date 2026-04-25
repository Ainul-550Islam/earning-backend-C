"""
Conversion Quality ViewSet

ViewSet for fraud protection statistics and analytics,
including conversion quality scoring and fraud detection.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db.models import Case, When

from ..models.fraud_protection import ConversionQualityScore
try:
    from ..services import ConversionQualityService
except ImportError:
    ConversionQualityService = None
try:
    from ..services import AdvertiserFraudService
except ImportError:
    AdvertiserFraudService = None
from ..serializers import ConversionQualityScoreSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class ConversionQualityViewSet(viewsets.ModelViewSet):
    """
    ViewSet for fraud protection statistics and analytics.
    
    Handles conversion quality scoring, fraud detection,
    and protection metrics.
    """
    
    queryset = ConversionQualityScore.objects.all()
    serializer_class = ConversionQualityScoreSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all quality scores
            return ConversionQualityScore.objects.all()
        else:
            # Advertisers can only see their own quality scores
            return ConversionQualityScore.objects.filter(advertiser__user=user)
    
    @action(detail=False, methods=['get'])
    def quality_overview(self, request):
        """
        Get conversion quality overview.
        
        Returns comprehensive quality metrics and fraud statistics.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get conversion quality scores for the period
            quality_scores = ConversionQualityScore.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('conversion')
            
            # Aggregate quality data
            quality_data = quality_scores.aggregate(
                total_conversions=Count('conversion', distinct=True),
                total_score=Avg('overall_score'),
                behavioral_score=Avg('behavioral_score'),
                timing_score=Avg('timing_score'),
                engagement_score=Avg('engagement_score'),
                technical_score=Avg('technical_score'),
                fraud_score=Avg('fraud_score'),
                high_quality_conversions=Count(
                    Case(When(overall_score__gte=80, then=1))
                ),
                medium_quality_conversions=Count(
                    Case(When(overall_score__gte=60, overall_score__lt=80, then=1))
                ),
                low_quality_conversions=Count(
                    Case(When(overall_score__lt=60, then=1))
                ),
                flagged_conversions=Count(
                    Case(When(is_flagged=True, then=1))
                ),
            )
            
            # Fill missing values
            for key, value in quality_data.items():
                if value is None:
                    quality_data[key] = 0
            
            # Calculate derived metrics
            total_conversions = quality_data['total_conversions']
            high_quality_count = quality_data['high_quality_conversions']
            medium_quality_count = quality_data['medium_quality_conversions']
            low_quality_count = quality_data['low_quality_conversions']
            flagged_count = quality_data['flagged_conversions']
            
            high_quality_percentage = (high_quality_count / total_conversions * 100) if total_conversions > 0 else 0
            medium_quality_percentage = (medium_quality_count / total_conversions * 100) if total_conversions > 0 else 0
            low_quality_percentage = (low_quality_count / total_conversions * 100) if total_conversions > 0 else 0
            flagged_percentage = (flagged_count / total_conversions * 100) if total_conversions > 0 else 0
            
            # Get daily breakdown
            daily_breakdown = {}
            current_date = start_date.date()
            while current_date <= end_date:
                day_scores = quality_scores.filter(date=current_date)
                day_data = day_scores.aggregate(
                    conversions=Count('conversion', distinct=True),
                    avg_score=Avg('overall_score'),
                    flagged_count=Count(Case(When(is_flagged=True, then=1)))
                )
                
                daily_breakdown[current_date.isoformat()] = {
                    'conversions': day_data['conversions'] or 0,
                    'avg_score': float(day_data['avg_score'] or 0),
                    'flagged_count': day_data['flagged_count'] or 0,
                }
                
                current_date += timezone.timedelta(days=1)
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_conversions': total_conversions,
                    'average_quality_score': float(quality_data['total_score'] or 0),
                    'behavioral_score': float(quality_data['behavioral_score'] or 0),
                    'timing_score': float(quality_data['timing_score'] or 0),
                    'engagement_score': float(quality_data['engagement_score'] or 0),
                    'technical_score': float(quality_data['technical_score'] or 0),
                    'fraud_score': float(quality_data['fraud_score'] or 0),
                    'high_quality_conversions': high_quality_count,
                    'medium_quality_conversions': medium_quality_count,
                    'low_quality_conversions': low_quality_count,
                    'flagged_conversions': flagged_count,
                    'high_quality_percentage': float(high_quality_percentage),
                    'medium_quality_percentage': float(medium_quality_percentage),
                    'low_quality_percentage': float(low_quality_percentage),
                    'flagged_percentage': float(flagged_percentage),
                },
                'daily_breakdown': daily_breakdown,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting quality overview: {e}")
            return Response(
                {'detail': 'Failed to get quality overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def fraud_statistics(self, request):
        """
        Get fraud detection statistics.
        
        Returns fraud detection metrics and analysis.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get fraud service
            fraud_service = AdvertiserFraudService()
            
            # Get fraud statistics
            fraud_stats = fraud_service.get_fraud_statistics(request.user.advertiser, start_date, end_date)
            
            return Response(fraud_stats)
            
        except Exception as e:
            logger.error(f"Error getting fraud statistics: {e}")
            return Response(
                {'detail': 'Failed to get fraud statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def quality_trends(self, request):
        """
        Get conversion quality trends.
        
        Returns trend analysis for quality metrics.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get daily quality scores
            daily_scores = ConversionQualityScore.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).values('date').annotate(
                avg_score=Avg('overall_score'),
                avg_behavioral=Avg('behavioral_score'),
                avg_timing=Avg('timing_score'),
                avg_engagement=Avg('engagement_score'),
                avg_technical=Avg('technical_score'),
                avg_fraud=Avg('fraud_score'),
                flagged_count=Count(Case(When(is_flagged=True, then=1))),
                total_conversions=Count('conversion', distinct=True)
            ).order_by('date')
            
            # Calculate trends
            if len(daily_scores) >= 2:
                mid_point = len(daily_scores) // 2
                recent_avg = daily_scores[mid_point:].aggregate(
                    avg_score=Avg('avg_score'),
                    avg_fraud=Avg('avg_fraud'),
                    flagged_rate=Avg('flagged_count') / Avg('total_conversions') * 100
                )
                
                older_avg = daily_scores[:mid_point].aggregate(
                    avg_score=Avg('avg_score'),
                    avg_fraud=Avg('avg_fraud'),
                    flagged_rate=Avg('flagged_count') / Avg('total_conversions') * 100
                )
                
                quality_trend = 'up' if recent_avg['avg_score'] > older_avg['avg_score'] else 'down'
                fraud_trend = 'up' if recent_avg['avg_fraud'] > older_avg['avg_fraud'] else 'down'
                flagged_trend = 'up' if recent_avg['flagged_rate'] > older_avg['flagged_rate'] else 'down'
            else:
                quality_trend = 'stable'
                fraud_trend = 'stable'
                flagged_trend = 'stable'
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'trends': {
                    'quality_trend': quality_trend,
                    'fraud_trend': fraud_trend,
                    'flagged_trend': flagged_trend,
                },
                'daily_data': [
                    {
                        'date': item['date'].isoformat(),
                        'avg_score': float(item['avg_score'] or 0),
                        'avg_behavioral': float(item['avg_behavioral'] or 0),
                        'avg_timing': float(item['avg_timing'] or 0),
                        'avg_engagement': float(item['avg_engagement'] or 0),
                        'avg_technical': float(item['avg_technical'] or 0),
                        'avg_fraud': float(item['avg_fraud'] or 0),
                        'flagged_count': item['flagged_count'] or 0,
                        'total_conversions': item['total_conversions'] or 0,
                    }
                    for item in daily_scores
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting quality trends: {e}")
            return Response(
                {'detail': 'Failed to get quality trends'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def flagged_conversions(self, request):
        """
        Get flagged conversions.
        
        Returns list of conversions flagged for fraud.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get flagged conversions
            flagged_scores = ConversionQualityScore.objects.filter(
                advertiser=request.user.advertiser,
                is_flagged=True,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('conversion')
            
            flagged_conversions = []
            for score in flagged_scores:
                flagged_conversions.append({
                    'conversion_id': score.conversion.id,
                    'date': score.date.isoformat(),
                    'overall_score': float(score.overall_score),
                    'fraud_score': float(score.fraud_score),
                    'behavioral_score': float(score.behavioral_score),
                    'timing_score': float(score.timing_score),
                    'engagement_score': float(score.engagement_score),
                    'technical_score': float(score.technical_score),
                    'flag_reason': score.flag_reason,
                    'risk_factors': score.risk_factors,
                    'created_at': score.created_at.isoformat(),
                })
            
            return Response({
                'flagged_conversions': flagged_conversions,
                'count': len(flagged_conversions),
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting flagged conversions: {e}")
            return Response(
                {'detail': 'Failed to get flagged conversions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def quality_distribution(self, request):
        """
        Get conversion quality distribution.
        
        Returns distribution of quality scores.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get quality scores for the period
            quality_scores = ConversionQualityScore.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('conversion')
            
            # Create distribution buckets
            distribution = {
                'excellent': {'count': 0, 'percentage': 0, 'range': '90-100'},
                'good': {'count': 0, 'percentage': 0, 'range': '80-89'},
                'average': {'count': 0, 'percentage': 0, 'range': '70-79'},
                'below_average': {'count': 0, 'percentage': 0, 'range': '60-69'},
                'poor': {'count': 0, 'percentage': 0, 'range': '50-59'},
                'very_poor': {'count': 0, 'percentage': 0, 'range': '0-49'},
            }
            
            total_conversions = quality_scores.count()
            
            for score in quality_scores:
                overall_score = score.overall_score
                
                if overall_score >= 90:
                    distribution['excellent']['count'] += 1
                elif overall_score >= 80:
                    distribution['good']['count'] += 1
                elif overall_score >= 70:
                    distribution['average']['count'] += 1
                elif overall_score >= 60:
                    distribution['below_average']['count'] += 1
                elif overall_score >= 50:
                    distribution['poor']['count'] += 1
                else:
                    distribution['very_poor']['count'] += 1
            
            # Calculate percentages
            for bucket in distribution:
                count = distribution[bucket]['count']
                distribution[bucket]['percentage'] = (count / total_conversions * 100) if total_conversions > 0 else 0
            
            return Response({
                'distribution': distribution,
                'total_conversions': total_conversions,
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting quality distribution: {e}")
            return Response(
                {'detail': 'Failed to get quality distribution'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def risk_factors(self, request):
        """
        Get common risk factors.
        
        Returns analysis of common fraud indicators.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get quality scores with risk factors
            quality_scores = ConversionQualityScore.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).exclude(risk_factors={})
            
            # Analyze risk factors
            risk_factor_counts = {}
            total_conversions = quality_scores.count()
            
            for score in quality_scores:
                if score.risk_factors:
                    for factor in score.risk_factors:
                        if factor not in risk_factor_counts:
                            risk_factor_counts[factor] = 0
                        risk_factor_counts[factor] += 1
            
            # Calculate percentages
            risk_factor_analysis = []
            for factor, count in risk_factor_counts.items():
                percentage = (count / total_conversions * 100) if total_conversions > 0 else 0
                risk_factor_analysis.append({
                    'factor': factor,
                    'count': count,
                    'percentage': float(percentage),
                })
            
            # Sort by count
            risk_factor_analysis.sort(key=lambda x: x['count'], reverse=True)
            
            return Response({
                'risk_factors': risk_factor_analysis,
                'total_conversions': total_conversions,
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting risk factors: {e}")
            return Response(
                {'detail': 'Failed to get risk factors'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def analyze_conversion(self, request):
        """
        Analyze conversion quality.
        
        Performs quality analysis on a specific conversion.
        """
        try:
            conversion_id = request.data.get('conversion_id')
            
            if not conversion_id:
                return Response(
                    {'detail': 'Conversion ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            quality_service = ConversionQualityService()
            analysis_result = quality_service.analyze_conversion_quality(
                request.user.advertiser,
                conversion_id
            )
            
            return Response(analysis_result)
            
        except Exception as e:
            logger.error(f"Error analyzing conversion: {e}")
            return Response(
                {'detail': 'Failed to analyze conversion'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def flag_conversion(self, request):
        """
        Flag conversion for review.
        
        Manually flags a conversion for fraud review.
        """
        try:
            conversion_id = request.data.get('conversion_id')
            reason = request.data.get('reason', 'Manual flag')
            
            if not conversion_id:
                return Response(
                    {'detail': 'Conversion ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            quality_service = ConversionQualityService()
            flag_result = quality_service.flag_conversion(
                request.user.advertiser,
                conversion_id,
                reason
            )
            
            return Response(flag_result)
            
        except Exception as e:
            logger.error(f"Error flagging conversion: {e}")
            return Response(
                {'detail': 'Failed to flag conversion'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def unflag_conversion(self, request):
        """
        Unflag conversion.
        
        Removes flag from a conversion.
        """
        try:
            conversion_id = request.data.get('conversion_id')
            
            if not conversion_id:
                return Response(
                    {'detail': 'Conversion ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            quality_service = ConversionQualityService()
            unflag_result = quality_service.unflag_conversion(
                request.user.advertiser,
                conversion_id
            )
            
            return Response(unflag_result)
            
        except Exception as e:
            logger.error(f"Error unflagging conversion: {e}")
            return Response(
                {'detail': 'Failed to unflag conversion'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def quality_settings(self, request):
        """
        Get quality scoring settings.
        
        Returns configuration for quality scoring.
        """
        try:
            quality_service = ConversionQualityService()
            settings = quality_service.get_quality_settings(request.user.advertiser)
            
            return Response(settings)
            
        except Exception as e:
            logger.error(f"Error getting quality settings: {e}")
            return Response(
                {'detail': 'Failed to get quality settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def update_quality_settings(self, request):
        """
        Update quality scoring settings.
        
        Updates configuration for quality scoring.
        """
        try:
            settings = request.data.get('settings', {})
            
            quality_service = ConversionQualityService()
            update_result = quality_service.update_quality_settings(
                request.user.advertiser,
                settings
            )
            
            return Response(update_result)
            
        except Exception as e:
            logger.error(f"Error updating quality settings: {e}")
            return Response(
                {'detail': 'Failed to update quality settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export_quality_report(self, request):
        """
        Export quality report.
        
        Generates and exports conversion quality report.
        """
        try:
            try:
                from ..services import ReportExportService
            except ImportError:
                ReportExportService = None
            
            export_service = ReportExportService()
            
            format_type = request.data.get('format', 'csv')
            days = int(request.data.get('days', 30))
            filters = request.data.get('filters', {})
            
            # Generate report data
            report_data = self._generate_quality_export_data(days, filters)
            
            # Export based on format
            if format_type == 'csv':
                response = export_service.export_report_to_csv(request.user.advertiser, report_data)
            elif format_type == 'pdf':
                response = export_service.export_report_to_pdf(request.user.advertiser, report_data)
            elif format_type == 'excel':
                response = export_service.export_report_to_excel(request.user.advertiser, report_data)
            else:
                return Response(
                    {'detail': 'Invalid format type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting quality report: {e}")
            return Response(
                {'detail': 'Failed to export quality report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_quality_export_data(self, days, filters):
        """Generate quality report data for export."""
        start_date = timezone.now() - timezone.timedelta(days=days-1)
        end_date = timezone.now().date()
        
        # Get quality scores
        quality_scores = ConversionQualityScore.objects.filter(
            advertiser=self.request.user.advertiser,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('conversion')
        
        # Apply filters
        if 'flagged_only' in filters and filters['flagged_only']:
            quality_scores = quality_scores.filter(is_flagged=True)
        
        if 'min_score' in filters:
            quality_scores = quality_scores.filter(overall_score__gte=filters['min_score'])
        
        if 'max_score' in filters:
            quality_scores = quality_scores.filter(overall_score__lte=filters['max_score'])
        
        # Aggregate data
        report_data = {
            'report_type': 'conversion_quality',
            'period': {
                'start_date': start_date.date().isoformat(),
                'end_date': end_date.isoformat(),
                'days': days,
            },
            'data': []
        }
        
        # Add conversion quality data
        for score in quality_scores:
            report_data['data'].append({
                'conversion_id': score.conversion.id,
                'date': score.date.isoformat(),
                'overall_score': float(score.overall_score),
                'behavioral_score': float(score.behavioral_score),
                'timing_score': float(score.timing_score),
                'engagement_score': float(score.engagement_score),
                'technical_score': float(score.technical_score),
                'fraud_score': float(score.fraud_score),
                'is_flagged': score.is_flagged,
                'flag_reason': score.flag_reason,
                'risk_factors': score.risk_factors,
                'created_at': score.created_at.isoformat(),
            })
        
        return report_data
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        is_flagged = request.query_params.get('is_flagged')
        min_score = request.query_params.get('min_score')
        max_score = request.query_params.get('max_score')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        if is_flagged is not None:
            queryset = queryset.filter(is_flagged=is_flagged.lower() == 'true')
        
        if min_score:
            queryset = queryset.filter(overall_score__gte=float(min_score))
        
        if max_score:
            queryset = queryset.filter(overall_score__lte=float(max_score))
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
