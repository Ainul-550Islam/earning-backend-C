# management/commands/seed_translation_keys.py
"""python manage.py seed_translation_keys — CPAlead earning site keys seed করে"""
from django.core.management.base import BaseCommand

# CPAlead-specific TranslationKey definitions
CPALEAD_KEYS = [
    # ── Common ───────────────────────────────────────────────────
    {'key': 'common.hello',         'category': 'common', 'priority': 'high',    'description': 'Greeting'},
    {'key': 'common.goodbye',       'category': 'common', 'priority': 'normal',  'description': 'Farewell'},
    {'key': 'common.yes',           'category': 'common', 'priority': 'high',    'description': 'Affirmative'},
    {'key': 'common.no',            'category': 'common', 'priority': 'high',    'description': 'Negative'},
    {'key': 'common.save',          'category': 'common', 'priority': 'high',    'description': 'Save button'},
    {'key': 'common.cancel',        'category': 'common', 'priority': 'high',    'description': 'Cancel button'},
    {'key': 'common.search',        'category': 'common', 'priority': 'high',    'description': 'Search action'},
    {'key': 'common.loading',       'category': 'common', 'priority': 'high',    'description': 'Loading state'},
    {'key': 'common.error',         'category': 'common', 'priority': 'critical','description': 'Generic error'},
    {'key': 'common.success',       'category': 'common', 'priority': 'high',    'description': 'Success message'},
    {'key': 'common.back',          'category': 'common', 'priority': 'normal',  'description': 'Back navigation'},
    {'key': 'common.next',          'category': 'common', 'priority': 'high',    'description': 'Next navigation'},
    {'key': 'common.close',         'category': 'common', 'priority': 'normal',  'description': 'Close dialog'},
    {'key': 'common.delete',        'category': 'common', 'priority': 'high',    'description': 'Delete action'},
    {'key': 'common.edit',          'category': 'common', 'priority': 'normal',  'description': 'Edit action'},
    # ── Auth ─────────────────────────────────────────────────────
    {'key': 'auth.login',           'category': 'auth',   'priority': 'critical','description': 'Login button'},
    {'key': 'auth.logout',          'category': 'auth',   'priority': 'critical','description': 'Logout button'},
    {'key': 'auth.signup',          'category': 'auth',   'priority': 'critical','description': 'Sign up button'},
    {'key': 'auth.email',           'category': 'auth',   'priority': 'high',    'description': 'Email field'},
    {'key': 'auth.password',        'category': 'auth',   'priority': 'high',    'description': 'Password field'},
    {'key': 'auth.forgot_password', 'category': 'auth',   'priority': 'high',    'description': 'Forgot password'},
    {'key': 'auth.remember_me',     'category': 'auth',   'priority': 'normal',  'description': 'Remember me'},
    # ── Navigation ───────────────────────────────────────────────
    {'key': 'nav.home',             'category': 'nav',    'priority': 'critical','description': 'Home link'},
    {'key': 'nav.dashboard',        'category': 'nav',    'priority': 'critical','description': 'Dashboard link'},
    {'key': 'nav.settings',         'category': 'nav',    'priority': 'high',    'description': 'Settings link'},
    {'key': 'nav.profile',          'category': 'nav',    'priority': 'high',    'description': 'Profile link'},
    {'key': 'nav.notifications',    'category': 'nav',    'priority': 'high',    'description': 'Notifications link'},
    {'key': 'nav.help',             'category': 'nav',    'priority': 'normal',  'description': 'Help link'},
    # ── Offer (CPAlead core) ─────────────────────────────────────
    {'key': 'offer.title',          'category': 'offer',  'priority': 'critical','description': 'Offers section title'},
    {'key': 'offer.complete',       'category': 'offer',  'priority': 'critical','description': 'Complete offer button'},
    {'key': 'offer.reward',         'category': 'offer',  'priority': 'critical','description': 'Reward label'},
    {'key': 'offer.category',       'category': 'offer',  'priority': 'high',    'description': 'Category label'},
    {'key': 'offer.description',    'category': 'offer',  'priority': 'high',    'description': 'Description label'},
    {'key': 'offer.requirements',   'category': 'offer',  'priority': 'high',    'description': 'Requirements label'},
    {'key': 'offer.expires',        'category': 'offer',  'priority': 'high',    'description': 'Expires label'},
    {'key': 'offer.new',            'category': 'offer',  'priority': 'high',    'description': 'New offer badge'},
    {'key': 'offer.featured',       'category': 'offer',  'priority': 'high',    'description': 'Featured badge'},
    {'key': 'offer.completed',      'category': 'offer',  'priority': 'high',    'description': 'Completed status'},
    {'key': 'offer.in_progress',    'category': 'offer',  'priority': 'high',    'description': 'In progress status'},
    # ── Earning (CPAlead core) ───────────────────────────────────
    {'key': 'earning.total',        'category': 'earning','priority': 'critical','description': 'Total earnings label'},
    {'key': 'earning.pending',      'category': 'earning','priority': 'critical','description': 'Pending earnings'},
    {'key': 'earning.available',    'category': 'earning','priority': 'critical','description': 'Available balance'},
    {'key': 'earning.history',      'category': 'earning','priority': 'high',    'description': 'Earning history'},
    {'key': 'earning.today',        'category': 'earning','priority': 'high',    'description': "Today's earnings"},
    {'key': 'earning.this_week',    'category': 'earning','priority': 'normal',  'description': 'This week earnings'},
    {'key': 'earning.this_month',   'category': 'earning','priority': 'normal',  'description': 'This month earnings'},
    # ── Withdraw (CPAlead core) ──────────────────────────────────
    {'key': 'withdraw.button',      'category': 'withdraw','priority':'critical','description': 'Withdraw button'},
    {'key': 'withdraw.minimum',     'category': 'withdraw','priority':'critical','description': 'Minimum withdrawal'},
    {'key': 'withdraw.history',     'category': 'withdraw','priority':'high',    'description': 'Withdrawal history'},
    {'key': 'withdraw.method',      'category': 'withdraw','priority':'critical','description': 'Payment method'},
    {'key': 'withdraw.amount',      'category': 'withdraw','priority':'critical','description': 'Withdrawal amount'},
    {'key': 'withdraw.pending',     'category': 'withdraw','priority':'high',    'description': 'Pending withdrawal'},
    {'key': 'withdraw.completed',   'category': 'withdraw','priority':'high',    'description': 'Completed withdrawal'},
    {'key': 'withdraw.failed',      'category': 'withdraw','priority':'high',    'description': 'Failed withdrawal'},
    # ── Referral ─────────────────────────────────────────────────
    {'key': 'referral.code',        'category': 'referral','priority':'critical','description': 'Referral code label'},
    {'key': 'referral.earnings',    'category': 'referral','priority':'high',    'description': 'Referral earnings'},
    {'key': 'referral.link',        'category': 'referral','priority':'high',    'description': 'Referral link label'},
    {'key': 'referral.copy',        'category': 'referral','priority':'high',    'description': 'Copy referral link'},
    {'key': 'referral.share',       'category': 'referral','priority':'high',    'description': 'Share referral'},
    {'key': 'referral.count',       'category': 'referral','priority':'normal',  'description': 'Total referrals count'},
    {'key': 'referral.bonus',       'category': 'referral','priority':'high',    'description': 'Referral bonus'},
    # ── Currency ─────────────────────────────────────────────────
    {'key': 'currency.convert',     'category': 'currency','priority':'high',    'description': 'Convert currency'},
    {'key': 'currency.from',        'category': 'currency','priority':'high',    'description': 'Convert from'},
    {'key': 'currency.to',          'category': 'currency','priority':'high',    'description': 'Convert to'},
    {'key': 'currency.amount',      'category': 'currency','priority':'high',    'description': 'Amount label'},
    {'key': 'currency.rate',        'category': 'currency','priority':'normal',  'description': 'Exchange rate'},
    # ── Error messages ───────────────────────────────────────────
    {'key': 'error.notfound',       'category': 'error',  'priority': 'high',    'description': '404 page'},
    {'key': 'error.server',         'category': 'error',  'priority': 'critical','description': '500 error'},
    {'key': 'error.unauthorized',   'category': 'error',  'priority': 'critical','description': '401 error'},
    {'key': 'error.forbidden',      'category': 'error',  'priority': 'high',    'description': '403 error'},
    {'key': 'error.timeout',        'category': 'error',  'priority': 'high',    'description': 'Request timeout'},
    {'key': 'error.network',        'category': 'error',  'priority': 'high',    'description': 'Network error'},
    {'key': 'error.validation',     'category': 'error',  'priority': 'high',    'description': 'Validation error'},
    # ── Pagination ───────────────────────────────────────────────
    {'key': 'pagination.next',      'category': 'pagination','priority':'high',  'description': 'Next page'},
    {'key': 'pagination.prev',      'category': 'pagination','priority':'high',  'description': 'Previous page'},
    {'key': 'pagination.of',        'category': 'pagination','priority':'normal', 'description': 'Page X of Y'},
    {'key': 'pagination.items',     'category': 'pagination','priority':'normal', 'description': 'Items count'},
    {'key': 'pagination.showing',   'category': 'pagination','priority':'normal', 'description': 'Showing X-Y'},
    # ── Form ─────────────────────────────────────────────────────
    {'key': 'form.submit',          'category': 'form',   'priority': 'critical','description': 'Submit button'},
    {'key': 'form.cancel',          'category': 'form',   'priority': 'high',    'description': 'Cancel button'},
    {'key': 'form.save',            'category': 'form',   'priority': 'high',    'description': 'Save button'},
    {'key': 'form.reset',           'category': 'form',   'priority': 'normal',  'description': 'Reset form'},
    {'key': 'form.required',        'category': 'form',   'priority': 'high',    'description': 'Required field'},
    {'key': 'form.invalid',         'category': 'form',   'priority': 'high',    'description': 'Invalid input'},
    # ── Table / List ─────────────────────────────────────────────
    {'key': 'table.empty',          'category': 'table',  'priority': 'high',    'description': 'Empty state'},
    {'key': 'table.loading',        'category': 'table',  'priority': 'high',    'description': 'Loading state'},
    {'key': 'table.search',         'category': 'table',  'priority': 'normal',  'description': 'Search placeholder'},
    # ── Date / Number format ─────────────────────────────────────
    {'key': 'date.format',          'category': 'format', 'priority': 'normal',  'description': 'Date format pattern'},
    {'key': 'date.today',           'category': 'format', 'priority': 'normal',  'description': 'Today label'},
    {'key': 'date.yesterday',       'category': 'format', 'priority': 'normal',  'description': 'Yesterday label'},
    {'key': 'number.format',        'category': 'format', 'priority': 'normal',  'description': 'Number format pattern'},
    # ── Status ───────────────────────────────────────────────────
    {'key': 'status.active',        'category': 'status', 'priority': 'high',    'description': 'Active status'},
    {'key': 'status.inactive',      'category': 'status', 'priority': 'high',    'description': 'Inactive status'},
    {'key': 'status.pending',       'category': 'status', 'priority': 'high',    'description': 'Pending status'},
    {'key': 'status.completed',     'category': 'status', 'priority': 'high',    'description': 'Completed status'},
    {'key': 'status.cancelled',     'category': 'status', 'priority': 'high',    'description': 'Cancelled status'},
    {'key': 'status.failed',        'category': 'status', 'priority': 'high',    'description': 'Failed status'},
    # ── Notification ─────────────────────────────────────────────
    {'key': 'notification.new',     'category': 'notification','priority':'high', 'description': 'New notification'},
    {'key': 'notification.mark_read','category':'notification','priority':'normal','description':'Mark as read'},
    {'key': 'notification.all',     'category': 'notification','priority':'normal','description':'All notifications'},
    # ── User ─────────────────────────────────────────────────────
    {'key': 'user.profile',         'category': 'user',   'priority': 'high',    'description': 'Profile label'},
    {'key': 'user.dashboard',       'category': 'user',   'priority': 'critical','description': 'Dashboard label'},
    {'key': 'user.settings',        'category': 'user',   'priority': 'high',    'description': 'Settings label'},
    {'key': 'user.account',         'category': 'user',   'priority': 'high',    'description': 'Account label'},
    {'key': 'user.preferences',     'category': 'user',   'priority': 'normal',  'description': 'Preferences label'},
    # ── Language / Country ───────────────────────────────────────
    {'key': 'language.switch',      'category': 'language','priority':'high',    'description': 'Switch language'},
    {'key': 'language.select',      'category': 'language','priority':'high',    'description': 'Select language'},
    {'key': 'language.current',     'category': 'language','priority':'normal',  'description': 'Current language'},
    {'key': 'country.select',       'category': 'country','priority':'high',     'description': 'Select country'},
]


class Command(BaseCommand):
    help = 'CPAlead earning site translation keys seed করে'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Existing records overwrite')
        parser.add_argument('--category', help='Only seed specific category')

    def handle(self, *args, **options):
        from localization.models.core import TranslationKey
        force = options.get('force', False)
        category = options.get('category')
        keys = CPALEAD_KEYS
        if category:
            keys = [k for k in keys if k['category'] == category]

        created = updated = skipped = 0
        for key_data in keys:
            k = key_data['key']
            defaults = {
                'description': key_data['description'],
                'category': key_data['category'],
                'priority': key_data.get('priority', 'normal'),
            }
            if force:
                _, was_created = TranslationKey.objects.update_or_create(key=k, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1
            else:
                _, was_created = TranslationKey.objects.get_or_create(key=k, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Translation keys seeded: {created} created, {updated} updated, {skipped} skipped'
        ))
        self.stdout.write(f'Total keys: {len(CPALEAD_KEYS)}')
        cats = {}
        for k in CPALEAD_KEYS:
            cats[k['category']] = cats.get(k['category'], 0) + 1
        for cat, count in sorted(cats.items()):
            self.stdout.write(f'  {cat}: {count} keys')
