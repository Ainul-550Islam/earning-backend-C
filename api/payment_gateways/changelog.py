# api/payment_gateways/changelog.py
# System changelog
CHANGELOG=[
    {'version':'2.0.0','date':'2025-01-01','type':'major','changes':['World-class CPA affiliate system','12 payment gateways (6 BD + 6 international)','USDT FastPay','SmartLink with A/B testing','Content locker + offerwall','GEO-based pricing engine','Real-time WebSocket events','OpenAI integration','Sanctions screening (OFAC/UN)','AML/KYC compliance','Redis-backed message queue','Full integration system (18 files)','Clean architecture (selectors/repositories/use_cases/interactors)','43 world-class additional modules']},
    {'version':'1.5.0','date':'2024-06-01','type':'minor','changes':['Added Crypto gateway (USDT)','ACH bank transfer','Publisher leaderboard','Performance bonus tiers']},
    {'version':'1.0.0','date':'2024-01-01','type':'initial','changes':['Initial release with bKash, Nagad, SSLCommerz, Stripe, PayPal','Basic conversion tracking','Publisher profiles','Offer management']},
]

def get_changelog(): return CHANGELOG
def get_latest_version(): return CHANGELOG[0]['version'] if CHANGELOG else '0.0.0'
def get_changes_since(version):
    changes=[]
    for entry in CHANGELOG:
        if entry['version']==version: break
        changes.append(entry)
    return changes
