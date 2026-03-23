path = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api\serializers.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old1 = "                referrer.wallet.add_funds(5.00, \"New referral bonus\")\n                user.wallet.add_funds(Decimal(\"1.00\"), \"Welcome bonus\")"
new1 = "                from api.wallet.models import Wallet\n                referrer_wallet, _ = Wallet.objects.get_or_create(user=referrer)\n                referrer_wallet.add_funds(5.00, \"New referral bonus\")\n                user_wallet, _ = Wallet.objects.get_or_create(user=user)\n                user_wallet.add_funds(Decimal(\"1.00\"), \"Welcome bonus\")"

old2 = "            user.wallet.add_funds(Decimal(\"1.00\"), \"Welcome bonus\")"
new2 = "            from api.wallet.models import Wallet\n            user_wallet, _ = Wallet.objects.get_or_create(user=user)\n            user_wallet.add_funds(Decimal(\"1.00\"), \"Welcome bonus\")"

content = content.replace(old1, new1)
content = content.replace(old2, new2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
