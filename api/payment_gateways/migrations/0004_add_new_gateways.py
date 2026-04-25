# FILE: migrations/0004_add_new_gateways.py
from django.db import migrations, models

ALL_GW = [('bkash','bKash'),('nagad','Nagad'),('sslcommerz','SSLCommerz'),
          ('amarpay','AmarPay'),('upay','Upay'),('shurjopay','ShurjoPay'),
          ('stripe','Stripe'),('paypal','PayPal')]

class Migration(migrations.Migration):
    dependencies = [('payment_gateways', '0003_alter_gatewaytransaction_user_and_more')]
    operations = [
        migrations.AlterField(model_name='paymentgateway', name='name',
            field=models.CharField(max_length=50, choices=ALL_GW, unique=True)),
        migrations.AlterField(model_name='paymentgatewaymethod', name='gateway',
            field=models.CharField(max_length=20, choices=ALL_GW)),
        migrations.AlterField(model_name='gatewaytransaction', name='gateway',
            field=models.CharField(max_length=20, choices=ALL_GW)),
        migrations.AlterField(model_name='payoutrequest', name='payout_method',
            field=models.CharField(max_length=20, choices=ALL_GW+[('bank','Bank Transfer')])),
        migrations.AlterField(model_name='paymentgatewaywebhooklog', name='gateway',
            field=models.CharField(max_length=20, choices=ALL_GW)),
    ]
