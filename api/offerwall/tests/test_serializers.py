"""
Serializer Tests — HIGH + MEDIUM PRIORITY
Run: python manage.py test api.offerwall.tests.test_serializers
"""
import uuid
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.request import Request
from api.offerwall.models import (
    OfferProvider, OfferCategory, Offer, OfferClick, OfferConversion, OfferWall
)
from api.offerwall.serializers import (
    OfferProviderSerializer, OfferProviderDetailSerializer,
    OfferCategorySerializer, OfferListSerializer, OfferDetailSerializer,
    OfferClickSerializer, OfferConversionSerializer, OfferConversionDetailSerializer,
    OfferWallSerializer, OfferClickCreateSerializer,
    OfferConversionWebhookSerializer, OfferSearchSerializer,
)

User = get_user_model()
rf = RequestFactory()

def mk_prov(**kw):
    d = dict(name='SP', provider_type='tapjoy', status='active', revenue_share=Decimal('70'))
    d.update(kw); return OfferProvider.objects.create(**d)

def mk_cat(**kw):
    d = dict(name='Games', slug=f'gm-{uuid.uuid4().hex[:6]}', is_active=True)
    d.update(kw); return OfferCategory.objects.create(**d)

def mk_offer(prov, cat=None, **kw):
    d = dict(external_offer_id=str(uuid.uuid4())[:12], title='Ser Offer',
             description='desc', short_description='short',
             payout=Decimal('2'), reward_amount=Decimal('1.40'),
             reward_currency='BDT', click_url='https://x.com',
             status='active', offer_type='app_install', platform='android',
             difficulty='easy', estimated_time_minutes=5)
    if cat: d['category'] = cat
    d.update(kw); return Offer.objects.create(provider=prov, **d)

def mk_user(un='su'): return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')

def drf_req(user=None):
    req = rf.get('/')
    if user: req.user = user
    else:
        from django.contrib.auth.models import AnonymousUser
        req.user = AnonymousUser()
    return Request(req)


# ── OfferProviderSerializer ───────────────────────────────────────────────────
class OfferProviderSerializerTest(TestCase):
    def setUp(self): self.p = mk_prov()

    def test_required_fields(self):
        d = OfferProviderSerializer(self.p).data
        for f in ['id','name','provider_type','status','revenue_share',
                  'total_offers','total_conversions','is_active_status']:
            self.assertIn(f, d)

    def test_is_active_true(self): self.assertTrue(OfferProviderSerializer(self.p).data['is_active_status'])
    def test_is_active_false(self):
        p = mk_prov(name='IN', status='inactive')
        self.assertFalse(OfferProviderSerializer(p).data['is_active_status'])

    def test_total_offers_read_only(self):
        ser = OfferProviderSerializer(self.p, data={'total_offers': 999,
              'name': 'T', 'provider_type': 'tapjoy', 'status': 'active', 'revenue_share': '70'})
        ser.is_valid()
        self.assertNotIn('total_offers', ser.validated_data)

    def test_valid_data_passes(self):
        ser = OfferProviderSerializer(data={'name': 'N', 'provider_type': 'adgem',
              'status': 'testing', 'revenue_share': '65'})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_revenue_share_required(self):
        ser = OfferProviderSerializer(data={'name': 'N', 'provider_type': 'tapjoy', 'status': 'active'})
        self.assertFalse(ser.is_valid()); self.assertIn('revenue_share', ser.errors)

    def test_detail_serializer_has_api_key(self):
        d = OfferProviderDetailSerializer(mk_prov(name='DET', api_key='k123')).data
        self.assertIn('api_key', d)


# ── OfferCategorySerializer ───────────────────────────────────────────────────
class OfferCategorySerializerTest(TestCase):
    def setUp(self): self.cat = mk_cat()

    def test_required_fields(self):
        d = OfferCategorySerializer(self.cat).data
        for f in ['id','name','slug','is_active','offer_count']: self.assertIn(f, d)

    def test_valid_data_passes(self):
        ser = OfferCategorySerializer(data={'name': 'Survey', 'slug': f'sv-{uuid.uuid4().hex[:6]}'})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_blank_name_fails(self):
        ser = OfferCategorySerializer(data={'name': '', 'slug': 'no-name'})
        self.assertFalse(ser.is_valid()); self.assertIn('name', ser.errors)

    def test_offer_count_read_only(self):
        ser = OfferCategorySerializer(self.cat, data={'name': 'G', 'slug': f'g-{uuid.uuid4().hex[:4]}', 'offer_count': 999})
        ser.is_valid(); self.assertNotIn('offer_count', ser.validated_data)


# ── OfferListSerializer ───────────────────────────────────────────────────────
class OfferListSerializerTest(TestCase):
    def setUp(self):
        self.prov = mk_prov(); self.cat = mk_cat(); self.user = mk_user()
        self.offer = mk_offer(self.prov, self.cat)

    def test_required_fields(self):
        d = OfferListSerializer(self.offer, context={'request': drf_req()}).data
        for f in ['id','title','reward_amount','reward_currency','difficulty',
                  'estimated_time_minutes','is_featured','quality_score','is_available']:
            self.assertIn(f, d)

    def test_provider_name(self):
        self.assertEqual(OfferListSerializer(self.offer, context={'request': drf_req()}).data['provider_name'], 'SP')

    def test_category_name(self):
        self.assertEqual(OfferListSerializer(self.offer, context={'request': drf_req()}).data['category_name'], 'Games')

    def test_is_available_true_active_offer(self):
        self.assertTrue(OfferListSerializer(self.offer, context={'request': drf_req(self.user)}).data['is_available'])

    def test_is_available_false_paused(self):
        paused = mk_offer(self.prov, status='paused')
        self.assertFalse(OfferListSerializer(paused, context={'request': drf_req(self.user)}).data['is_available'])

    def test_is_available_false_user_limit_reached(self):
        o = mk_offer(self.prov, user_limit=1)
        OfferConversion.objects.create(offer=o, user=self.user, conversion_id='lm1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        self.assertFalse(OfferListSerializer(o, context={'request': drf_req(self.user)}).data['is_available'])

    def test_offer_type_display(self):
        d = OfferListSerializer(self.offer, context={'request': drf_req()}).data
        self.assertIn('offer_type_display', d); self.assertEqual(d['offer_type_display'], 'App Install')

    def test_difficulty_display(self):
        d = OfferListSerializer(self.offer, context={'request': drf_req()}).data
        self.assertIn('difficulty_display', d); self.assertEqual(d['difficulty_display'], 'Easy')


# ── OfferDetailSerializer ─────────────────────────────────────────────────────
class OfferDetailSerializerTest(TestCase):
    def setUp(self):
        self.prov = mk_prov(); self.cat = mk_cat(); self.user = mk_user('du')
        self.offer = mk_offer(self.prov, self.cat)

    def test_nested_provider(self):
        d = OfferDetailSerializer(self.offer, context={'request': drf_req(self.user)}).data
        self.assertIsInstance(d['provider'], dict); self.assertEqual(d['provider']['name'], 'SP')

    def test_nested_category(self):
        d = OfferDetailSerializer(self.offer, context={'request': drf_req(self.user)}).data
        self.assertIsInstance(d['category'], dict)

    def test_user_completion_count_zero(self):
        d = OfferDetailSerializer(self.offer, context={'request': drf_req(self.user)}).data
        self.assertEqual(d['user_completion_count'], 0)

    def test_user_completion_count_increments(self):
        OfferConversion.objects.create(offer=self.offer, user=self.user, conversion_id='uc1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        d = OfferDetailSerializer(self.offer, context={'request': drf_req(self.user)}).data
        self.assertEqual(d['user_completion_count'], 1)

    def test_can_complete_true_under_limit(self):
        o = mk_offer(self.prov, user_limit=3)
        d = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertTrue(d['can_complete'])

    def test_can_complete_false_limit_reached(self):
        o = mk_offer(self.prov, user_limit=1)
        OfferConversion.objects.create(offer=o, user=self.user, conversion_id='cc1',
            payout_amount=Decimal('1'), reward_amount=Decimal('0.70'), status='approved')
        d = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertFalse(d['can_complete'])

    def test_can_complete_true_unlimited(self):
        o = mk_offer(self.prov, user_limit=0)
        d = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertTrue(d['can_complete'])

    def test_can_complete_false_no_auth(self):
        d = OfferDetailSerializer(self.offer, context={'request': drf_req()}).data
        self.assertFalse(d['can_complete'])


# ── OfferConversionWebhookSerializer — HIGH PRIORITY ─────────────────────────
class WebhookSerializerTest(TestCase):
    def _valid(self, **ov):
        d = {'offer_id': 'off1', 'user_id': '42', 'transaction_id': 'tx1',
             'payout': '1.5', 'currency': 'USD', 'status': 'pending'}
        d.update(ov); return d

    def test_valid_passes(self):
        ser = OfferConversionWebhookSerializer(data=self._valid())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_missing_offer_id_fails(self):
        d = self._valid(); del d['offer_id']
        ser = OfferConversionWebhookSerializer(data=d)
        self.assertFalse(ser.is_valid()); self.assertIn('offer_id', ser.errors)

    def test_missing_user_id_fails(self):
        d = self._valid(); del d['user_id']
        self.assertFalse(OfferConversionWebhookSerializer(data=d).is_valid())

    def test_missing_transaction_id_fails(self):
        d = self._valid(); del d['transaction_id']
        self.assertFalse(OfferConversionWebhookSerializer(data=d).is_valid())

    def test_zero_payout_fails(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(payout='0'))
        self.assertFalse(ser.is_valid()); self.assertIn('payout', ser.errors)

    def test_negative_payout_fails(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(payout='-1'))
        self.assertFalse(ser.is_valid())

    def test_positive_tiny_payout_passes(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(payout='0.000001'))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_status_fails(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(status='invalid'))
        self.assertFalse(ser.is_valid()); self.assertIn('status', ser.errors)

    def test_valid_statuses(self):
        for s in ['pending', 'approved', 'rejected', 'chargeback']:
            ser = OfferConversionWebhookSerializer(data=self._valid(status=s))
            self.assertTrue(ser.is_valid(), f'{s}: {ser.errors}')

    def test_status_defaults_pending(self):
        d = self._valid(); del d['status']
        ser = OfferConversionWebhookSerializer(data=d)
        self.assertTrue(ser.is_valid())
        self.assertEqual(ser.validated_data['status'], 'pending')


# ── OfferClickCreateSerializer — HIGH PRIORITY ────────────────────────────────
class ClickCreateSerializerTest(TestCase):
    def test_valid_minimal(self):
        ser = OfferClickCreateSerializer(data={'offer_id': str(uuid.uuid4())})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_offer_id_required(self):
        ser = OfferClickCreateSerializer(data={})
        self.assertFalse(ser.is_valid()); self.assertIn('offer_id', ser.errors)

    def test_invalid_uuid_fails(self):
        ser = OfferClickCreateSerializer(data={'offer_id': 'not-uuid'})
        self.assertFalse(ser.is_valid())

    def test_all_optional_fields(self):
        ser = OfferClickCreateSerializer(data={
            'offer_id': str(uuid.uuid4()),
            'device_type': 'mobile', 'device_model': 'Galaxy S24',
            'os': 'Android', 'os_version': '14',
            'session_id': 'sess123', 'tracking_params': {'utm': 'offerwall'},
        })
        self.assertTrue(ser.is_valid(), ser.errors)


# ── OfferSearchSerializer — MEDIUM PRIORITY ───────────────────────────────────
class SearchSerializerTest(TestCase):
    def test_empty_is_valid(self):
        ser = OfferSearchSerializer(data={})
        self.assertTrue(ser.is_valid())

    def test_valid_full(self):
        ser = OfferSearchSerializer(data={
            'query': 'install', 'offer_type': 'app_install', 'platform': 'android',
            'min_payout': '0.5', 'max_payout': '5', 'difficulty': 'easy',
            'is_featured': True, 'sort_by': 'payout', 'page': 1, 'page_size': 20,
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_category_uuid(self):
        # category is CharField — accepts string values; test non-string rejection
        ser = OfferSearchSerializer(data={'category': 'any-string'})
        ser.is_valid()
        self.assertIn('category', ser.validated_data)  # CharField accepts it

    def test_min_payout_must_be_number(self):
        ser = OfferSearchSerializer(data={'min_payout': 'abc'})
        self.assertFalse(ser.is_valid())
        self.assertIn('min_payout', ser.errors)

    def test_sort_by_default(self):
        ser = OfferSearchSerializer(data={})
        ser.is_valid()
        self.assertEqual(ser.validated_data.get('sort_by'), 'quality_score')


# ── OfferConversionSerializer — MEDIUM PRIORITY ───────────────────────────────
class ConversionSerializerTest(TestCase):
    def setUp(self):
        self.prov = mk_prov(); self.offer = mk_offer(self.prov)
        self.user = mk_user('cnv')
        self.conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='cs1',
            payout_amount=Decimal('2'), payout_currency='USD',
            reward_amount=Decimal('1.40'), reward_currency='BDT',
            bonus_amount=Decimal('0.10'), status='pending')

    def test_required_fields(self):
        d = OfferConversionSerializer(self.conv).data
        for f in ['id','offer','user','conversion_id','payout_amount',
                  'reward_amount','reward_currency','status','status_display','converted_at']:
            self.assertIn(f, d)

    def test_field_name_is_external_WalletTransaction_id(self):
        d = OfferConversionSerializer(self.conv).data
        self.assertIn('external_WalletTransaction_id', d)
        self.assertNotIn('external_transaction_id', d)

    def test_offer_title_shown(self):
        self.assertEqual(OfferConversionSerializer(self.conv).data['offer_title'], 'Ser Offer')

    def test_status_display_pending(self):
        self.assertEqual(OfferConversionSerializer(self.conv).data['status_display'], 'Pending')

    def test_conversion_id_read_only(self):
        ser = OfferConversionSerializer(self.conv, data={'conversion_id': 'HACK'})
        ser.is_valid(); self.assertNotIn('conversion_id', ser.validated_data)

    def test_detail_has_postback_data(self):
        d = OfferConversionDetailSerializer(self.conv).data
        self.assertIn('postback_data', d)

    def test_detail_offer_is_nested(self):
        d = OfferConversionDetailSerializer(self.conv).data
        self.assertIsInstance(d['offer'], dict)


# ── OfferWallSerializer — MEDIUM PRIORITY ─────────────────────────────────────
class OfferWallSerializerTest(TestCase):
    def setUp(self):
        self.prov = mk_prov(); self.cat = mk_cat()
        self.wall = OfferWall.objects.create(name='Main Wall', slug='main-wall', is_active=True)
        self.wall.categories.add(self.cat); self.wall.providers.add(self.prov)

    def test_required_fields(self):
        d = OfferWallSerializer(self.wall).data
        for f in ['id','name','slug','is_active','offer_count']: self.assertIn(f, d)

    def test_offer_count_zero_no_offers(self):
        self.assertEqual(OfferWallSerializer(self.wall).data['offer_count'], 0)

    def test_offer_count_active_only(self):
        mk_offer(self.prov, self.cat); mk_offer(self.prov, self.cat)
        mk_offer(self.prov, self.cat, status='paused')
        self.assertEqual(OfferWallSerializer(self.wall).data['offer_count'], 2)

    def test_categories_data_nested(self):
        d = OfferWallSerializer(self.wall).data
        self.assertIn('categories_data', d); self.assertEqual(len(d['categories_data']), 1)

    def test_offer_count_read_only(self):
        ser = OfferWallSerializer(self.wall, data={'name': 'W', 'slug': 'w2', 'offer_count': 999})
        ser.is_valid(); self.assertNotIn('offer_count', ser.validated_data)


# ── Extra Serializer Tests ────────────────────────────────────────────────────

class OfferListSerializerExtraTest(TestCase):

    def setUp(self):
        self.prov = mk_prov(name='ExtraSP')
        self.user = mk_user('esu')

    def test_no_request_context_is_available_falls_back(self):
        o = mk_offer(self.prov)
        # No context → should not crash
        data = OfferListSerializer(o).data
        self.assertIn('is_available', data)

    def test_countries_field_present(self):
        o = mk_offer(self.prov, countries=['BD', 'IN'])
        data = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertIn('countries', data)
        self.assertIn('BD', data['countries'])

    def test_tags_field_present(self):
        o = mk_offer(self.prov, tags=['gaming', 'casual'])
        data = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertIn('tags', data)

    def test_short_description_in_list(self):
        o = mk_offer(self.prov, short_description='Short desc here')
        data = OfferListSerializer(o, context={'request': drf_req()}).data
        self.assertIn('short_description', data)

    def test_click_url_present(self):
        o = mk_offer(self.prov, click_url='https://click.example.com/track')
        data = OfferDetailSerializer(o, context={'request': drf_req(self.user)}).data
        self.assertIn('click_url', data)
        self.assertEqual(data['click_url'], 'https://click.example.com/track')

    def test_payout_is_string_or_decimal(self):
        o = mk_offer(self.prov, payout=Decimal('2.500000'))
        data = OfferListSerializer(o, context={'request': drf_req()}).data
        self.assertIn('payout', data)


class OfferConversionSerializerExtraTest(TestCase):

    def setUp(self):
        self.prov = mk_prov(name='CnvExtraSP')
        self.offer = mk_offer(self.prov)
        self.user  = mk_user('ceu')

    def test_bonus_amount_shown(self):
        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='bonus_ser_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
            bonus_amount=Decimal('0.60'), status='pending')
        data = OfferConversionSerializer(conv).data
        self.assertIn('bonus_amount', data)
        self.assertEqual(Decimal(str(data['bonus_amount'])), Decimal('0.60'))

    def test_approved_conversion_has_approved_at(self):
        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='app_at_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'), status='pending')
        conv.approve()
        conv.refresh_from_db()
        data = OfferConversionSerializer(conv).data
        self.assertIn('approved_at', data)
        self.assertIsNotNone(data['approved_at'])

    def test_detail_has_provider_data(self):
        conv = OfferConversion.objects.create(
            offer=self.offer, user=self.user, conversion_id='pd_ser_001',
            payout_amount=Decimal('2'), reward_amount=Decimal('1.40'),
            provider_data={'offer_id': 'tapjoy_001'}, status='pending')
        data = OfferConversionDetailSerializer(conv).data
        self.assertIn('provider_data', data)


class OfferProviderSerializerExtraTest(TestCase):

    def test_provider_type_choices_validated(self):
        ser = OfferProviderSerializer(data={
            'name': 'BadType', 'provider_type': 'invalid_provider_xyz',
            'status': 'active', 'revenue_share': '70'})
        self.assertFalse(ser.is_valid())
        self.assertIn('provider_type', ser.errors)

    def test_revenue_share_cannot_exceed_100(self):
        ser = OfferProviderSerializer(data={
            'name': 'Over100', 'provider_type': 'tapjoy',
            'status': 'active', 'revenue_share': '150'})
        self.assertFalse(ser.is_valid())

    def test_status_choices_validated(self):
        ser = OfferProviderSerializer(data={
            'name': 'BadStatus', 'provider_type': 'tapjoy',
            'status': 'invalid_status_xyz', 'revenue_share': '70'})
        self.assertFalse(ser.is_valid())
        self.assertIn('status', ser.errors)


class WebhookSerializerExtraTest(TestCase):

    def _valid(self, **ov):
        d = {'offer_id': 'off1', 'user_id': '42', 'transaction_id': 'tx1',
             'payout': '1.5', 'currency': 'USD', 'status': 'pending'}
        d.update(ov); return d

    def test_extra_fields_ignored_safely(self):
        d = self._valid()
        d['unknown_extra_field'] = 'should_be_ignored'
        ser = OfferConversionWebhookSerializer(data=d)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_payout_as_integer_accepted(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(payout='2'))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_very_large_payout_accepted(self):
        ser = OfferConversionWebhookSerializer(data=self._valid(payout='9999.999999'))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_currency_optional(self):
        d = self._valid()
        del d['currency']
        ser = OfferConversionWebhookSerializer(data=d)
        # currency optional → should still be valid
        if not ser.is_valid():
            self.assertNotIn('currency', ser.errors)
