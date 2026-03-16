# admin.py
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, mark_safe
from django.db.models import Count, Q, Sum, Avg
from django.urls import reverse, path
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.contrib import messages
from django.template.response import TemplateResponse
from django.core.cache import cache
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.template.loader import render_to_string
import logging
import json
from datetime import datetime, timedelta
import csv
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
User = get_user_model()
if not admin.site.is_registered(User):
    admin.site.register(User, UserAdmin)
    print("[OK] UserAdmin registered in localization/admin.py")
from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)

logger = logging.getLogger(__name__)


# ======================== Custom Filters (Defined First) ========================

class ActiveFilter(admin.SimpleListFilter):
    """Filter for active/inactive status"""
    title = _('Status')
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', _('[OK] Active')),
            ('0', _('[ERROR] Inactive')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_active=True)
        if self.value() == '0':
            return queryset.filter(is_active=False)
        return queryset


class DefaultFilter(admin.SimpleListFilter):
    """Filter for default items"""
    title = _('Default Status')
    parameter_name = 'is_default'

    def lookups(self, request, model_admin):
        return (
            ('1', _('[STAR] Default')),
            ('0', _('◯ Not Default')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_default=True)
        if self.value() == '0':
            return queryset.filter(is_default=False)
        return queryset


class TranslationSourceFilter(admin.SimpleListFilter):
    """Filter translations by source"""
    title = _('Source')
    parameter_name = 'source'

    def lookups(self, request, model_admin):
        return (
            ('manual', _('✍️ Manual')),
            ('auto', _('🤖 Auto-translated')),
            ('import', _('📥 Imported')),
            ('api', _('🌐 API')),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(source=self.value())
        return queryset


class MissingTranslationResolvedFilter(admin.SimpleListFilter):
    """Filter missing translations by resolved status"""
    title = _('Resolution Status')
    parameter_name = 'resolved'

    def lookups(self, request, model_admin):
        return (
            ('1', _('[OK] Resolved')),
            ('0', _('[ERROR] Unresolved')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(resolved=True)
        if self.value() == '0':
            return queryset.filter(resolved=False)
        return queryset


class ApprovedFilter(admin.SimpleListFilter):
    """Filter for approval status"""
    title = _('Approval Status')
    parameter_name = 'is_approved'

    def lookups(self, request, model_admin):
        return (
            ('1', _('[OK] Approved')),
            ('0', _('⏳ Pending')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_approved=True)
        if self.value() == '0':
            return queryset.filter(is_approved=False)
        return queryset


class RTLFilter(admin.SimpleListFilter):
    """Filter for RTL languages"""
    title = _('Text Direction')
    parameter_name = 'is_rtl'

    def lookups(self, request, model_admin):
        return (
            ('1', _('🔁 RTL')),
            ('0', _('➡️ LTR')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_rtl=True)
        if self.value() == '0':
            return queryset.filter(is_rtl=False)
        return queryset


class CityCapitalFilter(admin.SimpleListFilter):
    """Filter for capital cities"""
    title = _('City Type')
    parameter_name = 'is_capital'

    def lookups(self, request, model_admin):
        return (
            ('1', _('👑 Capital')),
            ('0', _('🏙️ Regular')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_capital=True)
        if self.value() == '0':
            return queryset.filter(is_capital=False)
        return queryset


class DSTFilter(admin.SimpleListFilter):
    """Filter for Daylight Saving Time"""
    title = _('Daylight Saving')
    parameter_name = 'is_dst'

    def lookups(self, request, model_admin):
        return (
            ('1', _('☀️ DST')),
            ('0', _('❄️ No DST')),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(is_dst=True)
        if self.value() == '0':
            return queryset.filter(is_dst=False)
        return queryset


class ExchangeRateFilter(admin.SimpleListFilter):
    """Filter currencies by exchange rate status"""
    title = _('Exchange Rate')
    parameter_name = 'exchange_status'

    def lookups(self, request, model_admin):
        return (
            ('needs_update', _('[WARN] Needs Update')),
            ('updated', _('[OK] Updated')),
            ('zero', _('[ERROR] Zero Rate')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'needs_update':
            return queryset.filter(
                Q(exchange_rate_updated_at__isnull=True) |
                Q(exchange_rate_updated_at__lt=timezone.now() - timedelta(days=1))
            )
        if self.value() == 'updated':
            return queryset.filter(
                exchange_rate_updated_at__gte=timezone.now() - timedelta(days=1)
            )
        if self.value() == 'zero':
            return queryset.filter(exchange_rate=0)
        return queryset


# ======================== Chart.js Integration ========================

class ChartMixin:
    """Mixin for adding charts to admin views"""
    
    def get_chart_data(self, request):
        """Get chart data - override in subclasses"""
        return {}
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Add chart data
        extra_context['charts'] = self.get_chart_data(request)
        
        # Add Chart.js
        extra_context['media'] = self.media + format_html(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )
        
        return super().changelist_view(request, extra_context)


# ======================== Dashboard Widgets ========================

class DashboardWidget:
    """Reusable dashboard widgets"""
    
    @staticmethod
    def metric_card(title, value, icon, color, subtitle=None, link=None):
        """Create a metric card widget"""
        link_html = f' onclick="window.location=\'{link}\'" style="cursor: pointer;"' if link else ''
        
        return format_html(
            '<div class="metric-card"{} style="background: white; border-radius: 10px; padding: 20px; '
            'box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-left: 4px solid {}; '
            'transition: transform 0.3s; margin-bottom: 20px;">'
            '<div style="display: flex; justify-content: space-between; align-items: center;">'
            '<div>'
            '<div style="font-size: 14px; color: #6c757d;">{}</div>'
            '<div style="font-size: 32px; font-weight: bold; color: {};">{}</div>'
            '{}</div>'
            '<div style="font-size: 48px; opacity: 0.2;">{}</div>'
            '</div></div>',
            link_html, color, title, color, value,
            f'<div style="font-size: 12px; color: #6c757d;">{subtitle}</div>' if subtitle else '',
            icon
        )
    
    @staticmethod
    def progress_card(title, value, total, icon, color, link=None):
        """Create a progress card widget"""
        percentage = (value / total * 100) if total > 0 else 0
        link_html = f' onclick="window.location=\'{link}\'" style="cursor: pointer;"' if link else ''
        
        return format_html(
            '<div class="progress-card"{} style="background: white; border-radius: 10px; padding: 20px; '
            'box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px;">'
            '<div style="display: flex; justify-content: space-between; margin-bottom: 10px;">'
            '<span style="font-size: 16px; font-weight: bold;">{} {}</span>'
            '<span style="font-size: 14px;">{}/{} ({:.1f}%)</span>'
            '</div>'
            '<div style="height: 10px; background: #e9ecef; border-radius: 5px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: {}; transition: width 0.3s;"></div>'
            '</div></div>',
            link_html, icon, title, value, total, percentage, percentage, color
        )
    
    @staticmethod
    def alert_card(message, type='info'):
        """Create an alert card"""
        colors = {
            'info': {'bg': '#cce5ff', 'text': '#004085', 'border': '#b8daff'},
            'success': {'bg': '#d4edda', 'text': '#155724', 'border': '#c3e6cb'},
            'warning': {'bg': '#fff3cd', 'text': '#856404', 'border': '#ffeeba'},
            'danger': {'bg': '#f8d7da', 'text': '#721c24', 'border': '#f5c6cb'},
        }
        color = colors.get(type, colors['info'])
        
        return format_html(
            '<div class="alert alert-{}" style="background: {}; color: {}; border: 1px solid {}; '
            'border-radius: 5px; padding: 12px; margin-bottom: 15px;">{}</div>',
            type, color['bg'], color['text'], color['border'], message
        )


# ======================== Bulk Edit Mixin ========================

class BulkEditMixin:
    """Mixin for bulk editing fields"""
    
    bulk_edit_fields = ['is_active', 'is_default']
    
    def get_bulk_edit_fields(self, request):
        """Get fields available for bulk edit"""
        return self.bulk_edit_fields
    
    def get_urls(self):
        """Add bulk edit URL"""
        urls = super().get_urls()
        custom_urls = [
            path('bulk-edit/', self.admin_site.admin_view(self.bulk_edit_view), name='bulk-edit'),
        ]
        return custom_urls + urls
    
    def bulk_edit_view(self, request):
        """Handle bulk edit requests"""
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                ids = data.get('ids', [])
                updates = data.get('updates', {})
                
                if not ids:
                    return JsonResponse({'error': 'No items selected'}, status=400)
                
                # Validate fields
                for field in updates.keys():
                    if field not in self.get_bulk_edit_fields(request):
                        return JsonResponse({'error': f'Invalid field: {field}'}, status=400)
                
                # Perform bulk update
                with transaction.atomic():
                    queryset = self.get_queryset(request).filter(id__in=ids)
                    updated = queryset.update(**updates)
                    
                    # Log the action
                    self.log_change(request, queryset.first(), f'Bulk edited {updated} items')
                    
                    # Clear cache for affected items
                    for obj in queryset:
                        if hasattr(obj, 'code'):
                            cache.delete_pattern(f"*{obj.code}*")
                
                return JsonResponse({
                    'success': True,
                    'updated': updated,
                    'message': f'Successfully updated {updated} items'
                })
                
            except Exception as e:
                logger.error(f"Bulk edit error: {e}")
                return JsonResponse({'error': str(e)}, status=500)
        
        # GET request - show bulk edit form
        context = {
            'fields': self.get_bulk_edit_fields(request),
            'model_name': self.model._meta.verbose_name_plural,
            'opts': self.model._meta,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/bulk_edit.html', context)
    
    class Media:
        js = ('admin/js/bulk_edit.js',)
        css = {'all': ('admin/css/bulk_edit.css',)}


# ======================== Import/Export with Progress ========================

class ImportExportMixin:
    """Mixin for import/export functionality with progress tracking"""
    
    def get_urls(self):
        """Add import/export URLs"""
        urls = super().get_urls()
        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view), name='import'),
            path('export/', self.admin_site.admin_view(self.export_view), name='export'),
            path('import-progress/<str:task_id>/', self.admin_site.admin_view(self.import_progress), name='import-progress'),
        ]
        return custom_urls + urls
    
    def import_view(self, request):
        """Handle import requests"""
        if request.method == 'POST':
            if 'file' not in request.FILES:
                messages.error(request, _('Please select a file'))
                return HttpResponseRedirect(request.path)
            
            file = request.FILES['file']
            format = request.POST.get('format', 'json')
            
            # Start async import task
            from .tasks import import_translations_task
            task = import_translations_task.delay(
                file.read().decode('utf-8'),
                format,
                request.user.id
            )
            
            return JsonResponse({
                'task_id': task.id,
                'status': 'started'
            })
        
        # GET request - show import form
        context = {
            'formats': ['json', 'csv', 'po'],
            'opts': self.model._meta,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/import.html', context)
    
    def export_view(self, request):
        """Handle export requests"""
        if request.method == 'POST':
            format = request.POST.get('format', 'json')
            queryset = self.get_queryset(request)
            
            if format == 'json':
                data = self.export_json(queryset)
                response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
                response['Content-Disposition'] = f'attachment; filename="{self.model.__name__}_export.json"'
                return response
            
            elif format == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{self.model.__name__}_export.csv"'
                
                writer = csv.writer(response)
                # Write headers
                headers = [field.name for field in self.model._meta.fields]
                writer.writerow(headers)
                
                # Write data
                for obj in queryset:
                    row = [getattr(obj, field) for field in headers]
                    writer.writerow(row)
                
                return response
        
        # GET request - show export form
        context = {
            'formats': ['json', 'csv', 'po'],
            'opts': self.model._meta,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/export.html', context)
    
    def import_progress(self, request, task_id):
        """Check import progress"""
        from celery.result import AsyncResult
        task = AsyncResult(task_id)
        
        if task.ready():
            if task.successful():
                return JsonResponse({
                    'status': 'completed',
                    'result': task.result
                })
            else:
                return JsonResponse({
                    'status': 'failed',
                    'error': str(task.result)
                })
        
        return JsonResponse({
            'status': 'processing',
            'progress': task.info.get('progress', 0) if task.info else 0
        })
    
    def export_json(self, queryset):
        """Export queryset as JSON"""
        data = []
        for obj in queryset:
            obj_data = {}
            for field in obj._meta.fields:
                value = getattr(obj, field.name)
                if hasattr(value, 'str'):
                    value = str(value)
                obj_data[field.name] = value
            data.append(obj_data)
        return data
    
    class Media:
        js = ('admin/js/import_export.js',)
        css = {'all': ('admin/css/import_export.css',)}


# ======================== Activity Timeline ========================

class ActivityTimelineMixin:
    """Mixin for showing activity timeline"""
    
    def activity_timeline(self, obj):
        """Show activity timeline for object"""
        activities = []
        
        # Get model history if available
        if hasattr(obj, 'history'):
            for version in obj.history.all()[:10]:
                activities.append({
                    'date': version.history_date,
                    'user': version.history_user,
                    'type': 'update',
                    'changes': self.format_changes(version)
                })
        
        # Get related activities
        if hasattr(obj, 'translations'):
            for trans in obj.translations.all()[:5]:
                activities.append({
                    'date': trans.created_at,
                    'user': trans.approved_by,
                    'type': 'translation',
                    'description': f'Translation added: {trans.value[:50]}...'
                })
        
        # Render timeline
        return render_to_string('admin/timeline.html', {
            'activities': sorted(activities, key=lambda x: x['date'], reverse=True)
        })
    
    def format_changes(self, version):
        """Format changes from version"""
        if not version.delta:
            return 'No changes'
        
        changes = []
        for field, (old, new) in version.delta.items():
            changes.append(f'{field}: {old} → {new}')
        
        return '<br>'.join(changes)
    
    activity_timeline.short_description = _('Activity Timeline')
    activity_timeline.allow_tags = True


# ======================== Related Objects Popup ========================

class RelatedObjectsMixin:
    """Mixin for showing related objects in popup"""
    
    def related_objects_popup(self, obj):
        """Show related objects in popup"""
        return format_html(
            '<a href="#" onclick="showRelatedObjects(\'{}\', {})" '
            'class="related-link button" style="background-color: #17a2b8; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; display: inline-block;">'
            '🔍 View Related ({})</a>',
            obj._meta.model_name, obj.id, self.get_related_count(obj)
        )
    
    def get_related_count(self, obj):
        """Get count of related objects"""
        count = 0
        for rel in obj._meta.related_objects:
            related_name = rel.get_accessor_name()
            if hasattr(obj, related_name):
                try:
                    count += getattr(obj, related_name).count()
                except:
                    pass
        return count
    
    def get_urls(self):
        """Add related objects URL"""
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/related/', 
                 self.admin_site.admin_view(self.related_objects_view),
                 name='related-objects'),
        ]
        return custom_urls + urls
    
    def related_objects_view(self, request, object_id):
        """Show related objects in JSON format"""
        obj = get_object_or_404(self.model, pk=object_id)
        
        related_data = []
        for rel in obj._meta.related_objects:
            related_name = rel.get_accessor_name()
            if hasattr(obj, related_name):
                try:
                    related_qs = getattr(obj, related_name).all()
                    for related_obj in related_qs[:10]:
                        related_data.append({
                            'model': rel.related_model.__name__,
                            'id': related_obj.id,
                            'name': str(related_obj),
                            'url': reverse(f'admin:{rel.related_model._meta.app_label}_{rel.related_model._meta.model_name}_change', 
                                         args=[related_obj.id])
                        })
                except:
                    pass
        
        return JsonResponse({'objects': related_data})
    
    class Media:
        js = ('admin/js/related_objects.js',)
        css = {'all': ('admin/css/related_objects.css',)}


# ======================== Advanced Search ========================

class AdvancedSearchMixin:
    """Advanced search with multiple criteria"""
    
    advanced_search_fields = {
        'created_after': {'type': 'date', 'label': _('Created After')},
        'created_before': {'type': 'date', 'label': _('Created Before')},
        'has_translations': {'type': 'boolean', 'label': _('Has Translations')},
        'min_coverage': {'type': 'number', 'label': _('Minimum Coverage (%)')},
        'updated_by': {'type': 'user', 'label': _('Updated By')},
    }
    
    def get_search_results(self, request, queryset, search_term):
        """Override to add advanced search"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        # Apply advanced filters
        for field, config in self.advanced_search_fields.items():
            value = request.GET.get(f'adv_{field}')
            if value:
                queryset = self.apply_advanced_filter(queryset, field, value, config)
        
        return queryset, use_distinct
    
    def apply_advanced_filter(self, queryset, field, value, config):
        """Apply advanced filter to queryset"""
        if config['type'] == 'date':
            try:
                date = datetime.strptime(value, '%Y-%m-%d').date()
                return queryset.filter(**{f'{field}__gte': date})
            except:
                pass
        
        elif config['type'] == 'boolean':
            bool_val = value.lower() in ['true', 'yes', '1']
            if field == 'has_translations':
                if bool_val:
                    return queryset.annotate(trans_count=Count('translations')).filter(trans_count__gt=0)
                else:
                    return queryset.annotate(trans_count=Count('translations')).filter(trans_count=0)
        
        elif config['type'] == 'number':
            try:
                num_val = float(value)
                return queryset.filter(**{f'{field}__gte': num_val})
            except:
                pass
        
        elif config['type'] == 'user':
            return queryset.filter(**{field: value})
        
        return queryset
    
    def changelist_view(self, request, extra_context=None):
        """Add advanced search form to context"""
        extra_context = extra_context or {}
        extra_context['advanced_search_fields'] = self.advanced_search_fields
        return super().changelist_view(request, extra_context)
    
    class Media:
        js = ('admin/js/advanced_search.js',)
        css = {'all': ('admin/css/advanced_search.css',)}


# ======================== Real-time Notifications ========================

class NotificationMixin:
    """Mixin for real-time notifications"""
    
    def get_alerts(self, request):
        """Check for alerts and return notifications"""
        alerts = []
        
        # Check for low translation coverage
        try:
            for lang in Language.objects.filter(is_active=True):
                total_keys = TranslationKey.objects.count()
                if total_keys > 0:
                    translated = Translation.objects.filter(
                        language=lang,
                        is_approved=True
                    ).count()
                    coverage = (translated / total_keys * 100)
                    
                    if coverage < 50:
                        alerts.append({
                            'type': 'warning',
                            'message': f'[WARN] {lang.name} translation coverage is only {coverage:.1f}%',
                            'link': reverse('admin:localization_translation_changelist') + f'?language__id__exact={lang.id}'
                        })
        except Exception as e:
            logger.error(f"Error checking translation coverage: {e}")
        
        # Check for missing translations
        try:
            missing_count = MissingTranslation.objects.filter(resolved=False).count()
            if missing_count > 10:
                alerts.append({
                    'type': 'danger',
                    'message': f'[ERROR] {missing_count} unresolved missing translations',
                    'link': reverse('admin:localization_missingtranslation_changelist') + '?resolved__exact=0'
                })
        except Exception as e:
            logger.error(f"Error checking missing translations: {e}")
        
        # Check for expired cache
        try:
            expired_cache = TranslationCache.objects.filter(expires_at__lt=timezone.now()).count()
            if expired_cache > 100:
                alerts.append({
                    'type': 'info',
                    'message': f'🧹 {expired_cache} expired cache entries',
                    'link': reverse('admin:localization_translationcache_changelist')
                })
        except Exception as e:
            logger.error(f"Error checking expired cache: {e}")
        
        # Check for exchange rates needing update
        try:
            needs_update = Currency.objects.filter(
                Q(exchange_rate_updated_at__isnull=True) |
                Q(exchange_rate_updated_at__lt=timezone.now() - timedelta(days=1))
            ).count()
            if needs_update > 0:
                alerts.append({
                    'type': 'warning',
                    'message': f'[MONEY] {needs_update} currencies need exchange rate update',
                    'link': reverse('admin:localization_currency_changelist')
                })
        except Exception as e:
            logger.error(f"Error checking exchange rates: {e}")
        
        return alerts
    
    def changelist_view(self, request, extra_context=None):
        """Add alerts to context"""
        extra_context = extra_context or {}
        extra_context['alerts'] = self.get_alerts(request)
        return super().changelist_view(request, extra_context)


# ======================== Batch Operations Queue ========================

class BatchOperationsMixin:
    """Mixin for batch operations with queue"""
    
    batch_operations = ['activate', 'deactivate', 'delete', 'export']
    
    def get_urls(self):
        """Add batch operation URLs"""
        urls = super().get_urls()
        custom_urls = [
            path('batch/', self.admin_site.admin_view(self.batch_view), name='batch'),
            path('batch-status/<str:batch_id>/', self.admin_site.admin_view(self.batch_status), name='batch-status'),
        ]
        return custom_urls + urls
    
    def batch_view(self, request):
        """Handle batch operations"""
        if request.method == 'POST':
            data = json.loads(request.body)
            operation = data.get('operation')
            ids = data.get('ids', [])
            params = data.get('params', {})
            
            if not ids:
                return JsonResponse({'error': 'No items selected'}, status=400)
            
            if operation not in self.batch_operations:
                return JsonResponse({'error': f'Invalid operation: {operation}'}, status=400)
            
            # Create batch task
            from .tasks import batch_operation_task
            task = batch_operation_task.delay(
                self.model.__name__,
                operation,
                ids,
                params,
                request.user.id
            )
            
            return JsonResponse({
                'batch_id': task.id,
                'status': 'queued',
                'message': f'Batch {operation} started with {len(ids)} items'
            })
        
        # GET request - show batch form
        context = {
            'operations': self.batch_operations,
            'model_name': self.model._meta.verbose_name_plural,
            'opts': self.model._meta,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/batch.html', context)
    
    def batch_status(self, request, batch_id):
        """Check batch operation status"""
        from celery.result import AsyncResult
        task = AsyncResult(batch_id)
        
        if task.ready():
            if task.successful():
                return JsonResponse({
                    'status': 'completed',
                    'result': task.result
                })
            else:
                return JsonResponse({
                    'status': 'failed',
                    'error': str(task.result)
                })
        
        return JsonResponse({
            'status': 'processing',
            'progress': task.info.get('progress', 0) if task.info else 0,
            'processed': task.info.get('processed', 0) if task.info else 0,
            'total': task.info.get('total', 0) if task.info else 0
        })
    
    class Media:
        js = ('admin/js/batch_operations.js',)
        css = {'all': ('admin/css/batch_operations.css',)}


# ======================== Base Admin Class with All Mixins ========================

class BaseModelAdmin(
    ChartMixin,
    BulkEditMixin,
    ImportExportMixin,
    ActivityTimelineMixin,
    RelatedObjectsMixin,
    AdvancedSearchMixin,
    NotificationMixin,
    BatchOperationsMixin,
    admin.ModelAdmin
):
    """Base admin class with all features"""
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css', 'admin/css/dashboard.css')
        }
        js = ('admin/js/custom_admin.js', 'admin/js/charts.js')


# ======================== Helper Functions for Display ========================

def colored_status(obj):
    """Show colored status badge"""
    if obj.is_active:
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">[OK] Active</span>'
        )
    return format_html(
        '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">[ERROR] Inactive</span>'
    )


def colored_default(obj):
    """Show colored default badge"""
    if obj.is_default:
        return format_html(
            '<span style="background-color: #ffc107; color: #212529; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">[STAR] Default</span>'
        )
    return format_html(
        '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">◯ Normal</span>'
    )


def action_buttons(obj):
    """Action buttons for edit, delete, etc."""
    edit_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
    delete_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_delete', args=[obj.pk])
    
    return format_html(
        '<a class="button" href="{}" style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; margin-right: 5px;">✏️ Edit</a>'
        '<a class="button" href="{}" style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none;">[DELETE] Delete</a>',
        edit_url, delete_url
    )


# ======================== Model Admins ========================

@admin.register(Language)
class LanguageAdmin(BaseModelAdmin):
    """Language admin with all features"""
    
    list_display = [
        'colored_code', 'colored_name', 'colored_native_name',
        'colored_status', 'colored_default', 'colored_rtl',
        'translation_count', 'related_objects_popup', 'action_buttons_display'
    ]
    
    list_filter = [
        ActiveFilter, DefaultFilter, RTLFilter,
    ]
    
    search_fields = ['code', 'name', 'name_native', 'locale_code']
    
    list_per_page = 25
    
    fieldsets = (
        (_('📋 Basic Information'), {
            'fields': ('code', 'name', 'name_native', 'locale_code'),
            'classes': ('wide',),
        }),
        (_('⚙️ Settings'), {
            'fields': ('is_active', 'is_default', 'is_rtl', 'flag_emoji'),
            'classes': ('wide',),
        }),
        (_('[STATS] Statistics'), {
            'fields': ('translation_stats',),
            'classes': ('wide',),
        }),
        (_('⏱️ Activity'), {
            'fields': ('activity_timeline',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'translation_stats', 'activity_timeline']
    
    bulk_edit_fields = ['is_active', 'is_default', 'is_rtl']
    batch_operations = ['activate', 'deactivate', 'export']
    
    def colored_code(self, obj):
        return format_html(
            '<span style="background-color: #6610f2; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">{}</span>',
            obj.code.upper()
        )
    colored_code.short_description = _('Code')
    colored_code.admin_order_field = 'code'
    
    def colored_name(self, obj):
        return format_html(
            '<span style="color: #007bff; font-weight: bold;">{}</span>',
            obj.name
        )
    colored_name.short_description = _('Name')
    colored_name.admin_order_field = 'name'
    
    def colored_native_name(self, obj):
        if obj.name_native:
            return format_html(
                '<span style="color: #6f42c1;">{}</span>',
                obj.name_native
            )
        return '-'
    colored_native_name.short_description = _('Native Name')
    
    def colored_status(self, obj):
        return colored_status(obj)
    colored_status.short_description = _('Status')
    colored_status.admin_order_field = 'is_active'
    
    def colored_default(self, obj):
        return colored_default(obj)
    colored_default.short_description = _('Default')
    colored_default.admin_order_field = 'is_default'
    
    def colored_rtl(self, obj):
        if obj.is_rtl:
            return format_html(
                '<span style="background-color: #17a2b8; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">🔁 RTL</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">➡️ LTR</span>'
        )
    colored_rtl.short_description = _('RTL')
    colored_rtl.admin_order_field = 'is_rtl'
    
    def translation_count(self, obj):
        count = Translation.objects.filter(language=obj, is_approved=True).count()
        if count > 0:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[NOTE] {}</span>',
                count
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[NOTE] 0</span>'
        )
    translation_count.short_description = _('Translations')
    
    def action_buttons_display(self, obj):
        return action_buttons(obj)
    action_buttons_display.short_description = _('Actions')
    
    def translation_stats(self, obj):
        """Show translation statistics"""
        total = Translation.objects.filter(language=obj).count()
        approved = Translation.objects.filter(language=obj, is_approved=True).count()
        pending = total - approved
        
        return format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<div><strong>Total:</strong> {} | <span style="color: #28a745;">[OK] Approved: {}</span> | <span style="color: #ffc107;">⏳ Pending: {}</span></div>'
            '<div style="margin-top: 10px; height: 10px; background-color: #e9ecef; border-radius: 5px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background-color: #28a745; float: left;"></div>'
            '<div style="width: {}%; height: 100%; background-color: #ffc107; float: left;"></div>'
            '</div>'
            '</div>',
            total, approved, pending,
            (approved/total*100) if total > 0 else 0,
            (pending/total*100) if total > 0 else 0
        )
    translation_stats.short_description = _('Translation Statistics')
    
    def get_chart_data(self, request):
        """Get chart data for language admin"""
        return {
            'translation_status': {
                'labels': ['Approved', 'Pending'],
                'data': [
                    Translation.objects.filter(is_approved=True).count(),
                    Translation.objects.filter(is_approved=False).count()
                ],
                'colors': ['#28a745', '#ffc107']
            }
        }


@admin.register(Country)
class CountryAdmin(BaseModelAdmin):
    """Country admin with all features"""
    
    list_display = [
        'colored_code', 'colored_name', 'colored_phone',
        'cities_count', 'colored_status', 'related_objects_popup',
        'action_buttons_display'
    ]
    
    list_filter = [ActiveFilter]
    
    search_fields = ['code', 'name', 'native_name', 'phone_code']
    
    list_per_page = 25
    
    fieldsets = (
        (_('📋 Basic Information'), {
            'fields': ('code', 'code_alpha3', 'name', 'native_name'),
            'classes': ('wide',),
        }),
        (_('📞 Contact Info'), {
            'fields': ('phone_code', 'phone_digits'),
            'classes': ('wide',),
        }),
        (_('🏳️ Flags'), {
            'fields': ('flag_emoji', 'flag_svg_url'),
            'classes': ('wide',),
        }),
        (_('⚙️ Settings'), {
            'fields': ('is_active', 'metadata'),
            'classes': ('wide',),
        }),
        (_('⏱️ Activity'), {
            'fields': ('activity_timeline',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'flag_preview', 'activity_timeline']
    
    bulk_edit_fields = ['is_active']
    batch_operations = ['activate', 'deactivate', 'export']
    
    def colored_code(self, obj):
        return format_html(
            '<span style="background-color: #fd7e14; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">{}</span>',
            obj.code
        )
    colored_code.short_description = _('Code')
    colored_code.admin_order_field = 'code'
    
    def colored_name(self, obj):
        if obj.flag_emoji:
            return format_html(
                '<span style="color: #007bff; font-weight: bold;">{} {}</span>',
                obj.flag_emoji, obj.name
            )
        return format_html(
            '<span style="color: #007bff; font-weight: bold;">{}</span>',
            obj.name
        )
    colored_name.short_description = _('Name')
    colored_name.admin_order_field = 'name'
    
    def colored_phone(self, obj):
        return format_html(
            '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 4px;">{} ({} digits)</span>',
            obj.phone_code, obj.phone_digits
        )
    colored_phone.short_description = _('Phone')
    
    def colored_status(self, obj):
        return colored_status(obj)
    colored_status.short_description = _('Status')
    colored_status.admin_order_field = 'is_active'
    
    def cities_count(self, obj):
        count = obj.cities.filter(is_active=True).count()
        if count > 0:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px;">🏙️ {}</span>',
                count
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 20px;">🏙️ 0</span>'
        )
    cities_count.short_description = _('Cities')
    
    def action_buttons_display(self, obj):
        return action_buttons(obj)
    action_buttons_display.short_description = _('Actions')
    
    def flag_preview(self, obj):
        if obj.flag_svg_url:
            return format_html(
                '<img src="{}" style="width: 50px; height: auto; border: 1px solid #ddd; border-radius: 5px; padding: 5px;" />',
                obj.flag_svg_url
            )
        return obj.flag_emoji or '-'
    flag_preview.short_description = _('Flag Preview')


@admin.register(Currency)
class CurrencyAdmin(BaseModelAdmin):
    """Currency admin with all features"""
    
    list_display = [
        'colored_code', 'colored_symbol', 'colored_name',
        'exchange_rate_display', 'colored_status', 'colored_default',
        'needs_update', 'related_objects_popup', 'action_buttons_display'
    ]
    
    list_filter = [ActiveFilter, DefaultFilter, ExchangeRateFilter]
    
    search_fields = ['code', 'name', 'symbol']
    
    list_per_page = 25
    
    fieldsets = (
        (_('📋 Basic Information'), {
            'fields': ('code', 'name', 'symbol', 'symbol_native'),
            'classes': ('wide',),
        }),
        (_('[MONEY] Exchange Rate'), {
            'fields': ('exchange_rate', 'exchange_rate_updated_at'),
            'classes': ('wide',),
        }),
        (_('⚙️ Settings'), {
            'fields': ('decimal_digits', 'is_active', 'is_default', 'metadata'),
            'classes': ('wide',),
        }),
        (_('[STATS] Examples'), {
            'fields': ('format_examples',),
            'classes': ('wide',),
        }),
        (_('⏱️ Activity'), {
            'fields': ('activity_timeline',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'format_examples', 
                       'exchange_rate_updated_at', 'activity_timeline']
    
    bulk_edit_fields = ['is_active', 'is_default', 'decimal_digits']
    batch_operations = ['activate', 'deactivate', 'update_rates', 'export']
    
    def colored_code(self, obj):
        colors = ['#6f42c1', '#fd7e14', '#20c997', '#e83e8c', '#28a745']
        color = colors[hash(obj.code) % len(colors)]
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">{}</span>',
            color, obj.code
        )
    colored_code.short_description = _('Code')
    colored_code.admin_order_field = 'code'
    
    def colored_symbol(self, obj):
        return format_html(
            '<span style="font-size: 18px; font-weight: bold; color: #28a745;">{}</span>',
            obj.symbol
        )
    colored_symbol.short_description = _('Symbol')
    
    def colored_name(self, obj):
        return format_html(
            '<span style="color: #007bff;">{}</span>',
            obj.name
        )
    colored_name.short_description = _('Name')
    
    def colored_status(self, obj):
        return colored_status(obj)
    colored_status.short_description = _('Status')
    colored_status.admin_order_field = 'is_active'
    
    def colored_default(self, obj):
        return colored_default(obj)
    colored_default.short_description = _('Default')
    colored_default.admin_order_field = 'is_default'
    
    def exchange_rate_display(self, obj):
        rate = float(obj.exchange_rate)
        if rate > 100:
            color = '#dc3545'
        elif rate > 10:
            color = '#fd7e14'
        else:
            color = '#28a745'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">{}</span>',
            color, f'{rate:.4f}'
        )
    exchange_rate_display.short_description = _('Exchange Rate')
    exchange_rate_display.admin_order_field = 'exchange_rate'
    
    def needs_update(self, obj):
        if obj.needs_exchange_update:
            return format_html(
                '<span style="background-color: #ffc107; color: #212529; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[WARN] Update Needed</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[OK] Updated</span>'
        )
    needs_update.short_description = _('Exchange Rate Status')
    
    def action_buttons_display(self, obj):
        return action_buttons(obj)
    action_buttons_display.short_description = _('Actions')
    
    def format_examples(self, obj):
        examples = [1, 100, 1000, 10000, 100000]
        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
        for amount in examples:
            formatted = obj.format_amount(amount)
            html += f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 3px solid #28a745;">{formatted}</div>'
        html += '</div>'
        return format_html(html)
    format_examples.short_description = _('Format Examples')


@admin.register(Timezone)
class TimezoneAdmin(BaseModelAdmin):
    """Timezone admin"""
    
    list_display = ['name', 'code', 'offset', 'is_dst', 'is_active']
    list_filter = [ActiveFilter, DSTFilter]
    search_fields = ['name', 'code']
    list_per_page = 50


@admin.register(City)
class CityAdmin(BaseModelAdmin):
    """City admin"""
    
    list_display = ['name', 'country', 'is_capital', 'is_active']
    list_filter = [ActiveFilter, CityCapitalFilter, 'country']
    search_fields = ['name', 'native_name', 'country__name']
    list_per_page = 25
    autocomplete_fields = ['country', 'timezone']


@admin.register(TranslationKey)
class TranslationKeyAdmin(BaseModelAdmin):
    """Translation Key admin"""
    
    list_display = ['key', 'category', 'is_plural', 'is_html']
    list_filter = ['category', 'is_plural', 'is_html']
    search_fields = ['key', 'description', 'category']
    list_per_page = 25


@admin.register(Translation)
class TranslationAdmin(BaseModelAdmin):
    """Translation admin with all features"""
    
    list_display = [
        'colored_key', 'colored_language', 'value_short',
        'colored_approved', 'colored_source', 'modified_info',
        'related_objects_popup', 'action_buttons_display'
    ]
    
    list_filter = [
        ('language', admin.RelatedFieldListFilter),
        ApprovedFilter,
        TranslationSourceFilter,
        ('approved_by', admin.RelatedFieldListFilter),
    ]
    
    search_fields = ['key__key', 'value', 'language__name']
    
    list_per_page = 25
    
    autocomplete_fields = ['key', 'language', 'approved_by']
    
    fieldsets = (
        (_('[KEY] Key & Language'), {
            'fields': ('key', 'language'),
            'classes': ('wide',),
        }),
        (_('[NOTE] Translation'), {
            'fields': ('value', 'value_plural'),
            'classes': ('wide',),
        }),
        (_('[OK] Approval'), {
            'fields': ('is_approved', 'approved_by', 'approved_at'),
            'classes': ('wide',),
        }),
        (_('[INFO] Source Info'), {
            'fields': ('source', 'metadata'),
            'classes': ('wide',),
        }),
        (_('⏱️ Activity'), {
            'fields': ('activity_timeline',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'activity_timeline']
    
    bulk_edit_fields = ['is_approved', 'source']
    batch_operations = ['approve', 'unapprove', 'export']
    
    actions = ['approve_selected', 'unapprove_selected', 'export_as_json']
    
    def colored_key(self, obj):
        return format_html(
            '<span style="background-color: #6f42c1; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-family: monospace;">{}</span>',
            obj.key.key if obj.key else '-'
        )
    colored_key.short_description = _('Key')
    
    def colored_language(self, obj):
        if obj.language and obj.language.flag_emoji:
            return format_html(
                '{} <span style="color: #6c757d;">({})</span>',
                obj.language.flag_emoji, obj.language.code
            )
        return obj.language.code if obj.language else '-'
    colored_language.short_description = _('Language')
    
    def value_short(self, obj):
        if len(obj.value) > 50:
            return obj.value[:50] + '...'
        return obj.value
    value_short.short_description = _('Translation')
    
    def colored_approved(self, obj):
        if obj.is_approved:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[OK] Approved</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: #212529; padding: 3px 10px; border-radius: 20px; font-size: 12px;">⏳ Pending</span>'
        )
    colored_approved.short_description = _('Status')
    
    def colored_source(self, obj):
        source_colors = {
            'manual': '#28a745',
            'auto': '#17a2b8',
            'import': '#ffc107',
            'api': '#6f42c1',
        }
        color = source_colors.get(obj.source, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color, obj.get_source_display()
        )
    colored_source.short_description = _('Source')
    
    def modified_info(self, obj):
        if obj.updated_at:
            time_ago = timezone.now() - obj.updated_at
            if time_ago.days > 0:
                return f'{obj.updated_at.strftime("%Y-%m-%d")} ({time_ago.days}d ago)'
            elif time_ago.seconds > 3600:
                hours = time_ago.seconds // 3600
                return f'{obj.updated_at.strftime("%H:%M")} ({hours}h ago)'
            return obj.updated_at.strftime('%H:%M')
        return '-'
    modified_info.short_description = _('Updated')
    
    def action_buttons_display(self, obj):
        return action_buttons(obj)
    action_buttons_display.short_description = _('Actions')
    
    def approve_selected(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            is_approved=True,
            approved_at=timezone.now(),
            approved_by=request.user if request.user.is_authenticated else None
        )
        self.message_user(request, _(f'[OK] {updated} translations approved.'), level=messages.SUCCESS)
    approve_selected.short_description = _('[OK] Approve selected')
    
    def unapprove_selected(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, _(f'⏳ {updated} translations unapproved.'), level=messages.WARNING)
    unapprove_selected.short_description = _('⏳ Unapprove selected')
    
    def export_as_json(self, request, queryset):
        """Export selected translations as JSON"""
        data = []
        for obj in queryset:
            data.append({
                'key': obj.key.key if obj.key else None,
                'language': obj.language.code if obj.language else None,
                'value': obj.value,
                'value_plural': obj.value_plural,
                'is_approved': obj.is_approved,
                'source': obj.source,
            })
        
        response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = 'attachment; filename="translations_export.json"'
        return response
    export_as_json.short_description = _('📥 Export as JSON')
    
    def get_chart_data(self, request):
        """Get chart data for translation admin"""
        languages = Language.objects.filter(is_active=True)[:5]
        return {
            'translations_by_language': {
                'labels': [lang.code for lang in languages],
                'data': [
                    Translation.objects.filter(language=lang, is_approved=True).count()
                    for lang in languages
                ],
                'colors': ['#28a745', '#17a2b8', '#ffc107', '#dc3545', '#6610f2']
            }
        }


@admin.register(TranslationCache)
class TranslationCacheAdmin(BaseModelAdmin):
    """Translation Cache admin (read-only)"""
    
    list_display = ['language_code', 'cache_key', 'hits', 'expires_at']
    list_filter = ['language_code']
    search_fields = ['language_code', 'cache_key']
    readonly_fields = ['language_code', 'cache_key', 'cache_data', 'hits', 'expires_at', 'created_at', 'updated_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserLanguagePreference)
class UserLanguagePreferenceAdmin(BaseModelAdmin):
    """User Language Preference admin"""
    
    list_display = ['user', 'primary_language', 'ui_language', 'auto_translate']
    list_filter = ['auto_translate', 'primary_language', 'ui_language']
    search_fields = ['user__email', 'user__username']
    autocomplete_fields = ['user', 'primary_language', 'ui_language', 'content_language']
    filter_horizontal = ['preferred_languages']


@admin.register(MissingTranslation)
class MissingTranslationAdmin(BaseModelAdmin):
    """Missing Translation admin with all features"""
    
    list_display = [
        'colored_key', 'colored_language', 'request_count',
        'first_seen', 'last_seen', 'colored_resolved',
        'related_objects_popup', 'action_buttons_display'
    ]
    
    list_filter = [
        MissingTranslationResolvedFilter,
        ('language', admin.RelatedFieldListFilter),
        ('resolved_by', admin.RelatedFieldListFilter),
    ]
    
    search_fields = ['key', 'context', 'request_path']
    
    list_per_page = 25
    
    readonly_fields = ['created_at', 'resolved_at', 'activity_timeline']
    
    fieldsets = (
        (_('[KEY] Missing Key'), {
            'fields': ('key', 'language', 'context'),
            'classes': ('wide',),
        }),
        (_('🌐 Request Info'), {
            'fields': ('request_path', 'user_agent', 'ip_address', 'user'),
            'classes': ('wide',),
        }),
        (_('[OK] Resolution'), {
            'fields': ('resolved', 'resolved_at', 'resolved_by'),
            'classes': ('wide',),
        }),
        (_('⏱️ Activity'), {
            'fields': ('activity_timeline',),
            'classes': ('wide', 'collapse'),
        }),
    )
    
    bulk_edit_fields = ['resolved']
    batch_operations = ['mark_resolved', 'export']
    
    actions = ['mark_as_resolved', 'export_as_json']
    
    def colored_key(self, obj):
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-family: monospace;">{}</span>',
            obj.key
        )
    colored_key.short_description = _('Missing Key')
    
    def colored_language(self, obj):
        if obj.language and obj.language.flag_emoji:
            return f"{obj.language.flag_emoji} {obj.language.code}"
        return obj.language.code if obj.language else '-'
    colored_language.short_description = _('Language')
    
    def request_count(self, obj):
        count = MissingTranslation.objects.filter(
            key=obj.key,
            language=obj.language
        ).count()
        
        if count > 10:
            color = '#dc3545'
        elif count > 5:
            color = '#fd7e14'
        else:
            color = '#28a745'
            
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{} times</span>',
            color, count
        )
    request_count.short_description = _('Frequency')
    
    def first_seen(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M') if obj.created_at else '-'
    first_seen.short_description = _('First Seen')
    
    def last_seen(self, obj):
        last = MissingTranslation.objects.filter(
            key=obj.key,
            language=obj.language
        ).order_by('-created_at').first()
        if last and last.created_at:
            time_ago = timezone.now() - last.created_at
            if time_ago.days > 0:
                return f'{last.created_at.strftime("%Y-%m-%d")} ({time_ago.days}d ago)'
            return last.created_at.strftime('%H:%M')
        return '-'
    last_seen.short_description = _('Last Seen')
    
    def colored_resolved(self, obj):
        if obj.resolved:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[OK] Resolved</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px;">[ERROR] Unresolved</span>'
        )
    colored_resolved.short_description = _('Status')
    
    def action_buttons_display(self, obj):
        return action_buttons(obj)
    action_buttons_display.short_description = _('Actions')
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user if request.user.is_authenticated else None
        )
        self.message_user(request, _(f'[OK] {updated} missing translations marked as resolved.'), level=messages.SUCCESS)
    mark_as_resolved.short_description = _('[OK] Mark as resolved')
    
    def export_as_json(self, request, queryset):
        """Export selected missing translations as JSON"""
        data = []
        for obj in queryset:
            data.append({
                'key': obj.key,
                'language': obj.language.code if obj.language else None,
                'context': obj.context,
                'resolved': obj.resolved,
                'created_at': obj.created_at.isoformat() if obj.created_at else None,
            })
        
        response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = 'attachment; filename="missing_translations_export.json"'
        return response
    export_as_json.short_description = _('📥 Export as JSON')
    
    def get_chart_data(self, request):
        """Get chart data for missing translation admin"""
        languages = Language.objects.filter(is_active=True)[:5]
        return {
            'missing_by_language': {
                'labels': [lang.code for lang in languages],
                'data': [
                    MissingTranslation.objects.filter(language=lang, resolved=False).count()
                    for lang in languages
                ],
                'colors': ['#dc3545', '#fd7e14', '#ffc107', '#17a2b8', '#6f42c1']
            }
        }


# ======================== Custom Admin Dashboard ========================

class LocalizationDashboard(admin.AdminSite):
    """Custom admin dashboard with all new features"""
    
    site_header = _('🌐 Localization Management System')
    site_title = _('Localization Admin')
    index_title = _('Dashboard')
    
    def get_app_list(self, request):
        """Reorder app list to show localization first"""
        app_list = super().get_app_list(request)
        
        for i, app in enumerate(app_list):
            if app['app_label'] == 'localization':
                localization_app = app_list.pop(i)
                app_list.insert(0, localization_app)
                break
        
        return app_list
    
    def index(self, request, extra_context=None):
        """Custom index dashboard with widgets"""
        extra_context = extra_context or {}
        
        # Get statistics
        total_languages = Language.objects.count()
        active_languages = Language.objects.filter(is_active=True).count()
        total_translations = Translation.objects.count()
        approved_translations = Translation.objects.filter(is_approved=True).count()
        total_keys = TranslationKey.objects.count()
        missing_translations = MissingTranslation.objects.filter(resolved=False).count()
        
        # Add metric cards
        extra_context['metrics'] = [
            DashboardWidget.metric_card(
                'Languages', active_languages, '🌐', '#28a745',
                f'{total_languages} total', reverse('admin:localization_language_changelist')
            ),
            DashboardWidget.metric_card(
                'Translations', approved_translations, '[NOTE]', '#17a2b8',
                f'{total_translations} total', reverse('admin:localization_translation_changelist')
            ),
            DashboardWidget.metric_card(
                'Keys', total_keys, '[KEY]', '#ffc107',
                f'{TranslationKey.objects.filter(is_plural=True).count()} plural',
                reverse('admin:localization_translationkey_changelist')
            ),
            DashboardWidget.metric_card(
                'Missing', missing_translations, '[ERROR]', '#dc3545',
                'unresolved', reverse('admin:localization_missingtranslation_changelist')
            ),
        ]
        
        # Add progress cards
        if total_keys > 0:
            extra_context['progress'] = [
                DashboardWidget.progress_card(
                    'English Coverage',
                    Translation.objects.filter(language__code='en', is_approved=True).count(),
                    total_keys, '🇬🇧', '#28a745',
                    reverse('admin:localization_translation_changelist') + '?language__code__exact=en'
                ),
                DashboardWidget.progress_card(
                    'Bengali Coverage',
                    Translation.objects.filter(language__code='bn', is_approved=True).count(),
                    total_keys, '🇧🇩', '#17a2b8',
                    reverse('admin:localization_translation_changelist') + '?language__code__exact=bn'
                ),
            ]
        
        # Add charts
        extra_context['charts'] = {
            'translation_status': {
                'labels': ['Approved', 'Pending', 'Missing'],
                'data': [
                    approved_translations,
                    total_translations - approved_translations,
                    missing_translations
                ],
                'colors': ['#28a745', '#ffc107', '#dc3545']
            },
            'languages_by_rtl': {
                'labels': ['LTR', 'RTL'],
                'data': [
                    Language.objects.filter(is_rtl=False).count(),
                    Language.objects.filter(is_rtl=True).count()
                ],
                'colors': ['#17a2b8', '#6610f2']
            }
        }
        
        # Add alerts
        notification_mixin = NotificationMixin()
        extra_context['alerts'] = notification_mixin.get_alerts(request)
        
        # Add Chart.js
        extra_context['media'] = self.media + format_html(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )
        
        return super().index(request, extra_context)
    
    class Media:
        css = {
            'all': ('admin/css/dashboard.css',)
        }
        js = ('admin/js/dashboard.js',)


# ======================== Register with Default Admin Site ========================

# Register all models with default admin site
# (No need for custom admin_site variable)


# ==================== FORCE REGISTER ALL MODELS ====================
from django.contrib import admin
from .models import (
    City, Country, Currency, Language, MissingTranslation,
    Timezone, Translation, TranslationCache, TranslationKey,
    UserLanguagePreference
)

# Try to import all admin classes
try:
    from .admin import (
        CountryAdmin, CityAdmin, CurrencyAdmin, LanguageAdmin,
        TimezoneAdmin, TranslationKeyAdmin, TranslationAdmin,
        TranslationCacheAdmin, MissingTranslationAdmin,
        UserLanguagePreferenceAdmin
    )
    
    models_to_register = [
        (Country, CountryAdmin),
        (City, CityAdmin),
        (Currency, CurrencyAdmin),
        (Language, LanguageAdmin),
        (Timezone, TimezoneAdmin),
        (TranslationKey, TranslationKeyAdmin),
        (Translation, TranslationAdmin),
        (TranslationCache, TranslationCacheAdmin),
        (MissingTranslation, MissingTranslationAdmin),
        (UserLanguagePreference, UserLanguagePreferenceAdmin),
    ]
    
    registered = 0
    for model, admin_class in models_to_register:
        if not admin.site.is_registered(model):
            admin.site.register(model, admin_class)
            registered += 1
            print(f"[OK] Registered: {model.__name__}")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} localization models registered!")
    else:
        print("[OK] All localization models already registered")
        
except Exception as e:
    print(f"[ERROR] Error registering models: {e}")