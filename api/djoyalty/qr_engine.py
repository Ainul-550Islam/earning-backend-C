# api/djoyalty/qr_engine.py
"""
Djoyalty QR Engine -- Generate and verify QR codes for loyalty।
Customer loyalty card QR, earn QR (scan to earn), redeem QR।
pip install qrcode[pil] Pillow
"Do not summarize or skip any logic. Provide the full code."
"""
import base64
import hashlib
import logging
import secrets
from io import BytesIO
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class LoyaltyQREngine:
    """
    QR code generation and verification for loyalty।

    Types:
    1. Customer Card QR -- customer's unique ID QR for POS scan
    2. Earn QR -- merchant's QR that customers scan to earn points
    3. Redemption QR -- one-time QR for redeeming a reward
    4. SmartLink QR -- QR for SmartLink URLs

    Usage:
        qr = LoyaltyQREngine()
        # Customer card
        qr_b64 = qr.generate_customer_card_qr(customer)
        # Earn QR for a store
        qr_b64 = qr.generate_earn_qr(store_id='STORE1', points=50)
        # Verify a scanned QR
        result = qr.verify_qr(scanned_data)
    """

    QR_VERSION = '1'
    SECRET = getattr(settings, 'DJOYALTY_QR_SECRET', 'djoyalty-qr-secret-2025')

    def _sign(self, payload: str) -> str:
        """Create HMAC signature for QR data।"""
        return hashlib.hmac(
            self.SECRET.encode(),
            payload.encode(),
            'sha256',
        ).hexdigest()[:16]

    def generate_customer_card_qr(self, customer, size: int = 300) -> str:
        """Generate base64 QR code PNG for customer loyalty card।"""
        payload = f'CARD:v{self.QR_VERSION}:{customer.code}:{self._sign(customer.code)}'
        return self._render_qr(payload, size=size)

    def generate_earn_qr(self, store_id: str, points: int, campaign_id: int = None,
                          single_use: bool = False, size: int = 300) -> dict:
        """
        Generate earn QR for a merchant location।
        Customer scans this QR -> earns points।
        """
        token = secrets.token_urlsafe(8)
        payload_data = f'EARN:v{self.QR_VERSION}:{store_id}:{points}:{token}'
        sig = self._sign(payload_data)
        payload = f'{payload_data}:{sig}'

        # Store token in cache
        try:
            from django.core.cache import cache
            cache_key = f'djoyalty:qr:earn:{token}'
            cache.set(cache_key, {
                'store_id': store_id,
                'points': points,
                'campaign_id': campaign_id,
                'single_use': single_use,
                'created_at': timezone.now().isoformat(),
                'used': False,
            }, timeout=86400)  # 24h
        except Exception:
            pass

        return {
            'token': token,
            'qr_base64': self._render_qr(payload, size=size),
            'payload': payload,
        }

    def generate_redemption_qr(self, voucher_code: str, customer_code: str,
                                 size: int = 300) -> str:
        """Generate one-time redemption QR for a voucher।"""
        payload = f'REDEEM:v{self.QR_VERSION}:{customer_code}:{voucher_code}:{self._sign(voucher_code)}'
        return self._render_qr(payload, size=size)

    def generate_smartlink_qr(self, slug: str, base_url: str = '', size: int = 300) -> str:
        """Generate QR for a SmartLink URL।"""
        url = base_url or f'/ref/{slug}/'
        return self._render_qr(url, size=size)

    def verify_qr(self, scanned_data: str) -> dict:
        """
        Verify and parse a scanned QR code।
        Returns: {'type': 'CARD'/'EARN'/'REDEEM', 'valid': bool, ...}
        """
        try:
            if not scanned_data:
                return {'valid': False, 'error': 'Empty QR data'}

            parts = scanned_data.split(':')
            qr_type = parts[0] if parts else ''

            if qr_type == 'CARD':
                # Format: CARD:v1:CUSTOMER_CODE:SIG
                if len(parts) < 4:
                    return {'valid': False, 'error': 'Invalid CARD QR format'}
                customer_code = parts[2]
                sig = parts[3]
                expected_sig = self._sign(customer_code)
                if sig != expected_sig:
                    return {'valid': False, 'error': 'Invalid QR signature'}
                return {'valid': True, 'type': 'CARD', 'customer_code': customer_code}

            elif qr_type == 'EARN':
                # Format: EARN:v1:STORE_ID:POINTS:TOKEN:SIG
                if len(parts) < 6:
                    return {'valid': False, 'error': 'Invalid EARN QR format'}
                token = parts[4]
                sig = parts[5]
                payload_data = ':'.join(parts[:5])
                expected_sig = self._sign(payload_data)
                if sig != expected_sig:
                    return {'valid': False, 'error': 'Invalid QR signature'}

                # Check cache for token validity
                try:
                    from django.core.cache import cache
                    data = cache.get(f'djoyalty:qr:earn:{token}')
                    if not data:
                        return {'valid': False, 'error': 'QR expired or already used'}
                    if data.get('single_use') and data.get('used'):
                        return {'valid': False, 'error': 'QR already used'}
                    return {
                        'valid': True,
                        'type': 'EARN',
                        'store_id': data['store_id'],
                        'points': data['points'],
                        'token': token,
                    }
                except Exception:
                    return {'valid': True, 'type': 'EARN', 'store_id': parts[2],
                            'points': int(parts[3]), 'token': token}

            elif qr_type == 'REDEEM':
                if len(parts) < 5:
                    return {'valid': False, 'error': 'Invalid REDEEM QR format'}
                customer_code = parts[2]
                voucher_code = parts[3]
                sig = parts[4]
                if sig != self._sign(voucher_code):
                    return {'valid': False, 'error': 'Invalid QR signature'}
                return {'valid': True, 'type': 'REDEEM',
                        'customer_code': customer_code, 'voucher_code': voucher_code}

            return {'valid': False, 'error': f'Unknown QR type: {qr_type}'}
        except Exception as e:
            logger.error('LoyaltyQREngine.verify_qr error: %s', e)
            return {'valid': False, 'error': str(e)}

    @staticmethod
    def _render_qr(data: str, size: int = 300) -> str:
        """Render QR code as base64 PNG string।"""
        try:
            import qrcode
            from PIL import Image

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')

            # Resize to requested size
            img = img.resize((size, size), Image.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
        except ImportError:
            logger.warning('qr_engine: qrcode[pil] not installed. pip install "qrcode[pil]"')
            # Return a placeholder base64 string
            return base64.b64encode(data.encode()).decode()
        except Exception as e:
            logger.error('LoyaltyQREngine._render_qr error: %s', e)
            return ''
