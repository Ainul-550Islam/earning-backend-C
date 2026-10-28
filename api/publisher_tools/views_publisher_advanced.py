# publisher_tools/views_publisher_advanced.py  (DRY refactored)
"""
Publisher Advanced ViewSet — DRY refactored।

পুরনো pattern (এই file-এ 19 বার repeated):
──────────────────────────────────────────
    @action(...)
    def store(self, request):
        publisher = self._get_publisher()           ← 19×
        try:
            from .publisher_management.publisher_store import PublisherStore
            store = PublisherStore.objects.filter(publisher=publisher).first()
            if not store:
                return self.success_response(data={'store': None})
            return self.success_response(data={...})
        except (ImportError, Exception) as e:       ← 19×
            return self.error_response(str(e), status_code=503)

নতুন pattern (PublisherViewMixin + handle_errors):
──────────────────────────────────────────────────
    @action(...)
    def store(self, request):
        pub = self.publisher                        ← property (cached)
        with self.handle_errors() as guard:
            from .publisher_management.publisher_store import PublisherStore
            store = PublisherStore.objects.filter(publisher=pub).first()
            if not store:
                return self.ok({'store': None, 'message': 'No store profile.'})
            return self.ok({...})
        return guard.response
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ViewSet

from .mixins import PublisherViewMixin
from .permissions import IsPublisher


class PublisherAdvancedViewSet(PublisherViewMixin, ViewSet):
    """
    Publisher Management Advanced API — using PublisherViewMixin।
    _get_publisher() / handle_errors() / get_subfolder_object() all inherited।
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ══════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='subscription')
    def subscription(self, request):
        pub = self.publisher
        sub = self.get_subfolder_object(
            'publisher_management.publisher_subscription',
            'PublisherSubscription',
            publisher=pub, status='active',
        )
        if not sub:
            return self.ok({'plan': None, 'status': 'no_subscription',
                            'message': 'No active subscription found.'})
        plan = getattr(sub, 'plan', None)
        return self.ok({
            'subscription_id': sub.pk,
            'plan_name':       getattr(plan, 'name', None),
            'plan_tier':       getattr(plan, 'tier', None),
            'status':          getattr(sub, 'status', ''),
            'started_at':      str(sub.created_at),
            'expires_at':      str(getattr(sub, 'expires_at', '')),
            'limits': {
                'max_sites':    getattr(plan, 'max_sites', 0) if plan else 0,
                'max_apps':     getattr(plan, 'max_apps', 0) if plan else 0,
                'max_ad_units': getattr(plan, 'max_ad_units', 0) if plan else 0,
            },
            'can_add_site': sub.can_add_site() if hasattr(sub, 'can_add_site') else True,
            'can_add_app':  sub.can_add_app()  if hasattr(sub, 'can_add_app')  else True,
        })

    @action(detail=False, methods=['get'], url_path='subscription-plans')
    def subscription_plans(self, request):
        model = self.get_subfolder_model(
            'publisher_management.publisher_subscription', 'SubscriptionPlan'
        )
        if model is None:
            return self.ok({'plans': [], 'count': 0})
        plans = model.objects.filter(is_active=True).order_by('monthly_price')
        return self.ok({'plans': [
            {
                'pk':            p.pk,
                'name':          p.name,
                'tier':          getattr(p, 'tier', ''),
                'monthly_price': str(getattr(p, 'monthly_price', 0)),
                'annual_price':  str(getattr(p, 'annual_price', 0)),
                'max_sites':     getattr(p, 'max_sites', 0),
                'max_apps':      getattr(p, 'max_apps', 0),
                'max_ad_units':  getattr(p, 'max_ad_units', 0),
                'features':      getattr(p, 'features', []),
                'discount_pct':  p.get_discount_pct() if hasattr(p, 'get_discount_pct') else 0,
            }
            for p in plans
        ], 'count': plans.count()})

    @action(detail=False, methods=['post'], url_path='can-add-site')
    def can_add_site(self, request):
        pub = self.publisher
        sub = self.get_subfolder_object(
            'publisher_management.publisher_subscription',
            'PublisherSubscription',
            publisher=pub, status='active',
        )
        if not sub:
            return self.ok({'allowed': True, 'reason': 'No subscription limit'})
        return self.ok({
            'allowed':       sub.can_add_site() if hasattr(sub, 'can_add_site') else True,
            'current_sites': pub.sites.count(),
            'max_sites':     getattr(getattr(sub, 'plan', None), 'max_sites', '∞'),
        })

    @action(detail=False, methods=['get'], url_path='subscription-history')
    def subscription_history(self, request):
        pub     = self.publisher
        history = self.get_subfolder_queryset(
            'publisher_management.publisher_subscription',
            'SubscriptionPaymentHistory',
            publisher=pub,
        )
        if history is None:
            return self.ok({'history': [], 'count': 0})
        history = history.order_by('-created_at')[:50]
        return self.ok({'history': [
            {'pk': h.pk, 'amount': str(getattr(h, 'amount', 0)),
             'status': getattr(h, 'status', ''), 'date': str(h.created_at)}
            for h in history
        ], 'count': history.count()})

    # ══════════════════════════════════════════════════════════════════════════
    # KYC
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='kyc-status')
    def kyc_status(self, request):
        pub = self.publisher
        kyc = self.get_subfolder_object(
            'publisher_management.publisher_kyc', 'PublisherKYC',
            publisher=pub,
        )
        if not kyc:
            return self.ok({'status': 'not_submitted', 'can_submit': True,
                            'message': 'KYC not yet submitted.'})
        return self.ok({
            'kyc_id':           kyc.pk,
            'status':           getattr(kyc, 'status', ''),
            'is_approved':      kyc.is_approved()  if hasattr(kyc, 'is_approved')  else False,
            'is_expired':       kyc.is_expired()   if hasattr(kyc, 'is_expired')   else False,
            'can_submit':       kyc.can_submit()   if hasattr(kyc, 'can_submit')   else False,
            'submitted_at':     str(getattr(kyc, 'submitted_at', '')),
            'reviewed_at':      str(getattr(kyc, 'reviewed_at', '')),
            'expires_at':       str(getattr(kyc, 'expires_at', '')),
            'rejection_reason': getattr(kyc, 'rejection_reason', ''),
        })

    @action(detail=False, methods=['post'], url_path='kyc-submit')
    def kyc_submit(self, request):
        pub  = self.publisher
        data = request.data
        required = ['kyc_type', 'full_name', 'id_type', 'id_number', 'country']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return self._build_error(f'Missing fields: {", ".join(missing)}', 400)
        with self.handle_errors() as guard:
            from .publisher_management.publisher_kyc import PublisherKYC, KYCDocument
            existing = PublisherKYC.objects.filter(publisher=pub).first()
            if existing and not (existing.can_submit() if hasattr(existing, 'can_submit') else True):
                return self._build_error('KYC cannot be resubmitted at this time.', 400)
            if existing:
                for field in ['kyc_type', 'full_name', 'date_of_birth', 'nationality',
                              'id_type', 'id_number', 'address', 'city', 'country', 'postal_code']:
                    if data.get(field) is not None:
                        setattr(existing, field, data[field])
                existing.status = 'pending'
                existing.save()
                kyc = existing
            else:
                kyc = PublisherKYC(publisher=pub, status='pending')
                for field in ['kyc_type', 'full_name', 'date_of_birth', 'nationality',
                              'id_type', 'id_number', 'address', 'city', 'country', 'postal_code']:
                    if data.get(field) is not None:
                        setattr(kyc, field, data[field])
                kyc.save()
            docs_created = []
            for doc in data.get('documents', []):
                if doc.get('document_type') and doc.get('file_url'):
                    d = KYCDocument.objects.create(
                        kyc=kyc, document_type=doc['document_type'],
                        file_url=doc['file_url'], status='pending',
                    )
                    docs_created.append({'pk': d.pk, 'document_type': doc['document_type']})
            return self.ok(
                {'kyc_id': kyc.pk, 'status': kyc.status,
                 'docs_uploaded': len(docs_created), 'documents': docs_created},
                message='KYC submitted. Under review.',
            )
        return guard.response

    @action(detail=False, methods=['get'], url_path='kyc-documents')
    def kyc_documents(self, request):
        pub = self.publisher
        kyc = self.get_subfolder_object(
            'publisher_management.publisher_kyc', 'PublisherKYC', publisher=pub
        )
        if not kyc:
            return self.ok({'documents': [], 'count': 0})
        docs = self.get_subfolder_queryset(
            'publisher_management.publisher_kyc', 'KYCDocument', kyc=kyc
        )
        if docs is None:
            return self.ok({'documents': [], 'count': 0})
        return self.ok({'documents': [
            {'pk': d.pk, 'doc_type': getattr(d, 'document_type', ''),
             'status': getattr(d, 'status', ''),
             'is_expired': d.is_expired() if hasattr(d, 'is_expired') else False,
             'uploaded_at': str(d.created_at)}
            for d in docs
        ], 'count': docs.count()})

    @action(detail=False, methods=['post'], url_path='kyc-verify-token')
    def kyc_verify_token(self, request):
        token = request.data.get('token', '')
        if not token:
            return self._build_error('token required.', 400)
        pub = self.publisher
        kyc = self.get_subfolder_object(
            'publisher_management.publisher_kyc', 'PublisherKYC', publisher=pub
        )
        if not kyc:
            return self._build_error('No KYC submission found.', 404)
        if hasattr(kyc, 'verify_by_token'):
            return self.ok({'verified': kyc.verify_by_token(token)})
        return self._build_error('Token verification not supported.', 400)

    # ══════════════════════════════════════════════════════════════════════════
    # BANK ACCOUNTS
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='bank-accounts')
    def bank_accounts(self, request):
        pub      = self.publisher
        accounts = self.get_subfolder_queryset(
            'publisher_management.publisher_bank_account', 'PublisherBankAccount',
            publisher=pub,
        )
        if accounts is None:
            return self.ok({'accounts': [], 'count': 0})
        return self.ok({'accounts': [
            {'pk': a.pk,
             'account_type':  getattr(a, 'account_type', ''),
             'is_primary':    getattr(a, 'is_primary', False),
             'is_verified':   getattr(a, 'is_verified', False),
             'masked_number': a.masked_account_number() if hasattr(a, 'masked_account_number') else '****',
             'status':        getattr(a, 'status', ''),
             'added_at':      str(a.created_at)}
            for a in accounts
        ], 'count': accounts.count()})

    @action(detail=False, methods=['post'], url_path='bank-accounts/add')
    def add_bank_account(self, request):
        pub          = self.publisher
        account_type = request.data.get('account_type', '')
        if not account_type:
            return self._build_error('account_type required.', 400)
        with self.handle_errors() as guard:
            from .publisher_management.publisher_bank_account import PublisherBankAccount
            account = PublisherBankAccount(publisher=pub)
            for field in ['account_type', 'account_holder_name', 'account_number',
                          'routing_number', 'bank_name', 'bank_country',
                          'swift_code', 'iban', 'email', 'currency']:
                if request.data.get(field) is not None:
                    setattr(account, field, request.data[field])
            account.status = 'pending_verification'
            account.save()
            if request.data.get('set_as_primary'):
                if hasattr(account, 'set_as_primary'):
                    account.set_as_primary()
                else:
                    PublisherBankAccount.objects.filter(publisher=pub).exclude(pk=account.pk).update(is_primary=False)
                    account.is_primary = True
                    account.save(update_fields=['is_primary'])
            return self.ok({
                'pk':            account.pk,
                'account_type':  account_type,
                'masked_number': account.masked_account_number() if hasattr(account, 'masked_account_number') else '****',
                'is_primary':    getattr(account, 'is_primary', False),
                'status':        account.status,
            }, message='Bank account added. Verification pending.')
        return guard.response

    @action(detail=False, methods=['post'], url_path='bank-accounts/primary')
    def set_primary_account(self, request):
        account_id = request.data.get('account_id')
        if not account_id:
            return self._build_error('account_id required.', 400)
        pub = self.publisher
        with self.handle_errors() as guard:
            from .publisher_management.publisher_bank_account import PublisherBankAccount
            account = PublisherBankAccount.objects.get(pk=account_id, publisher=pub)
            if hasattr(account, 'set_as_primary'):
                account.set_as_primary()
            else:
                PublisherBankAccount.objects.filter(publisher=pub).update(is_primary=False)
                PublisherBankAccount.objects.filter(pk=account_id).update(is_primary=True)
            return self.ok({'account_id': account_id, 'is_primary': True})
        return guard.response

    @action(detail=False, methods=['post'], url_path='bank-accounts/validate')
    def validate_bank_account(self, request):
        account_id = request.data.get('account_id')
        if not account_id:
            return self._build_error('account_id required.', 400)
        pub = self.publisher
        with self.handle_errors() as guard:
            from .publisher_management.publisher_bank_account import PublisherBankAccount
            account = PublisherBankAccount.objects.get(pk=account_id, publisher=pub)
            result  = account.validate() if hasattr(account, 'validate') else {'account_id': account_id, 'valid': True}
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['delete'], url_path='bank-accounts/remove')
    def remove_bank_account(self, request):
        account_id = request.data.get('account_id')
        if not account_id:
            return self._build_error('account_id required.', 400)
        pub = self.publisher
        with self.handle_errors() as guard:
            from .publisher_management.publisher_bank_account import PublisherBankAccount
            account = PublisherBankAccount.objects.get(pk=account_id, publisher=pub)
            if getattr(account, 'is_primary', False):
                remaining = PublisherBankAccount.objects.filter(publisher=pub).exclude(pk=account_id).count()
                if remaining == 0:
                    return self._build_error('Cannot remove the only bank account.', 400)
            account.delete()
            return self.ok({'account_id': account_id, 'removed': True})
        return guard.response

    # ══════════════════════════════════════════════════════════════════════════
    # COMMISSION
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='commissions')
    def commissions(self, request):
        pub  = self.publisher
        qs   = self.get_subfolder_queryset(
            'publisher_management.publisher_commission', 'PublisherCommission',
            publisher=pub,
        )
        if qs is None:
            return self.ok({'commissions': [], 'count': 0})
        qs = qs.order_by('-created_at')[:100]
        return self.ok({'commissions': [
            {'pk': c.pk, 'commission_type': getattr(c, 'commission_type', ''),
             'amount': str(getattr(c, 'amount', 0)), 'status': getattr(c, 'status', ''),
             'date': str(c.created_at)}
            for c in qs
        ], 'count': qs.count()})

    @action(detail=False, methods=['get'], url_path='commission-breakdown')
    def commission_breakdown(self, request):
        pub           = self.publisher
        gross_revenue = float(request.query_params.get('gross_revenue', 1000))
        with self.handle_errors() as guard:
            from .publisher_management.publisher_commission import calculate_tiered_commission
            return self.ok(calculate_tiered_commission(pub, gross_revenue))
        return guard.response

    @action(detail=False, methods=['get'], url_path='referral-commission')
    def referral_commission(self, request):
        pub  = self.publisher
        qs   = self.get_subfolder_queryset(
            'publisher_management.publisher_commission', 'PublisherReferral',
            referrer=pub,
        )
        if qs is None:
            return self.ok({'referrals': [], 'count': 0})
        qs = qs.order_by('-created_at')[:50]
        return self.ok({'referrals': [
            {'pk': r.pk, 'referred_name': str(getattr(r, 'referred', '')),
             'commission_rate': str(getattr(r, 'commission_rate', 0)),
             'total_earned': str(getattr(r, 'total_earned', 0)),
             'status': getattr(r, 'status', ''), 'joined_at': str(r.created_at)}
            for r in qs
        ], 'count': qs.count()})

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYTICS & PERFORMANCE
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='comparison')
    def comparison(self, request):
        with self.handle_errors() as guard:
            from .publisher_management.publisher_analytics import get_comparison_analytics
            return self.ok(get_comparison_analytics(self.publisher))
        return guard.response

    @action(detail=False, methods=['get'], url_path='period-stats')
    def period_stats(self, request):
        with self.handle_errors() as guard:
            from .publisher_management.publisher_analytics import get_period_stats
            return self.ok(get_period_stats(
                self.publisher,
                start=request.query_params.get('start'),
                end=request.query_params.get('end'),
            ))
        return guard.response

    @action(detail=False, methods=['get'], url_path='performance-goals')
    def performance_goals(self, request):
        with self.handle_errors() as guard:
            from .publisher_management.publisher_performance import get_actual_performance
            return self.ok(get_actual_performance(self.publisher))
        return guard.response

    @action(detail=False, methods=['get'], url_path='achievement')
    def achievement(self, request):
        with self.handle_errors() as guard:
            from .publisher_management.publisher_performance import get_achievement_pct
            return self.ok(get_achievement_pct(self.publisher))
        return guard.response

    # ══════════════════════════════════════════════════════════════════════════
    # RATING & BRAND
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='rating')
    def rating(self, request):
        pub    = self.publisher
        rating = self.get_subfolder_object(
            'publisher_management.publisher_rating', 'PublisherRating', publisher=pub
        )
        if not rating:
            return self.ok({'rating': None, 'message': 'No rating yet.'})
        return self.ok({
            'pk':             rating.pk,
            'overall_score':  getattr(rating, 'overall_score', 0),
            'weighted_score': rating.weighted_score() if hasattr(rating, 'weighted_score') else 0,
            'category_scores': {
                'content':   getattr(rating, 'content_score', 0),
                'traffic':   getattr(rating, 'traffic_score', 0),
                'technical': getattr(rating, 'technical_score', 0),
            },
        })

    @action(detail=False, methods=['get'], url_path='brand')
    def brand(self, request):
        pub   = self.publisher
        brand = self.get_subfolder_object(
            'publisher_management.publisher_brand', 'PublisherBrand', publisher=pub
        )
        if not brand:
            return self.ok({'brand': None})
        return self.ok({
            'brand_name':    brand.effective_brand_name() if hasattr(brand, 'effective_brand_name') else getattr(brand, 'brand_name', ''),
            'store_url':     brand.store_url() if hasattr(brand, 'store_url') else '',
            'color_palette': brand.color_palette() if hasattr(brand, 'color_palette') else {},
            'logo_url':      getattr(brand, 'logo_url', ''),
        })

    @action(detail=False, methods=['get'], url_path='next-payout')
    def next_payout(self, request):
        with self.handle_errors() as guard:
            from .publisher_management.publisher_payout import calculate_next_payout_date
            result = calculate_next_payout_date(self.publisher)
            return self.ok(result if isinstance(result, dict) else {'next_payout_date': str(result)})
        return guard.response

    # ══════════════════════════════════════════════════════════════════════════
    # STORE, BUSINESS, VERIFICATION, REFERRALS, LEADERBOARD, TARGETS, BLACKLIST
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='store')
    def store(self, request):
        pub   = self.publisher
        store = self.get_subfolder_object(
            'publisher_management.publisher_store', 'PublisherStore', publisher=pub
        )
        if not store:
            return self.ok({'store': None, 'message': 'No store profile found.'})
        return self.ok({
            'pk':            store.pk,
            'store_name':    getattr(store, 'store_name', ''),
            'description':   getattr(store, 'description', ''),
            'slug':          getattr(store, 'slug', ''),
            'logo_url':      getattr(store, 'logo_url', ''),
            'contact_email': getattr(store, 'contact_email', ''),
            'is_active':     getattr(store, 'is_active', False),
            'store_url':     store.get_absolute_url() if hasattr(store, 'get_absolute_url') else '',
            'created_at':    str(store.created_at),
        })

    @action(detail=False, methods=['post'], url_path='store/contact')
    def store_contact(self, request):
        data     = request.data
        required = ['sender_name', 'sender_email', 'message']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return self._build_error(f'Missing fields: {", ".join(missing)}', 400)
        pub = self.publisher
        with self.handle_errors() as guard:
            from .publisher_management.publisher_store import PublisherStore, StoreContactMessage
            store = PublisherStore.objects.filter(publisher=pub).first()
            if not store:
                return self._build_error('Store not found.', 404)
            msg = StoreContactMessage.objects.create(
                store=store, sender_name=data['sender_name'],
                sender_email=data['sender_email'],
                subject=data.get('subject', ''), message=data['message'],
            )
            return self.ok({'message_id': msg.pk, 'status': 'sent'},
                           message='Message sent successfully.')
        return guard.response

    @action(detail=False, methods=['get'], url_path='business')
    def business(self, request):
        pub      = self.publisher
        business = self.get_subfolder_object(
            'publisher_management.publisher_business', 'PublisherBusiness', publisher=pub
        )
        if not business:
            return self.ok({'business': None, 'message': 'No business profile found.'})
        return self.ok({
            'pk':                   business.pk,
            'legal_name':           getattr(business, 'legal_name', ''),
            'registration_number':  getattr(business, 'registration_number', ''),
            'tax_id':               getattr(business, 'tax_id', ''),
            'business_type':        getattr(business, 'business_type', ''),
            'incorporation_country':getattr(business, 'incorporation_country', ''),
            'website':              getattr(business, 'website', ''),
            'is_verified':          getattr(business, 'is_verified', False),
            'created_at':           str(business.created_at),
        })

    @action(detail=False, methods=['get'], url_path='verification-status')
    def verification_status(self, request):
        pub           = self.publisher
        verifications = self.get_subfolder_queryset(
            'publisher_management.publisher_verification', 'PublisherVerification',
            publisher=pub,
        )
        if verifications is None:
            return self.ok({'verifications': [], 'count': 0, 'all_verified': False})
        results = [
            {'pk': v.pk, 'verification_type': getattr(v, 'verification_type', ''),
             'target': getattr(v, 'target', ''), 'status': getattr(v, 'status', ''),
             'method': getattr(v, 'method', ''),
             'is_expired': v.is_expired() if hasattr(v, 'is_expired') else False}
            for v in verifications
        ]
        return self.ok({
            'verifications': results,
            'count':         len(results),
            'all_verified':  all(r['status'] == 'verified' for r in results),
        })

    @action(detail=False, methods=['get'], url_path='referrals')
    def referrals(self, request):
        pub       = self.publisher
        referrals = self.get_subfolder_queryset(
            'publisher_management.publisher_commission', 'PublisherReferral',
            referrer=pub,
        )
        if referrals is None:
            return self.ok({'referrals': [], 'total_referrals': 0, 'total_earned': 0})
        results = list(referrals.order_by('-created_at'))
        total   = sum(float(getattr(r, 'total_earned', 0)) for r in results)
        return self.ok({'referrals': [
            {'pk': r.pk, 'referred_id': str(getattr(r, 'referred', '')),
             'commission_rate': str(getattr(r, 'commission_rate', 0)),
             'total_earned': str(getattr(r, 'total_earned', 0)),
             'status': getattr(r, 'status', ''), 'joined_at': str(r.created_at)}
            for r in results
        ], 'total_referrals': len(results), 'total_earned': total})

    @action(detail=False, methods=['get'], url_path='leaderboard')
    def leaderboard(self, request):
        pub   = self.publisher
        entry = self.get_subfolder_object(
            'publisher_management.publisher_leaderboard', 'PublisherLeaderboard',
            publisher=pub,
        )
        if not entry:
            return self.ok({'rank': None, 'message': 'Not yet on the leaderboard.'})
        return self.ok({
            'pk':           entry.pk,
            'rank':         getattr(entry, 'rank', None),
            'score':        getattr(entry, 'score', 0),
            'tier':         getattr(entry, 'tier', ''),
            'revenue_rank': getattr(entry, 'revenue_rank', None),
            'quality_rank': getattr(entry, 'quality_rank', None),
            'period':       getattr(entry, 'period', ''),
            'updated_at':   str(entry.updated_at),
        })

    @action(detail=False, methods=['get'], url_path='performance-targets')
    def performance_targets(self, request):
        pub     = self.publisher
        targets = self.get_subfolder_queryset(
            'publisher_management.publisher_performance', 'PublisherPerformanceTarget',
            publisher=pub,
        )
        snapshot = self.get_subfolder_object(
            'publisher_management.publisher_performance', 'PublisherPerformanceSnapshot',
            publisher=pub,
        )
        if targets is None:
            return self.ok({'targets': [], 'latest_snapshot': None, 'targets_count': 0})
        targets = targets.order_by('-created_at')[:5]
        return self.ok({
            'targets': [
                {'pk': t.pk, 'metric': getattr(t, 'metric', ''),
                 'target_value': str(getattr(t, 'target_value', 0)),
                 'period': getattr(t, 'period', '')}
                for t in targets
            ],
            'latest_snapshot': {
                'pk':           snapshot.pk if snapshot else None,
                'revenue':      str(getattr(snapshot, 'revenue', 0)) if snapshot else '0',
                'impressions':  getattr(snapshot, 'impressions', 0) if snapshot else 0,
            } if snapshot else None,
            'targets_count': targets.count(),
        })

    @action(detail=False, methods=['get'], url_path='blacklist-status')
    def blacklist_status(self, request):
        pub   = self.publisher
        entry = self.get_subfolder_object(
            'publisher_management.publisher_blacklist', 'PublisherBlacklist',
            publisher=pub, is_active=True,
        )
        return self.ok({
            'is_blacklisted': entry is not None,
            'reason':         getattr(entry, 'reason', '') if entry else '',
            'blacklisted_at': str(entry.created_at) if entry else '',
            'expires_at':     str(getattr(entry, 'expires_at', '')) if entry else '',
        })
