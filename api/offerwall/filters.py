"""
api/offerwall/filters.py

DRF Filter backends for offerwall module.
Provides 6 filter strategies for queryable endpoints:
  1. OfferFilterBackend — filter offers by category, type, platform, status
  2. ProviderFilterBackend — filter providers by type, status
  3. ConversionFilterBackend — filter conversions by status, user, date range
  4. OfferClickFilterBackend — filter clicks by offer, user, date range
  5. SearchFilterBackend — search offers/conversions by title/description
  6. DateRangeFilterBackend — filter by created_at, approved_at date ranges
"""
from datetime import datetime
from django.utils.timezone import make_aware

from rest_framework.filters import BaseFilterBackend, SearchFilter, OrderingFilter
from django.db.models import Q


class OfferFilterBackend(BaseFilterBackend):
    """
    Filter offers by multiple criteria:
    - category: offer category slug
    - offer_type: type of offer (app_install, survey, etc)
    - platform: target platform (ios, android, web, etc)
    - status: offer status (active, paused, expired, etc)
    - provider: provider UUID
    - featured: boolean (true/false)
    - min_payout: minimum payout amount
    - max_payout: maximum payout amount
    
    Usage: ?category=games&offer_type=survey&platform=android&status=active
    """
    
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        
        if category := params.get('category'):
            queryset = queryset.filter(category__slug=category)
        
        if offer_type := params.get('offer_type'):
            queryset = queryset.filter(offer_type=offer_type)
        
        if platform := params.get('platform'):
            queryset = queryset.filter(
                Q(platform='all') | Q(platform=platform)
            )
        
        if status := params.get('status'):
            queryset = queryset.filter(status=status)
        
        if provider := params.get('provider'):
            queryset = queryset.filter(provider__id=provider)
        
        if featured := params.get('featured', '').lower():
            if featured == 'true':
                queryset = queryset.filter(is_featured=True)
            elif featured == 'false':
                queryset = queryset.filter(is_featured=False)
        
        if min_payout := params.get('min_payout'):
            try:
                queryset = queryset.filter(payout__gte=float(min_payout))
            except (ValueError, TypeError):
                pass
        
        if max_payout := params.get('max_payout'):
            try:
                queryset = queryset.filter(payout__lte=float(max_payout))
            except (ValueError, TypeError):
                pass
        
        return queryset


class ProviderFilterBackend(BaseFilterBackend):
    """
    Filter providers by:
    - provider_type: type of provider (tapjoy, adgem, adgate, etc)
    - status: provider status (active, inactive, testing, suspended)
    - name: provider name (partial match)
    
    Usage: ?provider_type=tapjoy&status=active
    """
    
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        
        if provider_type := params.get('provider_type'):
            queryset = queryset.filter(provider_type=provider_type)
        
        if status := params.get('status'):
            queryset = queryset.filter(status=status)
        
        if name := params.get('name'):
            queryset = queryset.filter(name__icontains=name)
        
        return queryset


class ConversionFilterBackend(BaseFilterBackend):
    """
    Filter conversions by:
    - status: conversion status (pending, approved, rejected, chargeback)
    - user_id: filter by user
    - offer_id: filter by offer
    - date_from: conversions from this date (YYYY-MM-DD)
    - date_to: conversions until this date (YYYY-MM-DD)
    - is_verified: boolean (true/false)
    
    Usage: ?status=approved&user_id=123&date_from=2026-01-01&date_to=2026-06-11
    """
    
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        
        if status := params.get('status'):
            queryset = queryset.filter(status=status)
        
        if user_id := params.get('user_id'):
            queryset = queryset.filter(user__id=user_id)
        
        if offer_id := params.get('offer_id'):
            queryset = queryset.filter(offer__id=offer_id)
        
        if date_from := params.get('date_from'):
            try:
                dt = make_aware(datetime.strptime(date_from, "%Y-%m-%d"))
                queryset = queryset.filter(converted_at__gte=dt)
            except ValueError:
                pass
        
        if date_to := params.get('date_to'):
            try:
                dt = make_aware(datetime.strptime(date_to, "%Y-%m-%d"))
                queryset = queryset.filter(converted_at__lte=dt)
            except ValueError:
                pass
        
        if is_verified := params.get('is_verified', '').lower():
            if is_verified == 'true':
                queryset = queryset.filter(is_verified=True)
            elif is_verified == 'false':
                queryset = queryset.filter(is_verified=False)
        
        return queryset


class OfferClickFilterBackend(BaseFilterBackend):
    """
    Filter offer clicks by:
    - offer_id: filter by offer UUID
    - user_id: filter by user
    - is_converted: boolean (true/false) - was it converted?
    - date_from: clicks from this date (YYYY-MM-DD)
    - date_to: clicks until this date (YYYY-MM-DD)
    
    Usage: ?offer_id=<uuid>&user_id=123&is_converted=true
    """
    
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        
        if offer_id := params.get('offer_id'):
            queryset = queryset.filter(offer__id=offer_id)
        
        if user_id := params.get('user_id'):
            queryset = queryset.filter(user__id=user_id)
        
        if is_converted := params.get('is_converted', '').lower():
            if is_converted == 'true':
                queryset = queryset.filter(is_converted=True)
            elif is_converted == 'false':
                queryset = queryset.filter(is_converted=False)
        
        if date_from := params.get('date_from'):
            try:
                dt = make_aware(datetime.strptime(date_from, "%Y-%m-%d"))
                queryset = queryset.filter(clicked_at__gte=dt)
            except ValueError:
                pass
        
        if date_to := params.get('date_to'):
            try:
                dt = make_aware(datetime.strptime(date_to, "%Y-%m-%d"))
                queryset = queryset.filter(clicked_at__lte=dt)
            except ValueError:
                pass
        
        return queryset


class DateRangeFilterBackend(BaseFilterBackend):
    """
    Generic date range filter for any model with created_at/updated_at.
    - date_field: which field to filter (created_at, updated_at, approved_at, etc)
    - date_from: from this date (YYYY-MM-DD)
    - date_to: to this date (YYYY-MM-DD)
    
    Usage: ?date_field=approved_at&date_from=2026-06-01&date_to=2026-06-11
    """
    
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        
        date_field = params.get('date_field', 'created_at')
        
        if date_from := params.get('date_from'):
            try:
                dt = make_aware(datetime.strptime(date_from, "%Y-%m-%d"))
                queryset = queryset.filter(**{f'{date_field}__gte': dt})
            except ValueError:
                pass
        
        if date_to := params.get('date_to'):
            try:
                dt = make_aware(datetime.strptime(date_to, "%Y-%m-%d"))
                queryset = queryset.filter(**{f'{date_field}__lte': dt})
            except ValueError:
                pass
        
        return queryset
