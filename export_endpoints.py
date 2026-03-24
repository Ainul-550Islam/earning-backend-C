# -*- coding: utf-8 -*-
import os, json, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
import django
django.setup()
from django.urls import get_resolver

ICONS = {
    'GatewayTransactions': '[GT]',
    'ad-networks': '[AD]',
    'ad_networks': '[AD]',
    'admin-panel': '[AP]',
    'alerts': '[AL]',
    'analytics': '[AN]',
    'audit_logs': '[AU]',
    'auth': '[KY]',
    'auto-mod': '[AM]',
    'backup': '[BK]',
    'behavior-analytics': '[BA]',
    'bans': '[BN]',
    'cache': '[CA]',
    'cms': '[CM]',
    'complete-ad': '[CA]',
    'completions': '[CK]',
    'customers': '[CU]',
    'dashboard': '[DB]',
    'dashboards': '[DS]',
    'devices': '[DV]',
    'djoyalty': '[LY]',
    'engagement': '[EN]',
    'fraud-detection': '[FD]',
    'fraud_detection': '[FD]',
    'gamification': '[GM]',
    'inventory': '[IN]',
    'kyc': '[KC]',
    'localization': '[LC]',
    'login': '[LG]',
    'loyalty': '[LO]',
    'messaging': '[MS]',
    'notifications': '[NT]',
    'offers': '[OF]',
    'payment_gateways': '[PG]',
    'payout-queue': '[PQ]',
    'postback': '[PB]',
    'profile': '[PR]',
    'promotions': '[PM]',
    'rate-limit': '[RL]',
    'referral': '[RF]',
    'register': '[RG]',
    'security': '[SC]',
    'subscription': '[SB]',
    'subscriptions': '[SB]',
    'support': '[SP]',
    'tasks': '[TK]',
    'user': '[US]',
    'users': '[US]',
    'version-control': '[VC]',
    'wallet': '[WL]',
    'wallets': '[WL]',
    'withdrawals': '[WD]',
    '2fa': '[2F]',
    'admin': '[AD]',
    'admin-ledger': '[AL]',
    'audit': '[AU]',
    'auto-block-rules': '[AB]',
}


def extract(resolver, prefix=''):
    results = []
    for pattern in resolver.url_patterns:
        try:
            if hasattr(pattern, 'url_patterns'):
                results.extend(extract(pattern, prefix + str(pattern.pattern)))
            else:
                full = '/' + prefix + str(pattern.pattern)
                import re
                full = re.sub(r'\(\?P<[^>]+>[^)]+\)', '{id}', full)
                if not full.startswith('/api/'): continue
                skip = ['/schema','/docs','/redoc','/cms-admin','/admin/','/static','/media']
                if any(x in full for x in skip): continue
                methods = []
                if hasattr(pattern.callback, 'actions'):
                    m = {'get':'GET','post':'POST','put':'PUT','patch':'PATCH','delete':'DELETE'}
                    methods = [m[k] for k in pattern.callback.actions if k in m]
                if not methods: methods = ['GET']
                for meth in methods:
                    results.append({'method': meth, 'path': full})
        except: pass
    return results

print("Extracting URLs...")
urls = extract(get_resolver())
seen = set()
unique = []
for u in urls:
    k = u['method'] + u['path']
    if k not in seen:
        seen.add(k)
        unique.append(u)
print("Found:", len(unique), "unique endpoints")

groups = {}
for ep in unique:
    parts = ep['path'].split('/')
    key = parts[2] if len(parts) > 2 else 'other'
    if key not in groups:
        groups[key] = {
            'key': key,
            'label': key.replace('-',' ').replace('_',' ').title(),
            'icon': ICONS.get(key, '[??]'),
            'count': 0,
            'endpoints': []
        }
    groups[key]['endpoints'].append(ep)

out = []
for g in sorted(groups.values(), key=lambda x: x['key']):
    g['count'] = len(g['endpoints'])
    out.append(g)

print("Total:", len(unique), "Groups:", len(out))
base = os.path.dirname(os.path.abspath(__file__))
outfile = os.path.join(base, 'frontend', 'src', 'all_endpoints.json')
with open(outfile, 'w', encoding='utf-8') as f:
    import json
    json.dump(out, f, ensure_ascii=True, indent=2)
print("Saved:", outfile)
