path = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api\users\models.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = "    referred_by = models.ForeignKey(\n        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='%(app_label)s_%(class)s_tenant'\n    )"
new = "    referred_by = models.ForeignKey(\n        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_list'\n    )"

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done!')
else:
    print('Not found - checking...')
    idx = content.find('referred_by')
    print(content[idx-20:idx+150])
