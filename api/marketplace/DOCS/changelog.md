# Marketplace Changelog

## v1.0.0 (2025-01-01)
### Added
- Initial marketplace release
- Multi-tenant product & seller management
- Full order lifecycle (place → confirm → ship → deliver)
- bKash, Nagad, Rocket, COD payment methods
- Escrow holding with 7-day auto-release
- Commission calculator (multi-level: seller → category → global)
- Race-condition-safe inventory with `select_for_update`
- Elasticsearch search with ORM fallback
- Dispute resolution workflow (raise → respond → arbitrate)
- Loyalty reward system (Bronze → Silver → Gold → Platinum)
- Referral program with fraud prevention
- Push notifications (FCM + Expo)
- Remote app configuration
- Steadfast, Pathao, Redx courier integration
- Bangladesh VAT/NBR (15%) calculation
- bKash PGW v1.2 payment gateway integration
- Bulk product upload via CSV/Excel (Celery async)
- Seller KYC/NID verification workflow
- Counterfeit & prohibited item detection
- Webhook system (HMAC-SHA256 signed)

## v1.1.0
### Added
- Flash sale with countdown timer
- BOGO (Buy One Get One) promotions
- Bundle deals with tiered discount
- Seasonal promotions scheduler
- AI-powered offer recommendations
- QR code generation for products & sellers
- Offline sync manifest for mobile apps
- Cohort retention analytics
- Bayesian product rating scoring
- Seller performance scorecard (0-100)

## v1.2.0
### Added
- Postback webhook handler (CPAlead-compatible)
- Social commerce integration (Facebook, Instagram shop)
- Amazon SP-API price intelligence
- Shopify & WooCommerce product sync
- POS integration (barcode scanner)
- Abandoned cart recovery emails
- Deep link manager (marketplace:// scheme)
- App launch offers with claim tracking
