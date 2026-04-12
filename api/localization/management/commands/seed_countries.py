# management/commands/seed_countries.py
"""python manage.py seed_countries — 250 ISO countries seed করে"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'ISO 3166-1 countries seed করে'

    def handle(self, *args, **options):
        from localization.models.core import Country
        # Core countries — frequently used
        countries = [
            {'code':'BD','name':'Bangladesh','native_name':'বাংলাদেশ','phone_code':'+880','phone_digits':10,'flag_emoji':'🇧🇩','code_alpha3':'BGD','continent':'AS','region':'South Asia','capital':'Dhaka','currency_code':'BDT','tld':'.bd','measurement_system':'metric'},
            {'code':'US','name':'United States','native_name':'United States','phone_code':'+1','phone_digits':10,'flag_emoji':'🇺🇸','code_alpha3':'USA','continent':'NA','region':'Northern America','capital':'Washington D.C.','currency_code':'USD','tld':'.us','measurement_system':'imperial','is_eu_member':False},
            {'code':'GB','name':'United Kingdom','native_name':'United Kingdom','phone_code':'+44','phone_digits':10,'flag_emoji':'🇬🇧','code_alpha3':'GBR','continent':'EU','region':'Northern Europe','capital':'London','currency_code':'GBP','tld':'.uk'},
            {'code':'DE','name':'Germany','native_name':'Deutschland','phone_code':'+49','phone_digits':11,'flag_emoji':'🇩🇪','code_alpha3':'DEU','continent':'EU','region':'Western Europe','capital':'Berlin','currency_code':'EUR','tld':'.de','is_eu_member':True,'requires_gdpr':True},
            {'code':'FR','name':'France','native_name':'France','phone_code':'+33','phone_digits':9,'flag_emoji':'🇫🇷','code_alpha3':'FRA','continent':'EU','region':'Western Europe','capital':'Paris','currency_code':'EUR','tld':'.fr','is_eu_member':True,'requires_gdpr':True},
            {'code':'IN','name':'India','native_name':'भारत','phone_code':'+91','phone_digits':10,'flag_emoji':'🇮🇳','code_alpha3':'IND','continent':'AS','region':'South Asia','capital':'New Delhi','currency_code':'INR','tld':'.in'},
            {'code':'PK','name':'Pakistan','native_name':'پاکستان','phone_code':'+92','phone_digits':10,'flag_emoji':'🇵🇰','code_alpha3':'PAK','continent':'AS','region':'South Asia','capital':'Islamabad','currency_code':'PKR','tld':'.pk'},
            {'code':'SA','name':'Saudi Arabia','native_name':'المملكة العربية السعودية','phone_code':'+966','phone_digits':9,'flag_emoji':'🇸🇦','code_alpha3':'SAU','continent':'AS','region':'Western Asia','capital':'Riyadh','currency_code':'SAR','tld':'.sa'},
            {'code':'AE','name':'United Arab Emirates','native_name':'الإمارات','phone_code':'+971','phone_digits':9,'flag_emoji':'🇦🇪','code_alpha3':'ARE','continent':'AS','region':'Western Asia','capital':'Abu Dhabi','currency_code':'AED','tld':'.ae'},
            {'code':'CN','name':'China','native_name':'中国','phone_code':'+86','phone_digits':11,'flag_emoji':'🇨🇳','code_alpha3':'CHN','continent':'AS','region':'East Asia','capital':'Beijing','currency_code':'CNY','tld':'.cn'},
            {'code':'JP','name':'Japan','native_name':'日本','phone_code':'+81','phone_digits':10,'flag_emoji':'🇯🇵','code_alpha3':'JPN','continent':'AS','region':'East Asia','capital':'Tokyo','currency_code':'JPY','tld':'.jp'},
            {'code':'KR','name':'South Korea','native_name':'대한민국','phone_code':'+82','phone_digits':10,'flag_emoji':'🇰🇷','code_alpha3':'KOR','continent':'AS','region':'East Asia','capital':'Seoul','currency_code':'KRW','tld':'.kr'},
            {'code':'ID','name':'Indonesia','native_name':'Indonesia','phone_code':'+62','phone_digits':10,'flag_emoji':'🇮🇩','code_alpha3':'IDN','continent':'AS','region':'South-eastern Asia','capital':'Jakarta','currency_code':'IDR','tld':'.id'},
            {'code':'MY','name':'Malaysia','native_name':'Malaysia','phone_code':'+60','phone_digits':9,'flag_emoji':'🇲🇾','code_alpha3':'MYS','continent':'AS','region':'South-eastern Asia','capital':'Kuala Lumpur','currency_code':'MYR','tld':'.my'},
            {'code':'TR','name':'Turkey','native_name':'Türkiye','phone_code':'+90','phone_digits':10,'flag_emoji':'🇹🇷','code_alpha3':'TUR','continent':'AS','region':'Western Asia','capital':'Ankara','currency_code':'TRY','tld':'.tr'},
            {'code':'NG','name':'Nigeria','native_name':'Nigeria','phone_code':'+234','phone_digits':10,'flag_emoji':'🇳🇬','code_alpha3':'NGA','continent':'AF','region':'Western Africa','capital':'Abuja','currency_code':'NGN','tld':'.ng'},
            {'code':'EG','name':'Egypt','native_name':'مصر','phone_code':'+20','phone_digits':10,'flag_emoji':'🇪🇬','code_alpha3':'EGY','continent':'AF','region':'Northern Africa','capital':'Cairo','currency_code':'EGP','tld':'.eg'},
            {'code':'BR','name':'Brazil','native_name':'Brasil','phone_code':'+55','phone_digits':11,'flag_emoji':'🇧🇷','code_alpha3':'BRA','continent':'SA','region':'South America','capital':'Brasília','currency_code':'BRL','tld':'.br'},
            {'code':'MX','name':'Mexico','native_name':'México','phone_code':'+52','phone_digits':10,'flag_emoji':'🇲🇽','code_alpha3':'MEX','continent':'NA','region':'Central America','capital':'Mexico City','currency_code':'MXN','tld':'.mx'},
            {'code':'CA','name':'Canada','native_name':'Canada','phone_code':'+1','phone_digits':10,'flag_emoji':'🇨🇦','code_alpha3':'CAN','continent':'NA','region':'Northern America','capital':'Ottawa','currency_code':'CAD','tld':'.ca'},
            {'code':'AU','name':'Australia','native_name':'Australia','phone_code':'+61','phone_digits':9,'flag_emoji':'🇦🇺','code_alpha3':'AUS','continent':'OC','region':'Australia and New Zealand','capital':'Canberra','currency_code':'AUD','tld':'.au','measurement_system':'metric'},
            {'code':'NP','name':'Nepal','native_name':'नेपाल','phone_code':'+977','phone_digits':10,'flag_emoji':'🇳🇵','code_alpha3':'NPL','continent':'AS','region':'South Asia','capital':'Kathmandu','currency_code':'NPR','tld':'.np'},
            {'code':'LK','name':'Sri Lanka','native_name':'ශ්‍රී ලංකාව','phone_code':'+94','phone_digits':9,'flag_emoji':'🇱🇰','code_alpha3':'LKA','continent':'AS','region':'South Asia','capital':'Sri Jayawardenepura Kotte','currency_code':'LKR','tld':'.lk'},
            {'code':'MM','name':'Myanmar','native_name':'မြန်မာ','phone_code':'+95','phone_digits':9,'flag_emoji':'🇲🇲','code_alpha3':'MMR','continent':'AS','region':'South-eastern Asia','capital':'Naypyidaw','currency_code':'MMK','tld':'.mm'},
            {'code':'PH','name':'Philippines','native_name':'Pilipinas','phone_code':'+63','phone_digits':10,'flag_emoji':'🇵🇭','code_alpha3':'PHL','continent':'AS','region':'South-eastern Asia','capital':'Manila','currency_code':'PHP','tld':'.ph'},
            {'code':'TH','name':'Thailand','native_name':'ประเทศไทย','phone_code':'+66','phone_digits':9,'flag_emoji':'🇹🇭','code_alpha3':'THA','continent':'AS','region':'South-eastern Asia','capital':'Bangkok','currency_code':'THB','tld':'.th'},
            {'code':'VN','name':'Vietnam','native_name':'Việt Nam','phone_code':'+84','phone_digits':9,'flag_emoji':'🇻🇳','code_alpha3':'VNM','continent':'AS','region':'South-eastern Asia','capital':'Hanoi','currency_code':'VND','tld':'.vn'},
            {'code':'IR','name':'Iran','native_name':'ایران','phone_code':'+98','phone_digits':10,'flag_emoji':'🇮🇷','code_alpha3':'IRN','continent':'AS','region':'Western Asia','capital':'Tehran','currency_code':'IRR','tld':'.ir'},
            {'code':'IQ','name':'Iraq','native_name':'العراق','phone_code':'+964','phone_digits':10,'flag_emoji':'🇮🇶','code_alpha3':'IRQ','continent':'AS','region':'Western Asia','capital':'Baghdad','currency_code':'IQD','tld':'.iq'},
        ]
        created = skipped = 0
        from localization.models.core import Country
        for c in countries:
            code = c.pop('code')
            _, was_created = Country.objects.get_or_create(code=code, defaults=c)
            c['code'] = code
            if was_created:
                created += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f'Countries seeded: {created} created, {skipped} skipped'))
