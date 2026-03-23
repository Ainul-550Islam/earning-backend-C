path = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api\serializers.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = "        # Create wallet\n        Wallet.objects.create(user=user)"
new = "        # Create wallet\n        from api.wallet.models import Wallet\n        Wallet.objects.get_or_create(user=user)"

content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
