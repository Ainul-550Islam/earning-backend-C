# Marketplace FAQ

## Setup

**Q: How do I install the marketplace module?**
1. Add `"api.marketplace"` to `INSTALLED_APPS`
2. Include URLs: `path("api/marketplace/", include("api.marketplace.urls"))`
3. Run: `python manage.py makemigrations marketplace && python manage.py migrate`
4. Configure settings (see integration_guide.md)

**Q: What payment methods are supported?**
- bKash (bKash PGW v1.2)
- Nagad
- Rocket
- Cash on Delivery (COD)
- Card (optional, requires Stripe/SSLCommerz)

**Q: Which courier services are integrated?**
Steadfast, Pathao, Redx, eCourier, Sundarban Courier, SA Paribahan

## Sellers

**Q: How does seller KYC work?**
Sellers submit NID (front + back) + selfie. Admin reviews and approves/rejects via the Django admin panel or API endpoint `POST /api/marketplace/seller-verification/{id}/approve/`.

**Q: When do sellers receive payment?**
Funds are held in escrow for 7 days after delivery confirmation. If no dispute is raised, the escrow auto-releases to the seller's wallet.

**Q: How is commission calculated?**
Priority order:
1. Seller-specific override
2. Category commission
3. Parent category commission
4. Global default (10%)

## Orders

**Q: What order statuses exist?**
`pending → confirmed → processing → shipped → out_for_delivery → delivered`
Cancellation possible at: `pending` or `confirmed`
Returns after: `delivered`

**Q: How long does a buyer have to raise a dispute?**
14 days after delivery (configurable via `ESCROW_DISPUTE_WINDOW_DAYS`).

## Technical

**Q: Is Elasticsearch required?**
No. The search engine falls back to ORM-based search if Elasticsearch is unavailable.

**Q: How do I test push notifications?**
Configure `FCM_SERVER_KEY` in settings.py and use the `PushNotificationService` class directly, or `POST /api/marketplace/device-tokens/` to register a device.

**Q: How do I enable multi-tenancy?**
The marketplace uses `request.tenant` for tenant isolation. Ensure your tenant middleware sets `request.tenant` before the marketplace views are called.
