"""User Risk Profile — model helpers and advanced queries."""
from django.db import models
from django.db.models import Count, Avg


class UserRiskProfileManager(models.Manager):
    def high_risk(self, tenant=None, threshold=61):
        qs = self.filter(overall_risk_score__gte=threshold)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-overall_risk_score')

    def under_review(self, tenant=None):
        qs = self.filter(is_under_review=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def vpn_users(self, tenant=None):
        qs = self.filter(vpn_usage_detected=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def multi_account_users(self, tenant=None):
        qs = self.filter(multi_account_detected=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def distribution(self, tenant=None):
        qs = self.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.values('risk_level').annotate(count=Count('id')))

    def get_or_create_profile(self, user, tenant=None):
        profile, created = self.get_or_create(
            user=user,
            defaults={'tenant': tenant}
        )
        return profile, created
