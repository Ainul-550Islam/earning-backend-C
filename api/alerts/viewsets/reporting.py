"""
Reporting ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
import logging

from ..models.reporting import (
    AlertReport, MTTRMetric, MTTDMetric, SLABreach
)

logger = logging.getLogger(__name__)


class AlertReportViewSet(viewsets.ModelViewSet):
    """AlertReport ViewSet for CRUD operations"""
    queryset = AlertReport.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        report_type = self.request.query_params.get('report_type')
        status = self.request.query_params.get('status')
        
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.reporting import AlertReportSerializer
        return AlertReportSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['generate', 'export', 'schedule_next_run']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Generate report"""
        try:
            report = self.get_object()
            report.generate_report()
            
            return Response({
                'success': True,
                'status': report.status,
                'generated_at': report.generated_at,
                'generation_duration_ms': report.generation_duration_ms
            })
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export report"""
        try:
            report = self.get_object()
            export_data = report.export_to_file()
            
            return Response({
                'format_type': report.format_type,
                'content': export_data,
                'file_size': len(export_data)
            })
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def schedule_next_run(self, request, pk=None):
        """Schedule next run for recurring reports"""
        try:
            report = self.get_object()
            report.schedule_next_run()
            
            return Response({
                'success': True,
                'next_run': report.next_run
            })
        except Exception as e:
            logger.error(f"Error scheduling next run: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_daily_report(self, request):
        """Create daily report"""
        try:
            from datetime import date
            today = date.today()
            
            report_data = {
                'title': f'Daily Report - {today}',
                'report_type': 'daily',
                'start_date': timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
                'end_date': timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999),
                'included_metrics': ['basic_metrics', 'severity_breakdown', 'rule_performance'],
                'format_type': request.data.get('format_type', 'json'),
                'auto_distribute': request.data.get('auto_distribute', False)
            }
            
            report = AlertReport.objects.create(**report_data, created_by=request.user)
            report.generate_report()
            
            return Response({
                'success': True,
                'report_id': report.id,
                'status': report.status
            })
        except Exception as e:
            logger.error(f"Error creating daily report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_weekly_report(self, request):
        """Create weekly report"""
        try:
            from datetime import date, timedelta
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            report_data = {
                'title': f'Weekly Report - {week_start} to {week_end}',
                'report_type': 'weekly',
                'start_date': timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=today.weekday()),
                'end_date': timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999) - timedelta(days=(today.weekday() - 6)),
                'included_metrics': ['basic_metrics', 'severity_breakdown', 'rule_performance', 'trend_analysis'],
                'format_type': request.data.get('format_type', 'json'),
                'auto_distribute': request.data.get('auto_distribute', False)
            }
            
            report = AlertReport.objects.create(**report_data, created_by=request.user)
            report.generate_report()
            
            return Response({
                'success': True,
                'report_id': report.id,
                'status': report.status
            })
        except Exception as e:
            logger.error(f"Error creating weekly report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_sla_report(self, request):
        """Create SLA report"""
        try:
            days = int(request.data.get('days', 30))
            
            report_data = {
                'title': f'SLA Report - Last {days} Days',
                'report_type': 'sla',
                'start_date': timezone.now() - timedelta(days=days),
                'end_date': timezone.now(),
                'included_metrics': ['sla_metrics', 'resolution_times', 'compliance_rates'],
                'format_type': request.data.get('format_type', 'json'),
                'auto_distribute': request.data.get('auto_distribute', False)
            }
            
            report = AlertReport.objects.create(**report_data, created_by=request.user)
            report.generate_report()
            
            return Response({
                'success': True,
                'report_id': report.id,
                'status': report.status
            })
        except Exception as e:
            logger.error(f"Error creating SLA report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MTTRMetricViewSet(viewsets.ModelViewSet):
    """MTTRMetric ViewSet for CRUD operations"""
    queryset = MTTRMetric.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        calculation_period_days = self.request.query_params.get('calculation_period_days')
        
        if calculation_period_days:
            queryset = queryset.filter(calculation_period_days=calculation_period_days)
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.reporting import MTTRMetricSerializer
        return MTTRMetricSerializer
    
    def get_permissions(self):
        if self.action in ['calculate_mttr', 'get_trends']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def calculate_mttr(self, request, pk=None):
        """Calculate MTTR metrics"""
        try:
            mttr_metric = self.get_object()
            mttr_metric.calculate_mttr()
            
            return Response({
                'success': True,
                'current_mttr_minutes': mttr_metric.current_mttr_minutes,
                'target_mttr_minutes': mttr_metric.target_mttr_minutes,
                'target_compliance_percentage': mttr_metric.target_compliance_percentage,
                'calculated_at': mttr_metric.last_calculated
            })
        except Exception as e:
            logger.error(f"Error calculating MTTR: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_trends(self, request, pk=None):
        """Get MTTR trends"""
        try:
            mttr_metric = self.get_object()
            
            return Response({
                'current_mttr_minutes': mttr_metric.current_mttr_minutes,
                'target_mttr_minutes': mttr_metric.target_mttr_minutes,
                'mttr_trend_7_days': mttr_metric.mttr_trend_7_days,
                'mttr_trend_30_days': mttr_metric.mttr_trend_30_days,
                'mttr_by_severity': mttr_metric.mttr_by_severity,
                'mttr_by_rule': mttr_metric.mttr_by_rule
            })
        except Exception as e:
            logger.error(f"Error getting MTTR trends: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get MTTR overview for all metrics"""
        try:
            metrics = MTTRMetric.objects.all()
            
            overview = {
                'total_metrics': metrics.count(),
                'average_mttr': 0,
                'average_compliance': 0,
                'metrics_summary': []
            }
            
            if metrics.exists():
                total_mttr = sum(m.current_mttr_minutes for m in metrics)
                total_compliance = sum(m.target_compliance_percentage for m in metrics)
                
                overview['average_mttr'] = total_mttr / metrics.count()
                overview['average_compliance'] = total_compliance / metrics.count()
                
                for metric in metrics:
                    overview['metrics_summary'].append({
                        'id': metric.id,
                        'name': metric.name,
                        'current_mttr': metric.current_mttr_minutes,
                        'target_mttr': metric.target_mttr_minutes,
                        'compliance': metric.target_compliance_percentage,
                        'trend_7_days': metric.mttr_trend_7_days
                    })
            
            return Response(overview)
        except Exception as e:
            logger.error(f"Error getting MTTR overview: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MTTDMetricViewSet(viewsets.ModelViewSet):
    """MTTDMetric ViewSet for CRUD operations"""
    queryset = MTTDMetric.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        calculation_period_days = self.request.query_params.get('calculation_period_days')
        
        if calculation_period_days:
            queryset = queryset.filter(calculation_period_days=calculation_period_days)
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.reporting import MTTDMetricSerializer
        return MTTDMetricSerializer
    
    def get_permissions(self):
        if self.action in ['calculate_mttd', 'get_trends']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def calculate_mttd(self, request, pk=None):
        """Calculate MTTD metrics"""
        try:
            mttd_metric = self.get_object()
            mttd_metric.calculate_mttd()
            
            return Response({
                'success': True,
                'current_mttd_minutes': mttd_metric.current_mttd_minutes,
                'target_mttd_minutes': mttd_metric.target_mttd_minutes,
                'target_compliance_percentage': mttd_metric.target_compliance_percentage,
                'detection_rate': mttd_metric.detection_rate,
                'false_positive_rate': mttd_metric.false_positive_rate,
                'calculated_at': mttd_metric.last_calculated
            })
        except Exception as e:
            logger.error(f"Error calculating MTTD: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_trends(self, request, pk=None):
        """Get MTTD trends"""
        try:
            mttd_metric = self.get_object()
            
            return Response({
                'current_mttd_minutes': mttd_metric.current_mttd_minutes,
                'target_mttd_minutes': mttd_metric.target_mttd_minutes,
                'mttd_trend_7_days': mttd_metric.mttd_trend_7_days,
                'mttd_trend_30_days': mttd_metric.mttd_trend_30_days,
                'mttd_by_severity': mttd_metric.mttd_by_severity,
                'mttd_by_rule': mttd_metric.mttd_by_rule,
                'detection_rate': mttd_metric.detection_rate,
                'false_positive_rate': mttd_metric.false_positive_rate
            })
        except Exception as e:
            logger.error(f"Error getting MTTD trends: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get MTTD overview for all metrics"""
        try:
            metrics = MTTDMetric.objects.all()
            
            overview = {
                'total_metrics': metrics.count(),
                'average_mttd': 0,
                'average_detection_rate': 0,
                'average_false_positive_rate': 0,
                'metrics_summary': []
            }
            
            if metrics.exists():
                total_mttd = sum(m.current_mttd_minutes for m in metrics)
                total_detection_rate = sum(m.detection_rate for m in metrics)
                total_false_positive_rate = sum(m.false_positive_rate for m in metrics)
                
                overview['average_mttd'] = total_mttd / metrics.count()
                overview['average_detection_rate'] = total_detection_rate / metrics.count()
                overview['average_false_positive_rate'] = total_false_positive_rate / metrics.count()
                
                for metric in metrics:
                    overview['metrics_summary'].append({
                        'id': metric.id,
                        'name': metric.name,
                        'current_mttd': metric.current_mttd_minutes,
                        'target_mttd': metric.target_mttd_minutes,
                        'detection_rate': metric.detection_rate,
                        'false_positive_rate': metric.false_positive_rate,
                        'trend_7_days': metric.mttd_trend_7_days
                    })
            
            return Response(overview)
        except Exception as e:
            logger.error(f"Error getting MTTD overview: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SLABreachViewSet(viewsets.ModelViewSet):
    """SLABreach ViewSet for CRUD operations"""
    queryset = SLABreach.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('alert_log', 'resolved_by')
        
        # Apply filters
        sla_type = self.request.query_params.get('sla_type')
        severity = self.request.query_params.get('severity')
        status = self.request.query_params.get('status')
        
        if sla_type:
            queryset = queryset.filter(sla_type=sla_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-breach_time')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.reporting import SLABreachSerializer
        return SLABreachSerializer
    
    def get_permissions(self):
        if self.action in ['acknowledge', 'escalate', 'resolve']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge SLA breach"""
        try:
            breach = self.get_object()
            breach.acknowledge(request.user)
            
            return Response({'success': True, 'acknowledged_at': breach.acknowledged_at})
        except Exception as e:
            logger.error(f"Error acknowledging SLA breach: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate SLA breach"""
        try:
            breach = self.get_object()
            reason = request.data.get('reason', '')
            
            breach.escalate(request.user, reason)
            
            return Response({
                'success': True,
                'escalated_at': breach.escalated_at,
                'escalation_level': breach.escalation_level
            })
        except Exception as e:
            logger.error(f"Error escalating SLA breach: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve SLA breach"""
        try:
            breach = self.get_object()
            resolution_time_minutes = request.data.get('resolution_time_minutes')
            
            breach.resolve(request.user, resolution_time_minutes)
            
            return Response({
                'success': True,
                'resolved_at': breach.resolved_at,
                'resolution_time_minutes': breach.resolution_time_minutes
            })
        except Exception as e:
            logger.error(f"Error resolving SLA breach: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def breach_severity(self, request, pk=None):
        """Get breach severity"""
        try:
            breach = self.get_object()
            severity = breach.get_breach_severity()
            
            return Response({
                'breach_severity': severity,
                'breach_percentage': breach.breach_percentage,
                'breach_duration_minutes': breach.breach_duration_minutes
            })
        except Exception as e:
            logger.error(f"Error getting breach severity: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_breaches(self, request):
        """Get all active SLA breaches"""
        try:
            active_breaches = SLABreach.get_active_breaches()
            
            breaches_data = []
            for breach in active_breaches:
                breaches_data.append({
                    'id': breach.id,
                    'name': breach.name,
                    'sla_type': breach.sla_type,
                    'severity': breach.severity,
                    'breach_time': breach.breach_time,
                    'breach_percentage': breach.breach_percentage,
                    'breach_duration_minutes': breach.get_duration_minutes(),
                    'escalation_level': breach.escalation_level
                })
            
            return Response(breaches_data)
        except Exception as e:
            logger.error(f"Error getting active breaches: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def breach_trends(self, request):
        """Get SLA breach trends"""
        try:
            days = int(request.query_params.get('days', 30))
            
            trends = SLABreach.get_breach_trends(days)
            
            return Response(trends)
        except Exception as e:
            logger.error(f"Error getting breach trends: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get SLA breach summary"""
        try:
            days = int(request.query_params.get('days', 30))
            cutoff_date = timezone.now() - timedelta(days=days)
            
            breaches = SLABreach.objects.filter(breach_time__gte=cutoff_date)
            
            summary = {
                'period_days': days,
                'total_breaches': breaches.count(),
                'by_sla_type': {},
                'by_severity': {},
                'by_status': {},
                'average_breach_percentage': 0,
                'average_resolution_time': 0
            }
            
            # By SLA type
            for sla_type in ['resolution_time', 'response_time', 'detection_time', 'availability', 'custom']:
                summary['by_sla_type'][sla_type] = breaches.filter(sla_type=sla_type).count()
            
            # By severity
            for severity in ['low', 'medium', 'high', 'critical']:
                summary['by_severity'][severity] = breaches.filter(severity=severity).count()
            
            # By status
            for status in ['active', 'resolved', 'escalated', 'acknowledged']:
                summary['by_status'][status] = breaches.filter(status=status).count()
            
            # Average breach percentage
            if breaches.exists():
                total_percentage = sum(breach.breach_percentage for breach in breaches)
                summary['average_breach_percentage'] = total_percentage / breaches.count()
                
                # Average resolution time
                resolved_breaches = breaches.filter(resolved_at__isnull=False)
                if resolved_breaches.exists():
                    total_resolution_time = sum(
                        (breach.resolved_at - breach.breach_time).total_seconds() / 60
                        for breach in resolved_breaches
                    )
                    summary['average_resolution_time'] = total_resolution_time / resolved_breaches.count()
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting SLA breach summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportingDashboardViewSet(viewsets.ViewSet):
    """Reporting dashboard ViewSet"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get reporting dashboard overview"""
        try:
            # Get recent reports
            recent_reports = AlertReport.objects.filter(
                status='completed'
            ).order_by('-generated_at')[:10]
            
            # Get SLA breaches
            active_breaches = SLABreach.get_active_breaches()
            
            # Get MTTR/MTTD metrics
            mttr_metrics = MTTRMetric.objects.all()
            mttd_metrics = MTTDMetric.objects.all()
            
            overview = {
                'recent_reports': [
                    {
                        'id': report.id,
                        'title': report.title,
                        'report_type': report.report_type,
                        'status': report.status,
                        'generated_at': report.generated_at
                    }
                    for report in recent_reports
                ],
                'active_sla_breaches': active_breaches.count(),
                'mttr_summary': {
                    'total_metrics': mttr_metrics.count(),
                    'average_mttr': sum(m.current_mttr_minutes for m in mttr_metrics) / mttr_metrics.count() if mttr_metrics.exists() else 0
                },
                'mttd_summary': {
                    'total_metrics': mttd_metrics.count(),
                    'average_mttd': sum(m.current_mttd_minutes for m in mttd_metrics) / mttd_metrics.count() if mttd_metrics.exists() else 0
                }
            }
            
            return Response(overview)
        except Exception as e:
            logger.error(f"Error getting reporting overview: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def metrics_summary(self, request):
        """Get comprehensive metrics summary"""
        try:
            days = int(request.query_params.get('days', 30))
            
            # Get MTTR metrics
            mttr_metrics = MTTRMetric.objects.all()
            mttr_summary = {
                'average_mttr': sum(m.current_mttr_minutes for m in mttr_metrics) / mttr_metrics.count() if mttr_metrics.exists() else 0,
                'average_compliance': sum(m.target_compliance_percentage for m in mttr_metrics) / mttr_metrics.count() if mttr_metrics.exists() else 0,
                'total_metrics': mttr_metrics.count()
            }
            
            # Get MTTD metrics
            mttd_metrics = MTTDMetric.objects.all()
            mttd_summary = {
                'average_mttd': sum(m.current_mttd_minutes for m in mttd_metrics) / mttd_metrics.count() if mttd_metrics.exists() else 0,
                'average_detection_rate': sum(m.detection_rate for m in mttd_metrics) / mttd_metrics.count() if mttd_metrics.exists() else 0,
                'total_metrics': mttd_metrics.count()
            }
            
            # Get SLA breaches
            cutoff_date = timezone.now() - timedelta(days=days)
            sla_breaches = SLABreach.objects.filter(breach_time__gte=cutoff_date)
            sla_summary = {
                'total_breaches': sla_breaches.count(),
                'resolved_breaches': sla_breaches.filter(status='resolved').count(),
                'active_breaches': sla_breaches.filter(status='active').count(),
                'by_severity': {},
                'average_breach_percentage': sum(breach.breach_percentage for breach in sla_breaches) / sla_breaches.count() if sla_breaches.exists() else 0
            }
            
            # By severity
            for severity in ['low', 'medium', 'high', 'critical']:
                sla_summary['by_severity'][severity] = sla_breaches.filter(severity=severity).count()
            
            return Response({
                'period_days': days,
                'mttr_summary': mttr_summary,
                'mttd_summary': mttd_summary,
                'sla_summary': sla_summary
            })
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
