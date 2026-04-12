# Dispute Resolution Guide

## Overview
The marketplace provides a structured 5-step dispute resolution process to protect both buyers and sellers.

## Dispute Lifecycle

```
OPEN → UNDER_REVIEW → ESCALATED → ARBITRATION → RESOLVED
```

### Step 1: Buyer Raises Dispute
- Buyer clicks "Raise Dispute" on a delivered order
- Selects dispute type and provides description
- Dispute window: **14 days after delivery**
- Escrow is **immediately frozen** when dispute is raised

### Step 2: Seller Responds (3 days)
- Seller receives notification of dispute
- Seller provides response and can upload evidence
- If no response in 3 days → **auto-escalated**

### Step 3: Evidence Submission
Both parties can upload:
- Photos/videos (JPG, PNG, MP4)
- Documents (PDF)
- Max 5 files per party, max 20MB each

### Step 4: Admin Arbitration
Admin reviews all evidence and issues one of:
- **`buyer_wins`**: Full/partial refund to buyer
- **`seller_wins`**: Funds released to seller
- **`partial`**: Split based on `refund_percent`

### Step 5: Resolution
- Escrow resolved per verdict
- `RefundRequest` created automatically
- Both parties notified via push/email

## Dispute Types
| Type | Description | Typical Outcome |
|------|-------------|----------------|
| `not_received` | Item not arrived | Full refund |
| `not_as_described` | Wrong/different item | Partial/full refund |
| `counterfeit` | Fake product | Full refund + seller warning |
| `damaged` | Arrived damaged | Full refund |
| `wrong_item` | Different product sent | Full refund |
| `other` | Other issues | Admin decision |

## API Endpoints
```
POST /api/marketplace/disputes/                      Raise dispute
GET  /api/marketplace/disputes/                      My disputes
GET  /api/marketplace/disputes/{id}/                 Detail + messages
POST /api/marketplace/disputes/{id}/respond/         Seller response
POST /api/marketplace/disputes/{id}/evidence/        Upload evidence
POST /api/marketplace/disputes/{id}/escalate/        Manual escalation
POST /api/marketplace/disputes/{id}/arbitrate/       Admin verdict (staff only)
```

## SLA (Service Level Agreement)
| Action | Target Time |
|--------|------------|
| Seller response | 3 business days |
| Admin review | 5 business days |
| Refund processing | 3–5 business days |
