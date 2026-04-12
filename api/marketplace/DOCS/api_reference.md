# Marketplace API Reference

Base URL: `/api/marketplace/`

## Authentication
All write endpoints require `Authorization: Bearer <token>` header.

---

## 🛍️ Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/products/` | List active products |
| POST   | `/products/` | Create product (seller) |
| GET    | `/products/{id}/` | Product detail |
| PUT    | `/products/{id}/` | Update product |
| GET    | `/products/featured/` | Featured products |
| GET    | `/products/{id}/reviews/` | Product reviews |

## 🗂️ Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/categories/` | List categories |
| GET    | `/categories/tree/` | Full category tree |
| GET    | `/categories/{id}/products/` | Products in category |

## 👥 Sellers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/sellers/` | My seller profile |
| POST   | `/sellers/` | Create seller profile |
| GET    | `/sellers/{id}/dashboard/` | Seller dashboard stats |
| POST   | `/seller-verification/{id}/approve/` | Admin: approve KYC |
| POST   | `/seller-verification/{id}/reject/` | Admin: reject KYC |

## 🛒 Cart

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/cart/` | Get active cart |
| POST   | `/cart/{id}/add_item/` | Add item to cart |
| DELETE | `/cart/{id}/remove_item/` | Remove item |
| POST   | `/cart/{id}/apply_coupon/` | Apply coupon code |
| POST   | `/cart/{id}/checkout/` | Place order |

## 📦 Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/orders/` | My orders |
| GET    | `/orders/{id}/` | Order detail |
| POST   | `/orders/{id}/confirm/` | Confirm order |
| POST   | `/orders/{id}/ship/` | Mark shipped |
| POST   | `/orders/{id}/deliver/` | Mark delivered |
| POST   | `/orders/{id}/cancel/` | Cancel order |
| GET    | `/orders/{id}/tracking/` | Tracking events |

## 💳 Payments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/transactions/initiate/` | Initiate payment |
| POST   | `/transactions/{id}/mark_success/` | Admin: confirm payment |
| POST   | `/escrow/{id}/release/` | Admin: release escrow |
| POST   | `/refunds/` | Request refund |
| POST   | `/refunds/{id}/approve/` | Admin: approve refund |

## 🎁 Promotions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/coupons/` | Public coupons |
| POST   | `/coupons/validate/` | Validate coupon |
| GET    | `/promotions/live/` | Live campaigns |
| GET    | `/reviews/` | All reviews |
| POST   | `/reviews/` | Post review |
| POST   | `/reviews/{id}/reply/` | Seller reply |
| POST   | `/reviews/{id}/helpful/` | Mark helpful |
