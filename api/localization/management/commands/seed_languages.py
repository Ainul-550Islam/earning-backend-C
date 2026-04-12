# management/commands/seed_languages.py
"""python manage.py seed_languages — 50+ languages seed করে"""
from django.core.management.base import BaseCommand
from django.db import transaction
import logging
logger = logging.getLogger(__name__)

LANGUAGES = [
    {'code':'en','name':'English','name_native':'English','is_default':True,'flag_emoji':'🇺🇸','locale_code':'en_US','is_rtl':False,'bcp47_code':'en-US','iso_639_1':'en','iso_639_2':'eng'},
    {'code':'bn','name':'Bengali','name_native':'বাংলা','flag_emoji':'🇧🇩','locale_code':'bn_BD','is_rtl':False,'bcp47_code':'bn-BD','iso_639_1':'bn','iso_639_2':'ben','script_code':'Beng'},
    {'code':'hi','name':'Hindi','name_native':'हिन्दी','flag_emoji':'🇮🇳','locale_code':'hi_IN','is_rtl':False,'bcp47_code':'hi-IN','iso_639_1':'hi','iso_639_2':'hin','script_code':'Deva'},
    {'code':'ar','name':'Arabic','name_native':'العربية','flag_emoji':'🇸🇦','locale_code':'ar_SA','is_rtl':True,'bcp47_code':'ar-SA','iso_639_1':'ar','iso_639_2':'ara','script_code':'Arab'},
    {'code':'ur','name':'Urdu','name_native':'اردو','flag_emoji':'🇵🇰','locale_code':'ur_PK','is_rtl':True,'bcp47_code':'ur-PK','iso_639_1':'ur','iso_639_2':'urd','script_code':'Arab'},
    {'code':'fa','name':'Persian','name_native':'فارسی','flag_emoji':'🇮🇷','locale_code':'fa_IR','is_rtl':True,'bcp47_code':'fa-IR','iso_639_1':'fa','iso_639_2':'fas','script_code':'Arab'},
    {'code':'he','name':'Hebrew','name_native':'עברית','flag_emoji':'🇮🇱','locale_code':'he_IL','is_rtl':True,'bcp47_code':'he-IL','iso_639_1':'he','iso_639_2':'heb','script_code':'Hebr'},
    {'code':'es','name':'Spanish','name_native':'Español','flag_emoji':'🇪🇸','locale_code':'es_ES','bcp47_code':'es-ES','iso_639_1':'es','iso_639_2':'spa'},
    {'code':'fr','name':'French','name_native':'Français','flag_emoji':'🇫🇷','locale_code':'fr_FR','bcp47_code':'fr-FR','iso_639_1':'fr','iso_639_2':'fra'},
    {'code':'de','name':'German','name_native':'Deutsch','flag_emoji':'🇩🇪','locale_code':'de_DE','bcp47_code':'de-DE','iso_639_1':'de','iso_639_2':'deu'},
    {'code':'pt','name':'Portuguese','name_native':'Português','flag_emoji':'🇵🇹','locale_code':'pt_PT','bcp47_code':'pt-PT','iso_639_1':'pt','iso_639_2':'por'},
    {'code':'it','name':'Italian','name_native':'Italiano','flag_emoji':'🇮🇹','locale_code':'it_IT','bcp47_code':'it-IT','iso_639_1':'it','iso_639_2':'ita'},
    {'code':'ru','name':'Russian','name_native':'Русский','flag_emoji':'🇷🇺','locale_code':'ru_RU','bcp47_code':'ru-RU','iso_639_1':'ru','iso_639_2':'rus','script_code':'Cyrl'},
    {'code':'zh','name':'Chinese (Simplified)','name_native':'简体中文','flag_emoji':'🇨🇳','locale_code':'zh_CN','bcp47_code':'zh-Hans','iso_639_1':'zh','iso_639_2':'zho','script_code':'Hans'},
    {'code':'ja','name':'Japanese','name_native':'日本語','flag_emoji':'🇯🇵','locale_code':'ja_JP','bcp47_code':'ja-JP','iso_639_1':'ja','iso_639_2':'jpn','script_code':'Jpan'},
    {'code':'ko','name':'Korean','name_native':'한국어','flag_emoji':'🇰🇷','locale_code':'ko_KR','bcp47_code':'ko-KR','iso_639_1':'ko','iso_639_2':'kor','script_code':'Hang'},
    {'code':'tr','name':'Turkish','name_native':'Türkçe','flag_emoji':'🇹🇷','locale_code':'tr_TR','bcp47_code':'tr-TR','iso_639_1':'tr','iso_639_2':'tur'},
    {'code':'vi','name':'Vietnamese','name_native':'Tiếng Việt','flag_emoji':'🇻🇳','locale_code':'vi_VN','bcp47_code':'vi-VN','iso_639_1':'vi','iso_639_2':'vie'},
    {'code':'id','name':'Indonesian','name_native':'Bahasa Indonesia','flag_emoji':'🇮🇩','locale_code':'id_ID','bcp47_code':'id-ID','iso_639_1':'id','iso_639_2':'ind'},
    {'code':'ms','name':'Malay','name_native':'Bahasa Melayu','flag_emoji':'🇲🇾','locale_code':'ms_MY','bcp47_code':'ms-MY','iso_639_1':'ms','iso_639_2':'msa'},
    {'code':'ta','name':'Tamil','name_native':'தமிழ்','flag_emoji':'🇮🇳','locale_code':'ta_IN','bcp47_code':'ta-IN','iso_639_1':'ta','iso_639_2':'tam','script_code':'Taml'},
    {'code':'te','name':'Telugu','name_native':'తెలుగు','flag_emoji':'🇮🇳','locale_code':'te_IN','bcp47_code':'te-IN','iso_639_1':'te','iso_639_2':'tel','script_code':'Telu'},
    {'code':'ml','name':'Malayalam','name_native':'മലയാളം','flag_emoji':'🇮🇳','locale_code':'ml_IN','bcp47_code':'ml-IN','iso_639_1':'ml','iso_639_2':'mal','script_code':'Mlym'},
    {'code':'kn','name':'Kannada','name_native':'ಕನ್ನಡ','flag_emoji':'🇮🇳','locale_code':'kn_IN','bcp47_code':'kn-IN','iso_639_1':'kn','iso_639_2':'kan'},
    {'code':'mr','name':'Marathi','name_native':'मराठी','flag_emoji':'🇮🇳','locale_code':'mr_IN','bcp47_code':'mr-IN','iso_639_1':'mr','iso_639_2':'mar'},
    {'code':'gu','name':'Gujarati','name_native':'ગુજરાતી','flag_emoji':'🇮🇳','locale_code':'gu_IN','bcp47_code':'gu-IN','iso_639_1':'gu','iso_639_2':'guj'},
    {'code':'pa','name':'Punjabi','name_native':'ਪੰਜਾਬੀ','flag_emoji':'🇮🇳','locale_code':'pa_IN','bcp47_code':'pa-IN','iso_639_1':'pa','iso_639_2':'pan'},
    {'code':'ne','name':'Nepali','name_native':'नेपाली','flag_emoji':'🇳🇵','locale_code':'ne_NP','bcp47_code':'ne-NP','iso_639_1':'ne','iso_639_2':'nep'},
    {'code':'si','name':'Sinhala','name_native':'සිංහල','flag_emoji':'🇱🇰','locale_code':'si_LK','bcp47_code':'si-LK','iso_639_1':'si','iso_639_2':'sin'},
    {'code':'my','name':'Burmese','name_native':'မြန်မာဘာသာ','flag_emoji':'🇲🇲','locale_code':'my_MM','bcp47_code':'my-MM','iso_639_1':'my','iso_639_2':'mya'},
    {'code':'km','name':'Khmer','name_native':'ភាសាខ្មែរ','flag_emoji':'🇰🇭','locale_code':'km_KH','bcp47_code':'km-KH','iso_639_1':'km','iso_639_2':'khm'},
    {'code':'th','name':'Thai','name_native':'ภาษาไทย','flag_emoji':'🇹🇭','locale_code':'th_TH','bcp47_code':'th-TH','iso_639_1':'th','iso_639_2':'tha','script_code':'Thai'},
    {'code':'nl','name':'Dutch','name_native':'Nederlands','flag_emoji':'🇳🇱','locale_code':'nl_NL','bcp47_code':'nl-NL','iso_639_1':'nl','iso_639_2':'nld'},
    {'code':'pl','name':'Polish','name_native':'Polski','flag_emoji':'🇵🇱','locale_code':'pl_PL','bcp47_code':'pl-PL','iso_639_1':'pl','iso_639_2':'pol'},
    {'code':'uk','name':'Ukrainian','name_native':'Українська','flag_emoji':'🇺🇦','locale_code':'uk_UA','bcp47_code':'uk-UA','iso_639_1':'uk','iso_639_2':'ukr','script_code':'Cyrl'},
    {'code':'cs','name':'Czech','name_native':'Čeština','flag_emoji':'🇨🇿','locale_code':'cs_CZ','bcp47_code':'cs-CZ','iso_639_1':'cs','iso_639_2':'ces'},
    {'code':'sk','name':'Slovak','name_native':'Slovenčina','flag_emoji':'🇸🇰','locale_code':'sk_SK','bcp47_code':'sk-SK','iso_639_1':'sk','iso_639_2':'slk'},
    {'code':'ro','name':'Romanian','name_native':'Română','flag_emoji':'🇷🇴','locale_code':'ro_RO','bcp47_code':'ro-RO','iso_639_1':'ro','iso_639_2':'ron'},
    {'code':'hu','name':'Hungarian','name_native':'Magyar','flag_emoji':'🇭🇺','locale_code':'hu_HU','bcp47_code':'hu-HU','iso_639_1':'hu','iso_639_2':'hun'},
    {'code':'sv','name':'Swedish','name_native':'Svenska','flag_emoji':'🇸🇪','locale_code':'sv_SE','bcp47_code':'sv-SE','iso_639_1':'sv','iso_639_2':'swe'},
    {'code':'da','name':'Danish','name_native':'Dansk','flag_emoji':'🇩🇰','locale_code':'da_DK','bcp47_code':'da-DK','iso_639_1':'da','iso_639_2':'dan'},
    {'code':'no','name':'Norwegian','name_native':'Norsk','flag_emoji':'🇳🇴','locale_code':'nb_NO','bcp47_code':'nb-NO','iso_639_1':'no','iso_639_2':'nor'},
    {'code':'fi','name':'Finnish','name_native':'Suomi','flag_emoji':'🇫🇮','locale_code':'fi_FI','bcp47_code':'fi-FI','iso_639_1':'fi','iso_639_2':'fin'},
    {'code':'el','name':'Greek','name_native':'Ελληνικά','flag_emoji':'🇬🇷','locale_code':'el_GR','bcp47_code':'el-GR','iso_639_1':'el','iso_639_2':'ell','script_code':'Grek'},
    {'code':'bg','name':'Bulgarian','name_native':'Български','flag_emoji':'🇧🇬','locale_code':'bg_BG','bcp47_code':'bg-BG','iso_639_1':'bg','iso_639_2':'bul','script_code':'Cyrl'},
    {'code':'hr','name':'Croatian','name_native':'Hrvatski','flag_emoji':'🇭🇷','locale_code':'hr_HR','bcp47_code':'hr-HR','iso_639_1':'hr','iso_639_2':'hrv'},
    {'code':'sr','name':'Serbian','name_native':'Српски','flag_emoji':'🇷🇸','locale_code':'sr_RS','bcp47_code':'sr-Cyrl','iso_639_1':'sr','iso_639_2':'srp','script_code':'Cyrl'},
    {'code':'lt','name':'Lithuanian','name_native':'Lietuvių','flag_emoji':'🇱🇹','locale_code':'lt_LT','bcp47_code':'lt-LT','iso_639_1':'lt','iso_639_2':'lit'},
    {'code':'lv','name':'Latvian','name_native':'Latviešu','flag_emoji':'🇱🇻','locale_code':'lv_LV','bcp47_code':'lv-LV','iso_639_1':'lv','iso_639_2':'lav'},
    {'code':'et','name':'Estonian','name_native':'Eesti','flag_emoji':'🇪🇪','locale_code':'et_EE','bcp47_code':'et-EE','iso_639_1':'et','iso_639_2':'est'},
    {'code':'af','name':'Afrikaans','name_native':'Afrikaans','flag_emoji':'🇿🇦','locale_code':'af_ZA','bcp47_code':'af-ZA','iso_639_1':'af','iso_639_2':'afr'},
    {'code':'sw','name':'Swahili','name_native':'Kiswahili','flag_emoji':'🇰🇪','locale_code':'sw_KE','bcp47_code':'sw-KE','iso_639_1':'sw','iso_639_2':'swa'},
    {'code':'am','name':'Amharic','name_native':'አማርኛ','flag_emoji':'🇪🇹','locale_code':'am_ET','bcp47_code':'am-ET','iso_639_1':'am','iso_639_2':'amh','script_code':'Ethi'},
]

class Command(BaseCommand):
    help = '50+ languages seed করে'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Existing records overwrite করে')

    def handle(self, *args, **options):
        from localization.models.core import Language
        force = options.get('force', False)
        created = updated = skipped = 0
        with transaction.atomic():
            for lang_data in LANGUAGES:
                code = lang_data.pop('code')
                if force:
                    obj, was_created = Language.objects.update_or_create(code=code, defaults=lang_data)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                else:
                    obj, was_created = Language.objects.get_or_create(code=code, defaults=lang_data)
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                lang_data['code'] = code  # restore
        self.stdout.write(self.style.SUCCESS(
            f'Languages seeded: {created} created, {updated} updated, {skipped} skipped'
        ))
