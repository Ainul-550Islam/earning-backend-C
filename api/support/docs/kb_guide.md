# Knowledge Base Guide

## Structure
`KBCategory` → `KBArticle` (with `KBArticleVersion` history)

## Publishing Workflow
Draft → Published → Archived

## Auto-Suggest
When a ticket is created, the system auto-suggests related KB articles as internal notes.

## Seeding Categories
```bash
python manage.py seed_departments
```
Creates: Getting Started, Payment & Billing, Withdrawal, Account & Security, Offers, KYC, Technical, Referral.

## Helpful Voting
Users can vote articles helpful/unhelpful. Helpful ratio displayed on portal.
