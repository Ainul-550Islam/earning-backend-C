# Integration Guide

## Payment Gateways

### bKash
```python
from api.marketplace.INTEGRATIONS.payment_gateway_integration import BkashIntegration

gateway = BkashIntegration(
    app_key="YOUR_APP_KEY",
    app_secret="YOUR_APP_SECRET",
    username="YOUR_USERNAME",
    password="YOUR_PASSWORD",
    sandbox=True,  # False for production
)
result = gateway.create_payment(amount=500, phone="01700000001", reference="ORD12345678")
```

### Steadfast Courier
```python
from api.marketplace.INTEGRATIONS.shipping_carrier_integration import SteadfastCourier

courier = SteadfastCourier(api_key="YOUR_KEY", secret_key="YOUR_SECRET")
result = courier.create_order({
    "invoice": "ORD12345678",
    "recipient_name": "John Doe",
    "recipient_phone": "01700000001",
    "recipient_address": "123 Dhaka Road",
    "cod_amount": 500,
})
```

## Webhook Setup

Set your webhook URL in tenant settings. Events dispatched:
- `order.placed`
- `order.delivered`
- `payment.success`
- `refund.approved`

Webhook payloads are signed with HMAC-SHA256. Verify:
```python
import hmac, hashlib
expected = hmac.new(YOUR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
assert expected == request.headers["X-Marketplace-Signature"]
```
