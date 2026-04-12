# Revenue Models Documentation

## Overview

monetization_tools supports multiple revenue models simultaneously.
All calculations use Python `Decimal` for financial accuracy.

---

## 1. CPM (Cost Per Mille / 1000 Impressions)

**Formula:** `Revenue = (Impressions / 1000) × eCPM`

```python
from api.monetization_tools.REVENUE_MODELS.cpm_calculator import CPMCalculator

revenue = CPMCalculator.revenue(impressions=50000, ecpm=Decimal("2.50"))
# = 125.000000

ecpm = CPMCalculator.ecpm(revenue=Decimal("125"), impressions=50000)
# = 2.5000
```

**Typical eCPM Ranges (USD):**
| Format | Tier 1 (US/UK) | Tier 2 (IN/BR) | Tier 3 (BD/PK) |
|--------|---------------|---------------|---------------|
| Rewarded Video | $5–$40 | $1–$5 | $0.20–$0.80 |
| Interstitial | $2–$15 | $0.50–$2 | $0.10–$0.40 |
| Banner | $0.50–$3 | $0.10–$0.50 | $0.05–$0.20 |
| Native | $1–$5 | $0.30–$1.50 | $0.10–$0.30 |

---

## 2. CPC (Cost Per Click)

**Formula:** `Revenue = Clicks × CPC`

```python
from api.monetization_tools.REVENUE_MODELS.cpc_calculator import CPCCalculator

revenue = CPCCalculator.revenue(clicks=200, cpc=Decimal("0.25"))
# = 50.000000

ecpm = CPCCalculator.to_ecpm(cpc=Decimal("0.25"), ctr_pct=Decimal("2.0"))
# effective eCPM = 5.0000
```

---

## 3. CPA (Cost Per Action)

**Formula:** `Revenue = Conversions × CPA`

```python
from api.monetization_tools.REVENUE_MODELS.cpa_calculator import CPACalculator

revenue = CPACalculator.revenue(conversions=50, cpa=Decimal("1.50"))
# = 75.000000

roas = CPACalculator.roas(revenue=Decimal("500"), spend=Decimal("200"))
# = 2.5000 (250% ROAS)
```

---

## 4. CPI (Cost Per Install)

```python
from api.monetization_tools.REVENUE_MODELS.cpi_calculator import CPICalculator

revenue = CPICalculator.revenue(installs=100, cpi=Decimal("0.75"))
install_rate = CPICalculator.install_rate(installs=100, clicks=500)
# = 20.0000%
```

---

## 5. Revenue Share (RevShare)

**Formula:** `Publisher Revenue = Gross × Publisher%`

```python
from api.monetization_tools.REVENUE_MODELS.revshare_calculator import RevShareCalculator

split = RevShareCalculator.split(
    gross=Decimal("100.00"),
    publisher_pct=Decimal("70.00"),
)
# publisher=70.00, platform=30.00
```

---

## 6. Subscription Revenue

```python
from api.monetization_tools.REVENUE_MODELS.subscription_revenue import SubscriptionRevenueAnalytics

mrr = SubscriptionRevenueAnalytics.mrr()      # Monthly Recurring Revenue
arr = SubscriptionRevenueAnalytics.arr()      # Annual Recurring Revenue
churn = SubscriptionRevenueAnalytics.churn_rate()  # Monthly churn %
ltv = SubscriptionRevenueAnalytics.ltv(arpu=Decimal("199"), churn_rate_pct=Decimal("5"))
```

---

## 7. In-App Purchase Revenue

```python
from api.monetization_tools.REVENUE_MODELS.in_app_purchase_revenue import IAPRevenueAnalytics

total = IAPRevenueAnalytics.total_revenue()
arppu = IAPRevenueAnalytics.arppu()           # Average Revenue Per Paying User
cvr   = IAPRevenueAnalytics.conversion_rate() # Free-to-paid conversion %
```

---

## 8. Referral / Affiliate Revenue

Multi-level commission structure:
- L1 (direct referral): 10% of referee earnings
- L2 (indirect): 5%
- L3: 2%
- L4: 1%
- L5: 0.5%

```python
from api.monetization_tools.services import ReferralService

commission = ReferralService.award_commission(
    referrer=user,
    referee=new_user,
    program=program,
    commission_type="offer_earn",
    base_amount=Decimal("100.00"),
    level=1,
)
# coins_earned = 10.00 (10% of 100)
```

---

## Coin Economy

```
1 USD = 100 Coins (configurable per tenant via MonetizationConfig)
Minimum withdrawal = 1000 Coins (= $10.00 at default rate)
```

```python
from api.monetization_tools.utils import coins_to_usd, usd_to_coins

usd   = coins_to_usd(Decimal("1000"))  # = 10.00
coins = usd_to_coins(Decimal("10.00")) # = 1000.00
```
