# Redemption Guide — Djoyalty

## Overview
Customer অর্জিত points দিয়ে rewards redeem করতে পারে।
Redemption types: voucher, cashback, product, giftcard, donation।

## Redemption Flow
```
Customer requests redemption
       ↓
Points deducted from balance (locked)
       ↓
RedemptionRequest created (status=pending)
       ↓
Auto-approve (if ≤ 1000 pts) OR Manual review
       ↓
Approved → Reward delivered
Rejected → Points refunded
```

## Redemption Types
| Type | Description |
|---|---|
| `cashback` | Currency credit to account |
| `voucher` | Discount voucher code |
| `product` | Physical/digital product |
| `giftcard` | Gift card issuance |
| `donation` | Charitable donation |

## Minimum Redemption
- Default minimum: **100 points**
- Maximum: **100,000 points** per request
- Auto-approve threshold: **1,000 points**

## Voucher System
### Types
| Type | Description |
|---|---|
| `percent` | % discount (e.g., 15% off) |
| `fixed` | Fixed amount off (e.g., ৳50 off) |
| `free_shipping` | Free shipping |
| `bogo` | Buy one get one |

### Generate Voucher (Admin)
```python
from djoyalty.services.redemption.VoucherService import VoucherService
voucher = VoucherService.generate_voucher(customer, 'percent', Decimal('15'))
# Returns Voucher with unique code like: ABCD-EFGH-IJKL
```

### Use Voucher (Checkout)
```python
redemption = VoucherService.use_voucher('ABCD-EFGH-IJKL', customer, order_reference='ORD-001')
```

### Validate Voucher (API)
```
GET /api/djoyalty/vouchers/validate/?code=ABCD-EFGH-IJKL
```

## Gift Card System
### Issue
```python
from djoyalty.services.redemption.GiftCardService import GiftCardService
gc = GiftCardService.issue(Decimal('500'), issued_to=customer, validity_days=365)
```

### Redeem (Partial)
```python
gc = GiftCardService.redeem('GC-ABCD-EFGH-IJKL-MNOP', Decimal('200'))
# Partial redemption supported — remaining_value updates
```

## Reward Catalog
```python
from djoyalty.services.redemption.RewardCatalogService import RewardCatalogService
available = RewardCatalogService.get_available_rewards(customer)
summary = RewardCatalogService.get_reward_summary(customer)
```

## API Endpoints
```
POST /api/djoyalty/redemptions/redeem/         # Create request
POST /api/djoyalty/redemptions/{id}/approve/   # Approve (Admin)
POST /api/djoyalty/redemptions/{id}/reject/    # Reject (Admin)
POST /api/djoyalty/vouchers/generate/          # Generate voucher (Admin)
POST /api/djoyalty/vouchers/use/               # Use voucher
GET  /api/djoyalty/vouchers/validate/?code=    # Validate
POST /api/djoyalty/gift-cards/issue/           # Issue gift card (Admin)
POST /api/djoyalty/gift-cards/redeem/          # Redeem gift card
```

## Celery Tasks
```
djoyalty.auto_approve_redemptions        # Every 15 min: auto-approve small requests
djoyalty.expire_old_pending_redemptions  # Daily: cancel 30+ day old pending
djoyalty.expire_vouchers                 # Daily: mark expired vouchers
djoyalty.expire_gift_cards               # Daily: mark expired gift cards
```
