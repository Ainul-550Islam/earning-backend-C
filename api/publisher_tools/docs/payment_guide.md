# Payment Guide

## Payment Methods Supported

### Bangladesh
| Method | Min Payout | Processing Fee | Processing Time |
|--------|-----------|----------------|----------------|
| bKash | $5 | $0.50 flat | 1-2 business days |
| Nagad | $5 | $0.50 flat | 1-2 business days |
| Rocket | $5 | $0.50 flat | 1-2 business days |

### International
| Method | Min Payout | Processing Fee | Processing Time |
|--------|-----------|----------------|----------------|
| PayPal | $10 | $1.00 + 2% | 1-3 business days |
| Payoneer | $50 | $3.00 flat | 2-5 business days |
| Bank Transfer | $100 | $5.00 flat | 5-10 business days |
| Wire Transfer | $500 | $25.00 flat | 3-7 business days |
| USDT (TRC-20) | $10 | $1.00 flat | Same day |
| Bitcoin | $50 | $5.00 flat | 1-2 business days |

## Payment Schedule

### Standard (Monthly)
- Earnings confirmed: Month end
- Invoice generated: 2nd of next month
- Payment sent: 15th of next month
- Funds arrive: 18th-20th

### Premium (Bi-Monthly)
- Payments sent: 1st and 15th of each month

### Enterprise (Weekly)
- Payments sent every Monday

## Setting Up Payment

### 1. Add Payment Method
```bash
POST /api/publisher-tools/payout-thresholds/
{
    "payment_method": "bkash",
    "minimum_threshold": "5.00",
    "payment_frequency": "monthly",
    "account_number": "01XXXXXXXXX",
    "account_holder_name": "Your Name"
}
```

### 2. Verify Payment Method
Admin will verify your account within 2-3 business days.
You'll receive a small test deposit to confirm.

### 3. Request Payout (On-Demand)
```bash
POST /api/publisher-tools/payments/payout-request/
{
    "amount": "50.00",
    "bank_account_id": "YOUR_ACCOUNT_UUID",
    "notes": "Monthly payout request"
}
```

## Invoice Structure

```
Gross Revenue:          $100.00
Publisher Share (70%):  $70.00
IVT Deduction:         -$2.00
Processing Fee:        -$0.50
Withholding Tax:       -$7.00  (BD: 10%)
─────────────────────────────
Net Payable:            $60.50
```

## Withholding Tax Rates by Country
| Country | Rate | Notes |
|---------|------|-------|
| Bangladesh | 10% | Standard rate |
| India | 10% | Standard rate |
| USA | 30% | Reduced with W-8BEN treaty |
| UAE | 0% | Tax-free |
| Singapore | 0% | Tax-free |

**Reduce US withholding**: Submit W-8BEN form for treaty benefits (BD: 10% instead of 30%)

## Disputing an Invoice
1. Navigate to Invoices
2. Click "Dispute" on the invoice
3. Select dispute type
4. Provide evidence
5. Submit within 5 business days of issue date

## Payment Status Meanings
- `pending`: Payout request submitted, awaiting review
- `approved`: Admin approved, awaiting processing
- `processing`: Payment being sent
- `completed`: Funds sent to your account
- `failed`: Payment failed — check account details
- `rejected`: Did not meet eligibility criteria
