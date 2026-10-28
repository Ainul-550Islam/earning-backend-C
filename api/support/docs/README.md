# World #1 Support System — api.support

## Overview
Complete support system for CPA/earning platform built with Django 5.

## Features
- 🎫 Ticket System with full thread, attachments, tags, SLA
- 💬 Live Chat with WebSocket (Django Channels)
- 🤖 AI Auto-responder, Classifier, Sentiment Analysis
- 📚 Knowledge Base with versioning
- ⚡ Automation Engine (trigger → condition → action)
- 📊 Analytics dashboard + CSAT/NPS tracking
- 🔔 Multi-channel notifications (Email, SMS, Telegram, WhatsApp, Slack, Push)
- 🇧🇩 CPA-specific: Offer Dispute, Payment Dispute, Publisher Portal
- 🌐 Multi-language support with Bangla processor
- 🔐 Permission-based access (IsSupportAgent, IsSupervisorOrAbove)

## Quick Start
```bash
python manage.py migrate support
python manage.py seed_sla_policies
python manage.py seed_canned_responses
python manage.py seed_departments
```

## Directory Structure
See `ticket_system.md`, `livechat_setup.md`, `api_reference.md` for details.
