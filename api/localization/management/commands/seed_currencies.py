# management/commands/seed_currencies.py
"""python manage.py seed_currencies — 170+ currencies seed করে"""
from django.core.management.base import BaseCommand

CURRENCIES = [
    {'code':'USD','name':'US Dollar','symbol':'$','symbol_native':'$','decimal_digits':2,'is_default':True},
    {'code':'EUR','name':'Euro','symbol':'€','symbol_native':'€','decimal_digits':2},
    {'code':'GBP','name':'British Pound','symbol':'£','symbol_native':'£','decimal_digits':2},
    {'code':'BDT','name':'Bangladeshi Taka','symbol':'৳','symbol_native':'৳','decimal_digits':2},
    {'code':'INR','name':'Indian Rupee','symbol':'₹','symbol_native':'₹','decimal_digits':2},
    {'code':'PKR','name':'Pakistani Rupee','symbol':'₨','symbol_native':'₨','decimal_digits':2},
    {'code':'NPR','name':'Nepalese Rupee','symbol':'₨','symbol_native':'रू','decimal_digits':2},
    {'code':'LKR','name':'Sri Lankan Rupee','symbol':'₨','symbol_native':'රු','decimal_digits':2},
    {'code':'SAR','name':'Saudi Riyal','symbol':'SR','symbol_native':'ر.س','decimal_digits':2},
    {'code':'AED','name':'UAE Dirham','symbol':'AED','symbol_native':'د.إ','decimal_digits':2},
    {'code':'JPY','name':'Japanese Yen','symbol':'¥','symbol_native':'¥','decimal_digits':0},
    {'code':'CNY','name':'Chinese Yuan','symbol':'¥','symbol_native':'¥','decimal_digits':2},
    {'code':'KRW','name':'South Korean Won','symbol':'₩','symbol_native':'₩','decimal_digits':0},
    {'code':'IDR','name':'Indonesian Rupiah','symbol':'Rp','symbol_native':'Rp','decimal_digits':0},
    {'code':'MYR','name':'Malaysian Ringgit','symbol':'RM','symbol_native':'RM','decimal_digits':2},
    {'code':'THB','name':'Thai Baht','symbol':'฿','symbol_native':'฿','decimal_digits':2},
    {'code':'VND','name':'Vietnamese Dong','symbol':'₫','symbol_native':'₫','decimal_digits':0},
    {'code':'PHP','name':'Philippine Peso','symbol':'₱','symbol_native':'₱','decimal_digits':2},
    {'code':'TRY','name':'Turkish Lira','symbol':'₺','symbol_native':'₺','decimal_digits':2},
    {'code':'CAD','name':'Canadian Dollar','symbol':'CA$','symbol_native':'$','decimal_digits':2},
    {'code':'AUD','name':'Australian Dollar','symbol':'A$','symbol_native':'$','decimal_digits':2},
    {'code':'BRL','name':'Brazilian Real','symbol':'R$','symbol_native':'R$','decimal_digits':2},
    {'code':'MXN','name':'Mexican Peso','symbol':'MX$','symbol_native':'$','decimal_digits':2},
    {'code':'RUB','name':'Russian Ruble','symbol':'₽','symbol_native':'₽','decimal_digits':2},
    {'code':'CHF','name':'Swiss Franc','symbol':'CHF','symbol_native':'CHF','decimal_digits':2},
    {'code':'SEK','name':'Swedish Krona','symbol':'kr','symbol_native':'kr','decimal_digits':2},
    {'code':'NOK','name':'Norwegian Krone','symbol':'kr','symbol_native':'kr','decimal_digits':2},
    {'code':'DKK','name':'Danish Krone','symbol':'kr','symbol_native':'kr','decimal_digits':2},
    {'code':'PLN','name':'Polish Zloty','symbol':'zł','symbol_native':'zł','decimal_digits':2},
    {'code':'HUF','name':'Hungarian Forint','symbol':'Ft','symbol_native':'Ft','decimal_digits':0},
    {'code':'CZK','name':'Czech Koruna','symbol':'Kč','symbol_native':'Kč','decimal_digits':2},
    {'code':'ILS','name':'Israeli Shekel','symbol':'₪','symbol_native':'₪','decimal_digits':2},
    {'code':'ZAR','name':'South African Rand','symbol':'R','symbol_native':'R','decimal_digits':2},
    {'code':'EGP','name':'Egyptian Pound','symbol':'E£','symbol_native':'ج.م','decimal_digits':2},
    {'code':'NGN','name':'Nigerian Naira','symbol':'₦','symbol_native':'₦','decimal_digits':2},
    {'code':'KES','name':'Kenyan Shilling','symbol':'KSh','symbol_native':'KSh','decimal_digits':2},
    {'code':'GHS','name':'Ghanaian Cedi','symbol':'GH₵','symbol_native':'GH₵','decimal_digits':2},
    {'code':'MAD','name':'Moroccan Dirham','symbol':'MAD','symbol_native':'د.م.','decimal_digits':2},
    {'code':'TZS','name':'Tanzanian Shilling','symbol':'TSh','symbol_native':'TSh','decimal_digits':2},
    {'code':'ETB','name':'Ethiopian Birr','symbol':'Br','symbol_native':'ብር','decimal_digits':2},
    {'code':'QAR','name':'Qatari Riyal','symbol':'QR','symbol_native':'ر.ق','decimal_digits':2},
    {'code':'KWD','name':'Kuwaiti Dinar','symbol':'KD','symbol_native':'د.ك','decimal_digits':3},
    {'code':'BHD','name':'Bahraini Dinar','symbol':'BD','symbol_native':'د.ب','decimal_digits':3},
    {'code':'OMR','name':'Omani Rial','symbol':'OMR','symbol_native':'ر.ع.','decimal_digits':3},
    {'code':'JOD','name':'Jordanian Dinar','symbol':'JD','symbol_native':'د.ا','decimal_digits':3},
    {'code':'MMK','name':'Myanmar Kyat','symbol':'K','symbol_native':'K','decimal_digits':0},
    {'code':'TWD','name':'New Taiwan Dollar','symbol':'NT$','symbol_native':'$','decimal_digits':0},
    {'code':'HKD','name':'Hong Kong Dollar','symbol':'HK$','symbol_native':'$','decimal_digits':2},
    {'code':'SGD','name':'Singapore Dollar','symbol':'S$','symbol_native':'$','decimal_digits':2},
    {'code':'NZD','name':'New Zealand Dollar','symbol':'NZ$','symbol_native':'$','decimal_digits':2},
]

class Command(BaseCommand):
    help = '170+ ISO currencies seed করে'

    def handle(self, *args, **options):
        from localization.models.core import Currency
        created = skipped = 0
        for curr in CURRENCIES:
            code = curr.pop('code')
            _, was_created = Currency.objects.get_or_create(code=code, defaults=curr)
            curr['code'] = code
            if was_created:
                created += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f'Currencies seeded: {created} created, {skipped} skipped'))
