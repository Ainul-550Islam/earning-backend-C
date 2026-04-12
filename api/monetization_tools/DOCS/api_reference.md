# Monetization Tools — API Reference

## Base URL
```
/api/monetization/
```

## Authentication
All endpoints require JWT Bearer token:
```
Authorization: Bearer <access_token>
```

Admin-only endpoints additionally require `is_staff=True`.

---

## Core Endpoints

### Ad Networks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ad-networks/` | List all active ad networks |
| POST | `/ad-networks/` | Create new ad network (admin) |
| GET | `/ad-networks/{id}/` | Retrieve network detail |
| PUT | `/ad-networks/{id}/` | Update network (admin) |
| DELETE | `/ad-networks/{id}/` | Delete network (admin) |

### Ad Campaigns
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/campaigns/` | List campaigns |
| POST | `/campaigns/` | Create campaign (admin) |
| GET | `/campaigns/{id}/` | Campaign detail |
| POST | `/campaigns/{id}/pause/` | Pause campaign |
| POST | `/campaigns/{id}/activate/` | Activate campaign |
| GET | `/campaigns/{id}/stats/` | Campaign performance stats |

### Ad Units
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ad-units/` | List ad units |
| POST | `/ad-units/` | Create ad unit (admin) |
| GET | `/ad-units/{id}/performance/` | Unit performance stats |

### Offerwall
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/offerwalls/` | List active offerwalls |
| GET | `/offers/` | List available offers |
| GET | `/offers/?featured=true` | Featured offers |
| GET | `/offers/?country=BD&device=mobile` | Filtered offers |
| POST | `/offer-completions/` | Submit offer completion |
| GET | `/offer-completions/` | User's completions |

### Rewards
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reward-transactions/` | User reward history |
| GET | `/reward-transactions/summary/` | Earning summary |

### Subscriptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/subscription-plans/` | List plans |
| POST | `/user-subscriptions/` | Subscribe to plan |
| GET | `/user-subscriptions/active/` | User's active subscription |
| POST | `/user-subscriptions/{id}/cancel/` | Cancel subscription |

### Spin Wheel & Gamification
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/spin-configs/{id}/spin/` | Play spin wheel |
| GET | `/daily-streaks/me/` | User's streak info |
| POST | `/daily-streaks/check-in/` | Daily check-in |
| GET | `/leaderboard-ranks/` | Leaderboard |

### Referral
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/referral-links/my-link/` | User's referral link |
| GET | `/referral-commissions/summary/` | Commission summary |
| GET | `/referral-commissions/` | Commission history |

### Payout
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/payout-methods/` | User's payout methods |
| POST | `/payout-methods/` | Add payout method |
| POST | `/payout-methods/{id}/set-default/` | Set as default |
| POST | `/payout-methods/{id}/verify/` | Verify method (admin) |
| GET | `/payout-requests/` | User's payout requests |
| POST | `/payout-requests/` | Create payout request |
| POST | `/payout-requests/{id}/approve/` | Approve (admin) |
| POST | `/payout-requests/{id}/reject/` | Reject (admin) |
| POST | `/payout-requests/{id}/mark-paid/` | Mark paid (admin) |

### Coupon
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/coupons/validate/` | Validate coupon code |
| POST | `/coupons/redeem/` | Redeem coupon |
| GET | `/coupons/` | List coupons (admin) |

### Flash Sales
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/flash-sales/live/` | Currently live flash sales |
| GET | `/flash-sales/` | All flash sales (admin) |

### Fraud Alerts (Admin)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/fraud-alerts/` | List fraud alerts |
| POST | `/fraud-alerts/{id}/resolve/` | Resolve alert |
| GET | `/fraud-alerts/dashboard/` | Fraud dashboard stats |

### Revenue Goals (Admin)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/revenue-goals/` | List goals |
| POST | `/revenue-goals/` | Create goal |
| PATCH | `/revenue-goals/{id}/update-progress/` | Update progress |

### Analytics (Admin)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/perf/daily/` | Daily performance data |
| GET | `/perf/daily/kpi-summary/` | KPI summary |
| GET | `/perf/hourly/` | Hourly performance |
| GET | `/network-stats/` | Network daily stats |
| GET | `/config/feature-flags/` | Feature flags |

---

## Request / Response Format

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message"
}
```

### Error Response
```json
{
  "success": false,
  "detail": "Error message",
  "code": "error_code"
}
```

### Pagination
```json
{
  "count": 100,
  "next": "https://api/endpoint/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

---

## Postback Endpoint

Ad networks send server-to-server postbacks to:
```
POST /api/monetization/postback/{network_name}/
```

Query parameters vary by network. Signature validation is applied.
See `ad_integration_guide.md` for per-network documentation.
