# api/wallet/EXTENSION_GUIDE.py
"""
╔══════════════════════════════════════════════════════════════════╗
║             WALLET EXTENSION GUIDE                              ║
║   "এক কাজের জন্য একটাই মালিক"                                 ║
║   Core code কখনো touch করতে হবে না                            ║
╚══════════════════════════════════════════════════════════════════╝

PRINCIPLE: Open-Closed Principle (SOLID)
  - Core wallet code: CLOSED for modification
  - New features: OPEN for extension via plugins/hooks/events

════════════════════════════════════════════════════════════════════
HOW TO ADD A NEW FEATURE IN 3 STEPS:
════════════════════════════════════════════════════════════════════

STEP 1: Create your feature file (zero core changes)
  Example: I want to add "split payment" feature

  Create: api/wallet/split_payment.py
  
  class SplitPaymentService:
      @staticmethod
      def create_split(payer, recipients, amounts, description):
          from .services.core.WalletService import WalletService
          from .event_bus import event_bus
          for recipient, amount in zip(recipients, amounts):
              wallet = WalletService.get_or_create(recipient)
              WalletService.credit(wallet, amount, txn_type="split_payment")
          return {"success": True}


STEP 2: Register via plugin (zero core changes)
  In your NEW app's apps.py:
  
  from api.wallet.plugins import plugin_registry
  
  class SplitPaymentPlugin(WalletPlugin):
      name = "split_payment"
      def on_credit(self, wallet, amount, txn):
          if txn.type == "split_payment":
              pass  # custom logic

  plugin_registry.register(SplitPaymentPlugin())


STEP 3: Hook into lifecycle (zero core changes)
  from api.wallet.hooks import wallet_hooks
  
  @wallet_hooks.after("credit")
  def split_payment_after_credit(wallet=None, amount=None, **kwargs):
      pass  # Your logic here


════════════════════════════════════════════════════════════════════
EXTENSION POINTS (where you can plug in):
════════════════════════════════════════════════════════════════════

1. EVENTS (event_bus.py):
   Subscribe to any wallet event:
   
   @event_bus.subscribe(WalletCredited)
   def my_handler(event: WalletCredited):
       pass  # Called every time wallet is credited

   Available events: WalletCredited, WalletDebited, WalletLocked,
   WithdrawalRequested, WithdrawalCompleted, EarningAdded,
   KYCApproved, FraudDetected, StreakMilestone, etc.

2. HOOKS (hooks.py):
   Pre/post hooks on operations:
   
   @wallet_hooks.before("credit")    # Before crediting
   @wallet_hooks.after("credit")     # After crediting
   @wallet_hooks.before("withdrawal") # Before withdrawal
   @wallet_hooks.after("withdrawal")  # After withdrawal
   @wallet_hooks.after("withdrawal_complete") # After completion

3. PLUGINS (plugins.py):
   Full lifecycle plugin:
   
   class MyPlugin(WalletPlugin):
       name = "my_plugin"
       def on_wallet_created(self, wallet): pass
       def on_credit(self, wallet, amount, txn): pass
       def on_debit(self, wallet, amount, txn): pass
       def validate_withdrawal(self, wallet, amount, method): 
           return None  # or "error message" to block

4. SIGNALS (Django signals):
   In your app's signals.py:
   
   from django.db.models.signals import post_save
   from api.wallet.models.core import WalletTransaction
   
   @receiver(post_save, sender=WalletTransaction)
   def my_txn_handler(sender, instance, created, **kwargs):
       pass

5. FEATURE FLAGS (feature_flags.py):
   Gate your feature:
   
   from api.wallet.feature_flags import flags
   
   if flags.is_enabled("my_feature", user=user):
       # Your code runs only when flag enabled

6. GATEWAY REGISTRY (registry.py):
   Add a new payment gateway:
   
   from api.wallet.registry import wallet_registry
   wallet_registry.register_gateway("my_gateway", MyGatewayService)

════════════════════════════════════════════════════════════════════
ADDING A NEW GATEWAY (e.g., Upay, bKash 2.0, etc.):
════════════════════════════════════════════════════════════════════

1. Create: api/wallet/services/gateway/MyGatewayService.py
2. Add to: api/wallet/services/gateway/__init__.py
3. Add to: api/wallet/registry.py (auto-registered)
4. Add to: api/wallet/integration/webhooks_integration.py (handle_mygw)
5. Add to: api/wallet/celery_beat_config.py if needs scheduled tasks
6. Add feature flag: DEFAULT_FLAGS["withdrawal_mygw"] = True

ZERO changes to: models, views, serializers, admin, tasks, signals
════════════════════════════════════════════════════════════════════

ADDING A NEW 2030 FEATURE:
════════════════════════════════════════════════════════════════════

Step 1: The stub file already exists (e.g., quantum_encryption.py)
Step 2: Implement the stub methods
Step 3: Update feature flag: flags.set_global("quantum_encryption", True)
Step 4: The rest of the system picks it up automatically

Example: Enabling CBDC when Bangladesh launches Digital Taka:
  1. Set settings.BB_CBDC_API_KEY = "your_key"
  2. Set settings.CBDC_ENABLED = True
  3. Run: python manage.py migrate (adds cbdc_balance field)
  4. Run: flags.set_global("cbdc_enabled", True)
  5. Done! No other changes needed.

════════════════════════════════════════════════════════════════════
WHAT FILES TO NEVER MODIFY:
════════════════════════════════════════════════════════════════════

CLOSED (never touch):
  - models/core.py              (Wallet + WalletTransaction)
  - services/core/WalletService.py  (core credit/debit logic)
  - services/ledger/LedgerService.py (double-entry accounting)
  - migrations/                 (never edit, always new migration)
  - event_bus.py                (event infrastructure)
  - encryption.py               (security — audit required)

OPEN (add new methods, never remove/change existing):
  - plugins.py     (add new plugin class)
  - hooks.py       (add new hook)
  - registry.py    (register new gateway)
  - feature_flags.py (add new flag to DEFAULT_FLAGS)
  - choices.py     (add new choices)
  - constants.py   (add new constants)
  - urls.py        (add new URL patterns)

EXTENSION (create new file instead of modifying):
  - Instead of modifying views.py → create views_extra.py
  - Instead of modifying services.py → create services_extra.py
  - Instead of modifying tasks.py → create tasks_cap.py / tasks_extra.py
  - Instead of modifying signals.py → create signals_cap.py / signals_kb.py

════════════════════════════════════════════════════════════════════
2030 FEATURE ACTIVATION CHECKLIST:
════════════════════════════════════════════════════════════════════

CBDC (2026-2027):
  [ ] Set BB_CBDC_API_KEY in settings
  [ ] Run: python manage.py makemigrations wallet (cbdc_balance field)
  [ ] flags.set_global("cbdc_enabled", True)
  [ ] Test: python manage.py test api.wallet.tests.test_cbdc

BNPL (2026):
  [ ] Enable: BNPL is code-complete in bnpl_service.py
  [ ] Add BNPLPlan model to models_cpalead_extra.py
  [ ] Run migrations
  [ ] flags.set_global("bnpl_enabled", True)

Virtual Cards (2026):
  [ ] Set STRIPE_SECRET_KEY (Stripe Issuing enabled)
  [ ] Set VIRTUAL_CARDS_ENABLED = True
  [ ] flags.set_global("virtual_cards", True)
  [ ] Test card issuance

Open Banking (2026):
  [ ] Set OPEN_BANKING_CLIENT_ID + SECRET
  [ ] Set OPEN_BANKING_ENABLED = True
  [ ] Configure redirect URI
  [ ] Test OAuth2 flow

Biometric (2025):
  [ ] Set BIOMETRIC_ENABLED = True
  [ ] Configure FIDO2/WebAuthn on frontend
  [ ] flags.set_global("biometric_auth", True)

Credit Score (2026):
  [ ] Already works with existing data
  [ ] Enable: flags.set_global("credit_score", True)
  [ ] Optional: integrate external credit bureau API

Quantum Encryption (2030):
  [ ] pip install liboqs-python
  [ ] Implement quantum_encryption.py methods
  [ ] Run migration to re-encrypt existing data
  [ ] Test thoroughly before enabling

════════════════════════════════════════════════════════════════════
"""
# This file is the extension guide — import nothing, just documentation
__version__    = "2030.1.0"
__last_update__ = "2025-04-23"
__author__     = "Wallet System"
__principle__  = "Open-Closed: closed for modification, open for extension"
