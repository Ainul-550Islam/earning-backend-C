"""
Traditional Django Views for Offer Routing System

This module provides traditional Django views for the offer routing system,
including template rendering, form handling, and direct HTTP responses.
These views complement the DRF viewsets for web interface functionality.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import FormView
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.cache import cache
from django.conf import settings
import json
import logging

from .models import (
    OfferRoute, RoutingABTest, RoutingDecisionLog, RoutePerformanceStat,
    UserOfferHistory, OfferRoutingCap, PersonalizationConfig
)
from .services.core import routing_engine
from .services.analytics import analytics_service
from .services.monitoring import monitoring_service
from .forms import (
    OfferRouteForm, RoutingABTestForm, BulkAssignmentForm,
    PerformanceReportForm, SystemConfigForm
)

logger = logging.getLogger(__name__)


# Dashboard Views
class RoutingDashboardView(LoginRequiredMixin, TemplateView):
    """Main routing dashboard view."""
    
    template_name = 'offer_routing/dashboard.html'
    
    def get_context_data(self, **kwargs):
        """Add dashboard data to context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Basic stats
        context.update({
            'total_routes': OfferRoute.objects.filter(tenant=user).count(),
            'active_routes': OfferRoute.objects.filter(tenant=user, is_active=True).count(),
            'total_tests': RoutingABTest.objects.filter(tenant=user).count(),
            'active_tests': RoutingABTest.objects.filter(tenant=user, is_active=True).count(),
        })
        
        # Recent decisions
        recent_decisions = RoutingDecisionLog.objects.filter(
            user=user
        ).order_by('-created_at')[:10]
        context['recent_decisions'] = recent_decisions
        
        # Performance stats
        today = timezone.now().date()
        today_stats = RoutePerformanceStat.objects.filter(
            tenant=user,
            date=today
        ).first()
        
        if today_stats:
            context['today_stats'] = {
                'impressions': today_stats.impressions,
                'clicks': today_stats.clicks,
                'conversions': today_stats.conversions,
                'revenue': today_stats.revenue,
                'conversion_rate': (today_stats.conversions / today_stats.impressions * 100) if today_stats.impressions > 0 else 0,
            }
        
        # System health
        context['system_health'] = monitoring_service.get_system_health()
        
        return context


# Route Management Views
class RouteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List view for offer routes."""
    
    model = OfferRoute
    template_name = 'offer_routing/route_list.html'
    context_object_name = 'routes'
    permission_required = 'offer_routing.view_routes'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter routes by tenant."""
        queryset = OfferRoute.objects.filter(tenant=self.request.user)
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        return queryset.order_by('priority', 'name')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'status_filter': self.request.GET.get('status', ''),
            'search_query': self.request.GET.get('search', ''),
        })
        return context


class RouteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detail view for offer routes."""
    
    model = OfferRoute
    template_name = 'offer_routing/route_detail.html'
    context_object_name = 'route'
    permission_required = 'offer_routing.view_routes'
    
    def get_queryset(self):
        """Filter by tenant."""
        return OfferRoute.objects.filter(tenant=self.request.user)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        route = self.get_object()
        
        # Route statistics
        context['route_stats'] = analytics_service.get_route_statistics(route.id)
        
        # Recent decisions for this route
        context['recent_decisions'] = RoutingDecisionLog.objects.filter(
            route_id=route.id
        ).order_by('-created_at')[:20]
        
        # Performance data
        context['performance_data'] = RoutePerformanceStat.objects.filter(
            offer=route
        ).order_by('-date')[:30]
        
        return context


class RouteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for offer routes."""
    
    model = OfferRoute
    form_class = OfferRouteForm
    template_name = 'offer_routing/route_form.html'
    permission_required = 'offer_routing.add_routes'
    success_url = reverse_lazy('offer_routing:route_list')
    
    def form_valid(self, form):
        """Set tenant and save."""
        form.instance.tenant = self.request.user
        messages.success(self.request, 'Route created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Route'
        return context


class RouteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update view for offer routes."""
    
    model = OfferRoute
    form_class = OfferRouteForm
    template_name = 'offer_routing/route_form.html'
    permission_required = 'offer_routing.change_routes'
    
    def get_queryset(self):
        """Filter by tenant."""
        return OfferRoute.objects.filter(tenant=self.request.user)
    
    def get_success_url(self):
        """Return to detail view after update."""
        return reverse('offer_routing:route_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        """Save and show success message."""
        messages.success(self.request, 'Route updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Route: {self.object.name}'
        return context


class RouteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Delete view for offer routes."""
    
    model = OfferRoute
    template_name = 'offer_routing/route_confirm_delete.html'
    permission_required = 'offer_routing.delete_routes'
    success_url = reverse_lazy('offer_routing:route_list')
    
    def get_queryset(self):
        """Filter by tenant."""
        return OfferRoute.objects.filter(tenant=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        """Delete and show success message."""
        messages.success(request, 'Route deleted successfully.')
        return super().delete(request, *args, **kwargs)


# A/B Testing Views
class ABTestListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List view for A/B tests."""
    
    model = RoutingABTest
    template_name = 'offer_routing/abtest_list.html'
    context_object_name = 'tests'
    permission_required = 'offer_routing.view_ab_tests'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter tests by tenant."""
        queryset = RoutingABTest.objects.filter(tenant=self.request.user)
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'completed':
            queryset = queryset.filter(is_active=False, ended_at__isnull=False)
        elif status_filter == 'draft':
            queryset = queryset.filter(is_active=False, started_at__isnull=True)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'status_filter': self.request.GET.get('status', ''),
        })
        return context


class ABTestDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Detail view for A/B tests."""
    
    model = RoutingABTest
    template_name = 'offer_routing/abtest_detail.html'
    context_object_name = 'test'
    permission_required = 'offer_routing.view_ab_tests'
    
    def get_queryset(self):
        """Filter by tenant."""
        return RoutingABTest.objects.filter(tenant=self.request.user)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        test = self.get_object()
        
        # Test statistics
        context['test_stats'] = analytics_service.get_ab_test_statistics(test.id)
        
        # Assignment data
        from .models import ABTestAssignment
        context['assignments'] = ABTestAssignment.objects.filter(test=test).order_by('-assigned_at')[:50]
        
        # Results data
        from .models import ABTestResult
        context['results'] = ABTestResult.objects.filter(test=test).order_by('-analyzed_at')[:10]
        
        return context


class ABTestCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create view for A/B tests."""
    
    model = RoutingABTest
    form_class = RoutingABTestForm
    template_name = 'offer_routing/abtest_form.html'
    permission_required = 'offer_routing.add_ab_tests'
    success_url = reverse_lazy('offer_routing:abtest_list')
    
    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Set created by and save."""
        form.instance.tenant = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, 'A/B test created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create A/B Test'
        return context


# Analytics Views
class AnalyticsDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Analytics dashboard view."""
    
    template_name = 'offer_routing/analytics_dashboard.html'
    permission_required = 'offer_routing.view_analytics'
    
    def get_context_data(self, **kwargs):
        """Add analytics data to context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Time range from request
        days = int(self.request.GET.get('days', 30))
        
        # Performance metrics
        context['performance_metrics'] = analytics_service.get_performance_metrics(user.id, days)
        
        # Route performance
        context['route_performance'] = analytics_service.get_route_performance_summary(user.id, days)
        
        # User analytics
        context['user_analytics'] = analytics_service.get_user_analytics_summary(user.id, days)
        
        # Conversion trends
        context['conversion_trends'] = analytics_service.get_conversion_trends(user.id, days)
        
        # Revenue analytics
        context['revenue_analytics'] = analytics_service.get_revenue_analytics(user.id, days)
        
        context['days'] = days
        
        return context


class PerformanceReportView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Performance report view."""
    
    template_name = 'offer_routing/performance_report.html'
    form_class = PerformanceReportForm
    permission_required = 'offer_routing.view_analytics'
    
    def form_valid(self, form):
        """Generate performance report."""
        cleaned_data = form.cleaned_data
        
        # Generate report data
        report_data = analytics_service.generate_performance_report(
            tenant_id=self.request.user.id,
            date_from=cleaned_data['date_from'],
            date_to=cleaned_data['date_to'],
            report_type=cleaned_data['report_type']
        )
        
        context = self.get_context_data()
        context.update({
            'form': form,
            'report_data': report_data,
            'report_generated': True
        })
        
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Performance Report'
        return context


# System Configuration Views
class SystemConfigView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """System configuration view."""
    
    template_name = 'offer_routing/system_config.html'
    form_class = SystemConfigForm
    permission_required = 'offer_routing.manage_system'
    
    def get_initial(self):
        """Get initial configuration."""
        return {
            'cache_enabled': cache.get('routing_cache_enabled', True),
            'personalization_enabled': cache.get('personalization_enabled', True),
            'ab_testing_enabled': cache.get('ab_testing_enabled', True),
            'monitoring_enabled': cache.get('monitoring_enabled', True),
            'max_concurrent_requests': cache.get('max_concurrent_requests', 100),
            'default_timeout_ms': cache.get('default_timeout_ms', 5000),
        }
    
    def form_valid(self, form):
        """Save configuration."""
        cleaned_data = form.cleaned_data
        
        # Save to cache
        cache.set('routing_cache_enabled', cleaned_data['cache_enabled'])
        cache.set('personalization_enabled', cleaned_data['personalization_enabled'])
        cache.set('ab_testing_enabled', cleaned_data['ab_testing_enabled'])
        cache.set('monitoring_enabled', cleaned_data['monitoring_enabled'])
        cache.set('max_concurrent_requests', cleaned_data['max_concurrent_requests'])
        cache.set('default_timeout_ms', cleaned_data['default_timeout_ms'])
        
        messages.success(self.request, 'System configuration updated successfully.')
        
        return super().form_valid(form)
    
    def get_success_url(self):
        """Return to current page."""
        return reverse('offer_routing:system_config')


# API Views (AJAX Endpoints)
class RoutingTestView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """AJAX view for testing routing."""
    
    permission_required = 'offer_routing.test_routes'
    
    def post(self, request):
        """Handle routing test request."""
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            context = data.get('context', {})
            
            if not user_id:
                return JsonResponse({'error': 'user_id is required'}, status=400)
            
            # Perform routing
            result = routing_engine.route_offers(
                user_id=user_id,
                context=context,
                limit=10,
                cache_enabled=False  # Don't use cache for testing
            )
            
            return JsonResponse({
                'success': True,
                'result': result
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Routing test error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class BulkAssignmentView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Bulk assignment view for A/B tests."""
    
    template_name = 'offer_routing/bulk_assignment.html'
    form_class = BulkAssignmentForm
    permission_required = 'offer_routing.manage_ab_tests'
    
    def get_form_kwargs(self):
        """Add tenant to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Handle bulk assignment."""
        cleaned_data = form.cleaned_data
        
        try:
            # Perform bulk assignment
            from .services.ab_test import ab_test_service
            
            results = ab_test_service.bulk_assign_users(
                test_id=cleaned_data['test_id'],
                user_ids=cleaned_data['user_ids']
            )
            
            messages.success(
                self.request,
                f"Successfully assigned {results['assigned_count']} users to test."
            )
            
            return redirect('offer_routing:abtest_detail', pk=cleaned_data['test_id'])
            
        except Exception as e:
            messages.error(self.request, f"Error during bulk assignment: {e}")
            return self.form_invalid(form)


# Health Check Views
class HealthCheckView(View):
    """Health check endpoint for monitoring."""
    
    def get(self, request):
        """Return system health status."""
        try:
            health_data = monitoring_service.get_system_health()
            
            return JsonResponse({
                'status': 'healthy' if health_data['overall_status'] == 'ok' else 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'services': health_data['services'],
                'metrics': health_data['metrics']
            })
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return JsonResponse({
                'status': 'error',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }, status=500)


class MetricsView(View):
    """Metrics endpoint for monitoring."""
    
    def get(self, request):
        """Return system metrics."""
        try:
            metrics_data = monitoring_service.get_current_metrics()
            
            return JsonResponse({
                'timestamp': timezone.now().isoformat(),
                'metrics': metrics_data
            })
            
        except Exception as e:
            logger.error(f"Metrics error: {e}")
            return JsonResponse({
                'error': str(e)
            }, status=500)


# Export Views
class ExportDecisionsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Export decision logs view."""
    
    permission_required = 'offer_routing.export_analytics'
    
    def get(self, request):
        """Handle export request."""
        try:
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            format_type = request.GET.get('format', 'csv')
            
            if not date_from or not date_to:
                return JsonResponse({'error': 'date_from and date_to are required'}, status=400)
            
            # Parse dates
            date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            
            # Generate export
            export_data = analytics_service.export_decision_logs(
                tenant_id=request.user.id,
                date_from=date_from,
                date_to=date_to,
                format=format_type
            )
            
            if format_type == 'csv':
                response = HttpResponse(export_data, content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="decision_logs_{date_from}_{date_to}.csv"'
            else:
                response = HttpResponse(export_data, content_type='application/json')
                response['Content-Disposition'] = f'attachment; filename="decision_logs_{date_from}_{date_to}.json"'
            
            return response
            
        except ValueError as e:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        except Exception as e:
            logger.error(f"Export error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# Utility Views
class ClearCacheView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Clear cache view."""
    
    permission_required = 'offer_routing.manage_system'
    
    def post(self, request):
        """Clear routing cache."""
        try:
            # Clear routing cache
            cache.delete_pattern('routing:*')
            cache.delete_pattern('offer_routing:*')
            
            messages.success(request, 'Cache cleared successfully.')
            
        except Exception as e:
            messages.error(request, f'Error clearing cache: {e}')
        
        return redirect('offer_routing:system_config')


class ResetCapsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Reset caps view."""
    
    permission_required = 'offer_routing.manage_caps'
    
    def post(self, request):
        """Reset daily caps."""
        try:
            from .services.cap import cap_service
            
            reset_count = cap_service.reset_daily_caps()
            
            messages.success(request, f'Reset {reset_count} daily caps.')
            
        except Exception as e:
            messages.error(request, f'Error resetting caps: {e}')
        
        return redirect('offer_routing:dashboard')


# Template Views
class HelpView(LoginRequiredMixin, TemplateView):
    """Help and documentation view."""
    
    template_name = 'offer_routing/help.html'
    
    def get_context_data(self, **kwargs):
        """Add help content."""
        context = super().get_context_data(**kwargs)
        
        # Help sections
        context['help_sections'] = {
            'getting_started': {
                'title': 'Getting Started',
                'content': 'Learn how to set up your first offer route and start routing offers.'
            },
            'routing_basics': {
                'title': 'Routing Basics',
                'content': 'Understand the fundamentals of offer routing and targeting.'
            },
            'ab_testing': {
                'title': 'A/B Testing',
                'content': 'Learn how to set up and analyze A/B tests for your offers.'
            },
            'analytics': {
                'title': 'Analytics & Reporting',
                'content': 'Explore analytics features and generate performance reports.'
            },
            'advanced_features': {
                'title': 'Advanced Features',
                'content': 'Discover advanced features like personalization and caps.'
            }
        }
        
        return context


class ErrorView(TemplateView):
    """Custom error view."""
    
    template_name = 'offer_routing/error.html'
    
    def get_context_data(self, **kwargs):
        """Add error context."""
        context = super().get_context_data(**kwargs)
        context['error_code'] = kwargs.get('error_code', 500)
        return context


# Decorator-based Views
@login_required
@permission_required('offer_routing.view_routes')
def route_preview(request, pk):
    """Preview route functionality."""
    route = get_object_or_404(OfferRoute, pk=pk, tenant=request.user)
    
    if request.method == 'POST':
        try:
            test_user_id = request.POST.get('test_user_id')
            test_context = json.loads(request.POST.get('test_context', '{}'))
            
            if not test_user_id:
                messages.error(request, 'Test user ID is required.')
                return redirect('offer_routing:route_preview', pk=pk)
            
            # Test routing with this route
            result = routing_engine.test_route(route.id, test_user_id, test_context)
            
            context = {
                'route': route,
                'test_result': result,
                'test_user_id': test_user_id,
                'test_context': test_context
            }
            
            return render(request, 'offer_routing/route_preview.html', context)
            
        except json.JSONDecodeError:
            messages.error(request, 'Invalid context JSON.')
        except Exception as e:
            messages.error(request, f'Error testing route: {e}')
    
    context = {
        'route': route,
        'test_context': json.dumps({
            'ip_address': '127.0.0.1',
            'user_agent': 'Mozilla/5.0 (Test)',
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }, indent=2)
    }
    
    return render(request, 'offer_routing/route_preview.html', context)


@login_required
@permission_required('offer_routing.view_analytics')
def real_time_metrics(request):
    """Real-time metrics view."""
    if request.is_ajax():
        try:
            metrics = monitoring_service.get_real_time_metrics(request.user.id)
            return JsonResponse({'metrics': metrics})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return render(request, 'offer_routing/real_time_metrics.html')


@login_required
@permission_required('offer_routing.manage_ab_tests')
def stop_ab_test(request, pk):
    """Stop an A/B test."""
    test = get_object_or_404(RoutingABTest, pk=pk, tenant=request.user)
    
    if request.method == 'POST':
        try:
            from .services.ab_test import ab_test_service
            
            result = ab_test_service.stop_test(test.id)
            
            if result['success']:
                messages.success(request, f'A/B test "{test.name}" stopped successfully.')
            else:
                messages.error(request, f'Error stopping test: {result["error"]}')
            
        except Exception as e:
            messages.error(request, f'Error stopping test: {e}')
        
        return redirect('offer_routing:abtest_detail', pk=pk)
    
    return render(request, 'offer_routing/stop_ab_test.html', {'test': test})


# Utility Functions
def get_client_ip(request):
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def validate_json_data(data):
    """Validate JSON data."""
    try:
        if isinstance(data, str):
            return json.loads(data)
        return data
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON data")


def format_response_time(ms):
    """Format response time for display."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    else:
        return f"{ms/1000:.2f}s"


def format_percentage(value, decimal_places=2):
    """Format percentage for display."""
    return f"{value:.{decimal_places}f}%"


# Error Handlers
def custom_404(request, exception):
    """Custom 404 handler."""
    return render(request, 'offer_routing/404.html', status=404)


def custom_500(request):
    """Custom 500 handler."""
    return render(request, 'offer_routing/500.html', status=500)


def custom_403(request, exception):
    """Custom 403 handler."""
    return render(request, 'offer_routing/403.html', status=403)


# Context Processors
def routing_context(request):
    """Add routing context to all templates."""
    if request.user.is_authenticated:
        return {
            'routing_stats': {
                'unread_insights': RoutingInsight.objects.filter(
                    tenant=request.user,
                    is_resolved=False
                ).count(),
                'active_tests': RoutingABTest.objects.filter(
                    tenant=request.user,
                    is_active=True
                ).count(),
            }
        }
    return {}
