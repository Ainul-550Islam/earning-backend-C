# api/payment_gateways/integration_system/data_bridge.py
# Data bridge — bidirectional data sync between payment_gateways and external apps

from decimal import Decimal
from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class DataBridgeSync:
    """
    Bidirectional data synchronization between payment_gateways and other apps.

    Handles:
        - Pulling user balance from api.wallet into payment_gateways
        - Pushing transaction data to api.analytics
        - Syncing publisher stats with api.publisher_tools
        - Importing advertiser budgets from api.advertiser_portal
        - Syncing conversion data with api.postback_engine

    All operations are idempotent — safe to call multiple times.
    """

    def pull_user_balance(self, user) -> Decimal:
        """
        Get user's current balance from api.wallet.
        Falls back to user.balance field if wallet app unavailable.
        """
        # Try api.wallet first
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.select_for_update().get(user=user)
            return wallet.available_balance
        except ImportError:
            pass
        except Exception:
            pass

        # Try api.wallet alternate model name
        try:
            from api.wallet.models import UserWallet
            wallet = UserWallet.objects.get(user=user)
            return Decimal(str(wallet.balance or '0'))
        except Exception:
            pass

        # Fallback: user.balance field (direct)
        return Decimal(str(getattr(user, 'balance', '0') or '0'))

    def push_transaction_to_analytics(self, transaction) -> bool:
        """Push a GatewayTransaction to api.analytics."""
        try:
            from api.analytics.events import track
            track('payment_transaction', {
                'user_id':          transaction.user_id,
                'gateway':          transaction.gateway,
                'transaction_type': transaction.transaction_type,
                'amount':           float(transaction.amount),
                'currency':         transaction.currency,
                'status':           transaction.status,
                'reference_id':     transaction.reference_id,
            })
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f'DataBridgeSync.push_transaction_to_analytics: {e}')
            return False

    def pull_advertiser_budget(self, advertiser) -> Dict:
        """Get advertiser's campaign budget from api.advertiser_portal."""
        try:
            from api.advertiser_portal.models import AdvertiserAccount
            account = AdvertiserAccount.objects.get(user=advertiser)
            return {
                'total_budget':  float(account.total_budget or 0),
                'spent':         float(account.spent or 0),
                'remaining':     float((account.total_budget or 0) - (account.spent or 0)),
                'currency':      account.currency,
            }
        except ImportError:
            # Fall back to payment_gateways advertiser profile
            try:
                from api.payment_gateways.publisher.models import AdvertiserProfile
                profile = AdvertiserProfile.objects.get(user=advertiser)
                return {
                    'total_budget': float(profile.balance),
                    'spent':        float(profile.total_spent),
                    'remaining':    float(profile.available_balance),
                    'currency':     profile.currency,
                }
            except Exception:
                return {'total_budget': 0, 'spent': 0, 'remaining': 0, 'currency': 'USD'}
        except Exception as e:
            logger.debug(f'DataBridgeSync.pull_advertiser_budget: {e}')
            return {'total_budget': 0, 'spent': 0, 'remaining': 0, 'currency': 'USD'}

    def push_publisher_stats(self, publisher, stats: dict) -> bool:
        """Push publisher stats to api.publisher_tools."""
        try:
            from api.publisher_tools.services import PublisherStatsService
            PublisherStatsService().update(publisher, stats)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f'DataBridgeSync.push_publisher_stats: {e}')
            return False

    def sync_conversion_to_postback(self, conversion) -> bool:
        """Sync conversion data to api.postback_engine for postback firing."""
        try:
            from api.postback_engine.models import ConversionPostback
            ConversionPostback.objects.get_or_create(
                external_id=conversion.conversion_id,
                defaults={
                    'user':       conversion.publisher,
                    'payout':     conversion.payout,
                    'status':     conversion.status,
                    'click_id':   conversion.click_id_raw,
                    'offer_id':   conversion.offer_id,
                }
            )
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f'DataBridgeSync.sync_conversion_to_postback: {e}')
            return False

    def pull_kyc_status(self, user) -> dict:
        """Get user's KYC verification status from api.kyc."""
        try:
            from api.kyc.models import KYCProfile
            kyc = KYCProfile.objects.get(user=user)
            return {
                'is_verified':  kyc.status == 'approved',
                'status':       kyc.status,
                'level':        getattr(kyc, 'kyc_level', 1),
                'can_withdraw': kyc.status == 'approved',
                'max_withdrawal': None,  # No limit if verified
            }
        except ImportError:
            return {'is_verified': True, 'status': 'not_required', 'can_withdraw': True}
        except Exception:
            return {'is_verified': False, 'status': 'pending', 'can_withdraw': False}

    def pull_user_fraud_score(self, user) -> int:
        """Get user's fraud score from api.fraud_detection."""
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.get(user=user)
            return profile.risk_score
        except ImportError:
            return 0
        except Exception:
            return 0

    def sync_referral_data(self, referral_code: str, new_user) -> bool:
        """Sync referral signup with api.referral if available."""
        try:
            # Try your existing api.referral first
            from api.referral.services import ReferralService
            return ReferralService().register(new_user, referral_code)
        except ImportError:
            # Fall back to payment_gateways referral
            try:
                from api.payment_gateways.referral.ReferralEngine import ReferralEngine
                return ReferralEngine().register_referral(new_user, referral_code)
            except Exception:
                return False


class ModelTranslator:
    """
    Translates between different model formats across apps.
    Ensures payment_gateways can work with any wallet/notification app structure.
    """

    def get_wallet_model_class(self):
        """Detect which wallet model class your app uses."""
        candidates = [
            ('api.wallet.models', 'Wallet'),
            ('api.wallet.models', 'UserWallet'),
            ('api.wallet.models', 'PublisherWallet'),
        ]
        for module_path, class_name in candidates:
            try:
                mod = __import__(module_path, fromlist=[class_name])
                return getattr(mod, class_name)
            except (ImportError, AttributeError):
                continue
        return None

    def get_notification_service(self):
        """Detect which notification service your app uses."""
        candidates = [
            ('api.notifications.services', 'NotificationService'),
            ('api.notifications.service', 'NotificationService'),
            ('api.notifications.tasks', 'send_notification'),
        ]
        for module_path, attr in candidates:
            try:
                mod = __import__(module_path, fromlist=[attr])
                return getattr(mod, attr)
            except (ImportError, AttributeError):
                continue
        return None
