# Marketplace Pricing Models

## Commission Structure

### Default Rates
| Category | Commission Rate |
|----------|----------------|
| Electronics | 10% |
| Fashion | 12% |
| Food & Grocery | 5% |
| Books | 8% |
| Beauty | 15% |
| Global Default | 10% |

### Priority Order
1. **Seller-specific override** (set via admin)
2. **Category commission** (`CommissionConfig`)
3. **Parent category commission** (tree walk)
4. **Global default** (10%)

### Commission Formula
```
commission_amount = order_item.subtotal × commission_rate / 100
seller_net        = order_item.subtotal - commission_amount - platform_fee
```

## Platform Fees

### Payment Processing Fees
| Method | Fee |
|--------|-----|
| bKash  | 1.5% |
| Nagad  | 1.5% |
| Rocket | 1.8% |
| Card   | 2.5% + 10 BDT |
| COD    | 0% |

### Withdrawal Fees
| Amount | Fee |
|--------|-----|
| < 500 BDT | 20 BDT flat |
| 500–2000 BDT | 30 BDT flat |
| > 2000 BDT | 1.5% |

## Escrow & Payout

### Escrow Window
- **Hold period**: 7 days after delivery
- **Dispute window**: 14 days after delivery
- **Auto-release**: Day 7 if no dispute

### Payout Schedule Options
| Frequency | Description |
|-----------|-------------|
| Instant | Released immediately after escrow unlock |
| Daily | Every day at 9:00 AM |
| Weekly | Every Saturday at 9:00 AM |
| Monthly | 1st of each month |

## Loyalty Program

### Earning Rate
- 1 BDT spent = 1 point
- Tier multiplier applies

### Tier Multipliers
| Tier | Spend Required | Multiplier |
|------|---------------|-----------|
| Bronze | 0 BDT | 1.0× |
| Silver | 5,000 BDT | 1.25× |
| Gold | 20,000 BDT | 1.5× |
| Platinum | 50,000 BDT | 2.0× |

### Redemption Rate
100 points = 10 BDT (max 20% of order)

## Shipping Rates (BDT)

| Zone | Standard | Express |
|------|----------|---------|
| Inside Dhaka | 60 | 110 |
| Outside Dhaka | 110 | 160 |
| Divisional City | 100 | 150 |
| Remote Area | 150 | 200 |

**Free shipping threshold**: 500 BDT
**Weight surcharge**: 20 BDT per kg (after first 0.5 kg)
