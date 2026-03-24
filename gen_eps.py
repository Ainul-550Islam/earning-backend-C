import json, re
from django.urls import get_resolver

def ex(r, pre=''):
    res = []
    for p in r.url_patterns:
        try:
            if hasattr(p, 'url_patterns'):
                res.extend(ex(p, pre+str(p.pattern)))
            else:
                full = '/'+pre+str(p.pattern)
                full = re.sub(r'\(\?P<[^>]+>[^)]+\)', '{id}', full)
                if not full.startswith('/api/'): continue
                skip = ['/schema','/docs','/redoc','/admin/','/static','/media']
                if any(x in full for x in skip): continue
                ms = []
                if hasattr(p.callback, 'actions'):
                    mm = {'get':'GET','post':'POST','put':'PUT','patch':'PATCH','delete':'DELETE'}
                    ms = [mm[k] for k in p.callback.actions if k in mm]
                if not ms: ms = ['GET']
                for m in ms:
                    res.append({'method':m,'path':full})
        except: pass
    return res

urls = ex(get_resolver())
seen = set()
unique = []
for u in urls:
    k = u['method']+u['path']
    if k not in seen:
        seen.add(k)
        unique.append(u)

groups = {}
for ep in unique:
    key = ep['path'].split('/')[2] if len(ep['path'].split('/'))>2 else 'other'
    if key not in groups:
        groups[key] = {'key':key,'label':key.replace('-',' ').replace('_',' ').title(),'icon':'[?]','count':0,'endpoints':[]}
    groups[key]['endpoints'].append(ep)

out = sorted([dict(**g, count=len(g['endpoints'])) for g in groups.values()], key=lambda x: x['key'])
print('TOTAL:', len(unique), 'GROUPS:', len(out))

import os
outfile = os.path.join(os.path.dirname(os.path.abspath('.')), 'New folder (8)', 'earning_backend', 'frontend', 'src', 'all_endpoints.json')
with open('frontend/src/all_endpoints.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=True)
print('SAVED OK')
