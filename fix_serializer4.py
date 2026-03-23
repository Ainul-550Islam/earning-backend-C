path = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api\serializers.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'return obj.referrals.count()',
    'return obj.referrals_list.count()'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
