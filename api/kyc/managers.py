# kyc/managers.py  ── WORLD #1
from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Avg


class KYCQuerySet(models.QuerySet):

    def pending(self):       return self.filter(status='pending')
    def verified(self):      return self.filter(status='verified')
    def rejected(self):      return self.filter(status='rejected')
    def not_submitted(self): return self.filter(status='not_submitted')
    def expired(self):       return self.filter(status='expired')
    def active(self):        return self.filter(status__in=['pending','submitted','under_review'])
    def final(self):         return self.filter(status__in=['verified','rejected','expired'])

    def high_risk(self, threshold=60):  return self.filter(risk_score__gt=threshold)
    def low_risk(self,  threshold=30):  return self.filter(risk_score__lte=threshold)
    def flagged_duplicate(self):         return self.filter(is_duplicate=True)

    def by_document_type(self, doc_type): return self.filter(document_type=doc_type)

    def submitted_today(self):
        return self.filter(created_at__date=timezone.now().date())

    def submitted_this_week(self):
        return self.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7))

    def expiring_soon(self, days=30):
        deadline = timezone.now() + timezone.timedelta(days=days)
        return self.filter(status='verified', expires_at__lte=deadline, expires_at__gte=timezone.now())

    def already_expired(self):
        return self.filter(status='verified', expires_at__lt=timezone.now())

    def search(self, query: str):
        if not query: return self
        return self.filter(
            Q(full_name__icontains=query) | Q(phone_number__icontains=query) |
            Q(document_number__icontains=query) | Q(payment_number__icontains=query) |
            Q(user__username__icontains=query) | Q(user__email__icontains=query)
        )

    def by_tenant(self, tenant):
        return self if tenant is None else self.filter(tenant=tenant)

    def with_risk_level(self):
        return self.annotate(
            risk_level=models.Case(
                models.When(risk_score__lte=30, then=models.Value('low')),
                models.When(risk_score__lte=60, then=models.Value('medium')),
                models.When(risk_score__lte=80, then=models.Value('high')),
                default=models.Value('critical'),
                output_field=models.CharField(),
            )
        )

    def status_counts(self) -> dict:
        counts = self.values('status').annotate(count=Count('id'))
        return {item['status']: item['count'] for item in counts}

    def avg_risk_score(self) -> float:
        result = self.aggregate(avg=Avg('risk_score'))
        return round(result['avg'] or 0.0, 2)

    def mark_expired(self):
        return self.filter(status='verified', expires_at__lt=timezone.now()).update(status='expired')

    def bulk_verify(self, reviewed_by=None):
        now = timezone.now()
        return self.filter(status='pending').update(
            status='verified', reviewed_by=reviewed_by, reviewed_at=now, verified_at=now,
        )

    def bulk_reject(self, reason='Bulk rejected', reviewed_by=None):
        return self.filter(status='pending').update(
            status='rejected', rejection_reason=reason,
            reviewed_by=reviewed_by, reviewed_at=timezone.now(),
        )


class KYCManager(models.Manager):

    def get_queryset(self): return KYCQuerySet(self.model, using=self._db)

    def pending(self):       return self.get_queryset().pending()
    def verified(self):      return self.get_queryset().verified()
    def rejected(self):      return self.get_queryset().rejected()
    def high_risk(self, t=60): return self.get_queryset().high_risk(t)

    def for_user(self, user):     return self.get_queryset().filter(user=user)
    def for_tenant(self, tenant): return self.get_queryset().by_tenant(tenant)
    def search(self, query):      return self.get_queryset().search(query)

    def dashboard_stats(self) -> dict:
        qs    = self.get_queryset()
        today = timezone.now().date()
        return qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            verified=Count('id', filter=Q(status='verified')),
            rejected=Count('id', filter=Q(status='rejected')),
            not_submitted=Count('id', filter=Q(status='not_submitted')),
            expired=Count('id', filter=Q(status='expired')),
            high_risk=Count('id', filter=Q(risk_score__gt=60)),
            duplicates=Count('id', filter=Q(is_duplicate=True)),
            submitted_today=Count('id', filter=Q(created_at__date=today)),
        )


class KYCSubmissionQuerySet(models.QuerySet):
    def submitted(self): return self.filter(status='submitted')
    def pending(self):   return self.filter(status='pending')
    def verified(self):  return self.filter(status='verified')
    def rejected(self):  return self.filter(status='rejected')
    def for_user(self, user): return self.filter(user=user)
    def active(self):    return self.filter(status__in=['submitted','pending'])

    def latest_for_user(self, user):
        return self.filter(user=user).order_by('-submitted_at', '-created_at').first()

    def search(self, query):
        if not query: return self
        return self.filter(
            Q(document_number__icontains=query) | Q(user__username__icontains=query) | Q(user__email__icontains=query)
        )

    def liveness_passed(self): return self.filter(face_liveness_check='success')
    def liveness_failed(self): return self.filter(face_liveness_check='failure')
    def submitted_today(self): return self.filter(created_at__date=timezone.now().date())


class KYCSubmissionManager(models.Manager):
    def get_queryset(self): return KYCSubmissionQuerySet(self.model, using=self._db)

    def for_user(self, user):   return self.get_queryset().for_user(user)
    def verified(self):          return self.get_queryset().verified()
    def pending(self):           return self.get_queryset().pending()
    def latest_for_user(self, user): return self.get_queryset().latest_for_user(user)


class KYCVerificationLogQuerySet(models.QuerySet):
    def for_kyc(self, kyc):          return self.filter(kyc=kyc)
    def for_tenant(self, tenant):    return self.filter(tenant=tenant)
    def by_action(self, action):     return self.filter(action=action)
    def admin_actions(self):         return self.filter(action__in=['approved','rejected','reset','edited','note_added','bulk_action'])
    def system_actions(self):        return self.filter(action__in=['ocr_extracted','risk_scored','expired','duplicate_found'])
    def recent(self, limit=10):      return self.order_by('-created_at')[:limit]


class KYCVerificationLogManager(models.Manager):
    def get_queryset(self): return KYCVerificationLogQuerySet(self.model, using=self._db)

    def for_kyc(self, kyc):       return self.get_queryset().for_kyc(kyc)
    def for_tenant(self, tenant): return self.get_queryset().for_tenant(tenant)

    def create_log(self, kyc, action, details, performed_by=None, metadata=None, tenant=None):
        return self.create(
            kyc=kyc, action=action, performed_by=performed_by,
            details=details, metadata=metadata or {},
            tenant=tenant or getattr(kyc, 'tenant', None),
        )
