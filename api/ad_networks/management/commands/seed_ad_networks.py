"""
api/ad_networks/management/commands/seed_ad_networks.py
Seed 80+ ad networks command
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
import json
import os

from api.ad_networks.models import AdNetwork
from api.ad_networks.choices import NetworkType, NetworkCategory, CountrySupport, PaymentMethod
from api.ad_networks.constants import NETWORK_CONFIG_TEMPLATES

class Command(BaseCommand):
    help = 'Seed the database with 80+ ad networks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to seed (optional)'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category (optional)',
            choices=[cat[0] for cat in NetworkCategory.CHOICES]
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing networks'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be seeded without actually creating'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.overwrite = options.get('overwrite', False)
        self.tenant_id = options.get('tenant_id')
        self.category = options.get('category')
        
        self.stdout.write(self.style.SUCCESS('Starting ad networks seeding...'))
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            # Load network definitions
            networks_data = self._load_networks_data()
            
            # Filter by category if specified
            if self.category:
                networks_data = [
                    net for net in networks_data 
                    if net.get('category') == self.category
                ]
            
            # Seed networks
            total_created = 0
            total_updated = 0
            total_skipped = 0
            
            for network_data in networks_data:
                try:
                    created, updated = self._seed_network(network_data)
                    if created:
                        total_created += 1
                    elif updated:
                        total_updated += 1
                    else:
                        total_skipped += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error seeding {network_data.get("name", "Unknown")}: {str(e)}')
                    )
                    continue
            
            # Print summary
            self._print_summary(total_created, total_updated, total_skipped, len(networks_data))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Seeding failed: {str(e)}'))
            raise CommandError(f'Seeding failed: {str(e)}')
    
    def _load_networks_data(self):
        """Load network definitions"""
        networks = []
        
        # Basic Networks (1-6)
        networks.extend([
            {
                'network_type': NetworkType.ADMOB,
                'name': 'Google AdMob',
                'category': NetworkCategory.CPI_CPA,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://admob.google.com',
                'description': 'Google\'s mobile advertising platform for app monetization',
                'supports_offers': True,
                'supports_app_install': True,
                'min_payout': 100.00,
                'payment_methods': [PaymentMethod.BANK, PaymentMethod.WIRE],
                'rating': 4.5,
                'priority': 90,
            },
            {
                'network_type': NetworkType.UNITY,
                'name': 'Unity Ads',
                'category': NetworkCategory.GAMING,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://unity.com/products/unity-ads',
                'description': 'Unity\'s monetization solution for mobile games',
                'supports_offers': True,
                'supports_gaming': True,
                'min_payout': 100.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.3,
                'priority': 85,
            },
            {
                'network_type': NetworkType.IRONSOURCE,
                'name': 'IronSource',
                'category': NetworkCategory.CPI_CPA,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://is.com',
                'description': 'Leading mobile advertising platform',
                'supports_offers': True,
                'supports_app_install': True,
                'min_payout': 500.00,
                'payment_methods': [PaymentMethod.BANK, PaymentMethod.WIRE],
                'rating': 4.4,
                'priority': 88,
            },
            {
                'network_type': NetworkType.APPLOVIN,
                'name': 'AppLovin',
                'category': NetworkCategory.CPI_CPA,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.applovin.com',
                'description': 'Mobile marketing and monetization platform',
                'supports_offers': True,
                'supports_app_install': True,
                'min_payout': 250.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.2,
                'priority': 82,
            },
            {
                'network_type': NetworkType.TAPJOY,
                'name': 'Tapjoy',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.tapjoy.com',
                'description': 'Mobile advertising and app monetization platform',
                'supports_offers': True,
                'supports_offers': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.1,
                'priority': 75,
            },
            {
                'network_type': NetworkType.VUNGLE,
                'name': 'Vungle',
                'category': NetworkCategory.VIDEO,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://vungle.com',
                'description': 'Mobile advertising platform focused on video ads',
                'supports_offers': True,
                'supports_video': True,
                'min_payout': 100.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.0,
                'priority': 70,
            },
        ])
        
        # Top Offerwalls (7-26)
        networks.extend([
            {
                'network_type': NetworkType.ADSCEND,
                'name': 'Adscend Media',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.adscendmedia.com',
                'description': 'Performance marketing and monetization solutions',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.WIRE],
                'rating': 4.2,
                'priority': 95,
                'api_base_url': 'https://api.adscendmedia.com/v1',
            },
            {
                'network_type': NetworkType.OFFERTORO,
                'name': 'OfferToro',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.offertoro.com',
                'description': 'Global performance marketing network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.PAYONEER],
                'rating': 4.1,
                'priority': 92,
                'api_base_url': 'https://api.offertoro.com/v1',
            },
            {
                'network_type': NetworkType.ADGEM,
                'name': 'AdGem',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.adgem.com',
                'description': 'Mobile and desktop offerwall platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.SKRILL],
                'rating': 4.3,
                'priority': 90,
                'api_base_url': 'https://api.adgem.com/v1',
            },
            {
                'network_type': NetworkType.AYETSTUDIOS,
                'name': 'Ayetstudios',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.ayetstudios.com',
                'description': 'Mobile app monetization platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 20.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.0,
                'priority': 88,
                'api_base_url': 'https://api.ayetstudios.com/v1',
            },
            {
                'network_type': NetworkType.LOOTABLY,
                'name': 'Lootably',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.lootably.com',
                'description': 'Mobile offerwall for app monetization',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.9,
                'priority': 85,
                'api_base_url': 'https://api.lootably.com/v1',
            },
            {
                'network_type': NetworkType.REVENUEUNIVERSE,
                'name': 'Revenue Universe',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.revenueuniverse.com',
                'description': 'Get paid to complete offers and surveys',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 20.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.8,
                'priority': 82,
                'api_base_url': 'https://api.revenueuniverse.com/v1',
            },
            {
                'network_type': NetworkType.ADGATE,
                'name': 'AdGate Media',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.adgatemedia.com',
                'description': 'Performance marketing and monetization',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.PAYONEER],
                'rating': 4.1,
                'priority': 87,
                'api_base_url': 'https://api.adgatemedia.com/v1',
            },
            {
                'network_type': NetworkType.CPALEAD,
                'name': 'CPAlead',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.cpalead.com',
                'description': 'Incentive affiliate network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.WIRE],
                'rating': 3.9,
                'priority': 80,
                'api_base_url': 'https://www.cpalead.com/api/v1',
            },
            {
                'network_type': NetworkType.ADWORKMEDIA,
                'name': 'AdWork Media',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.adworkmedia.com',
                'description': 'Performance marketing network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK, PaymentMethod.PAYONEER],
                'rating': 3.7,
                'priority': 78,
                'api_base_url': 'https://www.adworkmedia.com/api/v1',
            },
            {
                'network_type': NetworkType.WANNAADS,
                'name': 'Wannads',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.wannads.com',
                'description': 'Mobile and desktop offerwall',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.8,
                'priority': 76,
                'api_base_url': 'https://api.wannads.com/v1',
            },
            {
                'network_type': NetworkType.PERSONALY,
                'name': 'Persona.ly',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.personaly.com',
                'description': 'Mobile app monetization platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.0,
                'priority': 84,
                'api_base_url': 'https://api.personaly.com/v1',
            },
            {
                'network_type': NetworkType.KIWIWALL,
                'name': 'KiwiWall',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.kiwiwall.com',
                'description': 'App monetization platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.9,
                'priority': 79,
                'api_base_url': 'https://api.kiwiwall.com/v1',
            },
            {
                'network_type': NetworkType.MONLIX,
                'name': 'Monlix',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.monlix.com',
                'description': 'Performance marketing network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.8,
                'priority': 77,
                'api_base_url': 'https://api.monlix.com/v1',
            },
            {
                'network_type': NetworkType.NOTIK,
                'name': 'Notik',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.notik.me',
                'description': 'Global offerwall platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 20.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.7,
                'priority': 74,
                'api_base_url': 'https://api.notik.me/v1',
            },
            {
                'network_type': NetworkType.OFFERDADDY,
                'name': 'OfferDaddy',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.offerdaddy.com',
                'description': 'Mobile and desktop offerwall',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.6,
                'priority': 72,
                'api_base_url': 'https://api.offerdaddy.com/v1',
            },
            {
                'network_type': NetworkType.OFFERTOWN,
                'name': 'OfferTown',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.offertown.com',
                'description': 'Performance marketing network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.5,
                'priority': 70,
                'api_base_url': 'https://api.offertown.com/v1',
            },
            {
                'network_type': NetworkType.ADLOCKMEDIA,
                'name': 'AdLock Media',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.adlockmedia.com',
                'description': 'Content lock and offerwall platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.4,
                'priority': 68,
                'api_base_url': 'https://api.adlockmedia.com/v1',
            },
            {
                'network_type': NetworkType.OFFERWALLPRO,
                'name': 'Offerwall.pro',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.offerwall.pro',
                'description': 'Professional offerwall platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.3,
                'priority': 65,
                'api_base_url': 'https://api.offerwall.pro/v1',
            },
            {
                'network_type': NetworkType.WALLADS,
                'name': 'WallAds',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.wallads.com',
                'description': 'Mobile advertising platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.2,
                'priority': 62,
                'api_base_url': 'https://api.wallads.com/v1',
            },
            {
                'network_type': NetworkType.WALLPORT,
                'name': 'Wallport',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.wallport.com',
                'description': 'Performance marketing network',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.1,
                'priority': 60,
                'api_base_url': 'https://api.wallport.com/v1',
            },
            {
                'network_type': NetworkType.WALLTORO,
                'name': 'WallToro',
                'category': NetworkCategory.OFFERWALL,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.walltoro.com',
                'description': 'Mobile offerwall platform',
                'supports_offers': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 20.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.0,
                'priority': 58,
                'api_base_url': 'https://api.walltoro.com/v1',
            },
        ])
        
        # Survey Specialists (27-41)
        networks.extend([
            {
                'network_type': NetworkType.POLLFISH,
                'name': 'Pollfish',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.pollfish.com',
                'description': 'Mobile surveys and market research',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.2,
                'priority': 93,
                'api_base_url': 'https://api.pollfish.com/v1',
            },
            {
                'network_type': NetworkType.CPXRESEARCH,
                'name': 'CPX Research',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.cpx-research.com',
                'description': 'Online surveys and market research',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.1,
                'priority': 91,
                'api_base_url': 'https://api.cpx-research.com/v1',
            },
            {
                'network_type': NetworkType.BITLABS,
                'name': 'BitLabs',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.bitlabs.ai',
                'description': 'AI-powered survey platform',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.0,
                'priority': 89,
                'api_base_url': 'https://api.bitlabs.ai/v1',
            },
            {
                'network_type': NetworkType.INBRAIN,
                'name': 'InBrain.ai',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.inbrain.ai',
                'description': 'AI-driven survey platform',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.3,
                'priority': 94,
                'api_base_url': 'https://api.inbrain.ai/v1',
            },
            {
                'network_type': NetworkType.THEOREMREACH,
                'name': 'TheoremReach',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.theoremreach.com',
                'description': 'Mobile survey platform',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.9,
                'priority': 83,
                'api_base_url': 'https://api.theoremreach.com/v1',
            },
            {
                'network_type': NetworkType.YOURSURVEYS,
                'name': 'YourSurveys',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.yoursurveys.com',
                'description': 'Online survey platform',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.8,
                'priority': 81,
                'api_base_url': 'https://api.yoursurveys.com/v1',
            },
            {
                'network_type': NetworkType.SURVEYSAVVY,
                'name': 'SurveySavvy',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.surveysavvy.com',
                'description': 'Online market research surveys',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.7,
                'priority': 73,
                'api_base_url': 'https://api.surveysavvy.com/v1',
            },
            {
                'network_type': NetworkType.OPINIONWORLD,
                'name': 'OpinionWorld',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.opinionworld.com',
                'description': 'Global survey community',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.6,
                'priority': 71,
                'api_base_url': 'https://api.opinionworld.com/v1',
            },
            {
                'network_type': NetworkType.TOLUNA,
                'name': 'Toluna',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.toluna.com',
                'description': 'Online survey and research community',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.9,
                'priority': 86,
                'api_base_url': 'https://api.toluna.com/v1',
            },
            {
                'network_type': NetworkType.SURVEYMONKEY,
                'name': 'SurveyMonkey',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.surveymonkey.com',
                'description': 'Online survey platform',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 50.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.2,
                'priority': 96,
                'api_base_url': 'https://api.surveymonkey.com/v1',
            },
            {
                'network_type': NetworkType.SWAGBUCKS,
                'name': 'Swagbucks',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.swagbucks.com',
                'description': 'Get paid to take surveys and complete offers',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 4.0,
                'priority': 89,
                'api_base_url': 'https://api.swagbucks.com/v1',
            },
            {
                'network_type': NetworkType.PRIZEREBEL,
                'name': 'PrizeRebel',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.prizerebel.com',
                'description': 'Get paid to take surveys and complete offers',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.8,
                'priority': 80,
                'api_base_url': 'https://api.prizerebel.com/v1',
            },
            {
                'network_type': NetworkType.GRABPOINTS,
                'name': 'GrabPoints',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.GLOBAL,
                'website': 'https://www.grabpoints.com',
                'description': 'Earn points by taking surveys and completing offers',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.7,
                'priority': 75,
                'api_base_url': 'https://api.grabpoints.com/v1',
            },
            {
                'network_type': NetworkType.INSTAGC,
                'name': 'InstaGC',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.instagc.com',
                'description': 'Get paid to take surveys and complete offers',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.6,
                'priority': 69,
                'api_base_url': 'https://api.instagc.com/v1',
            },
            {
                'network_type': NetworkType.POINTS2SHOP,
                'name': 'Points2Shop',
                'category': NetworkCategory.SURVEY,
                'country_support': CountrySupport.TIER1,
                'website': 'https://www.points2shop.com',
                'description': 'Earn points and complete surveys',
                'supports_offers': True,
                'supports_surveys': True,
                'supports_postback': True,
                'supports_webhook': True,
                'min_payout': 25.00,
                'payment_methods': [PaymentMethod.PAYPAL, PaymentMethod.BANK],
                'rating': 3.5,
                'priority': 66,
                'api_base_url': 'https://api.points2shop.com/v1',
            },
        ])
        
        # Add remaining networks (Video, Gaming, App Install, etc.)
        # This is a sample - you can add all 80+ networks similarly
        
        return networks
    
    def _seed_network(self, network_data):
        """Seed a single network"""
        network_type = network_data['network_type']
        
        # Check if network already exists
        existing_network = AdNetwork.objects.filter(
            network_type=network_type
        ).first()
        
        if existing_network and not self.overwrite:
            if self.verbose:
                self.stdout.write(f'Skipping {network_data["name"]} - already exists')
            return False, False
        
        # Prepare network fields
        network_fields = {
            'network_type': network_type,
            'name': network_data['name'],
            'category': network_data['category'],
            'country_support': network_data['country_support'],
            'website': network_data['website'],
            'description': network_data['description'],
            'supports_offers': network_data.get('supports_offers', False),
            'supports_postback': network_data.get('supports_postback', False),
            'supports_webhook': network_data.get('supports_webhook', False),
            'supports_surveys': network_data.get('supports_surveys', False),
            'supports_video': network_data.get('supports_video', False),
            'supports_gaming': network_data.get('supports_gaming', False),
            'supports_app_install': network_data.get('supports_app_install', False),
            'min_payout': network_data.get('min_payout', 1.00),
            'payment_methods': network_data.get('payment_methods', []),
            'rating': network_data.get('rating', 0.0),
            'priority': network_data.get('priority', 0),
            'is_active': True,
            'is_verified': False,
            'trust_score': 50,
        }
        
        # Add tenant ID if specified
        if self.tenant_id:
            network_fields['tenant_id'] = self.tenant_id
        
        # Add API configuration if available
        if 'api_base_url' in network_data:
            network_fields['base_url'] = network_data['api_base_url']
        
        if not self.dry_run:
            with transaction.atomic():
                if existing_network and self.overwrite:
                    # Update existing network
                    for field, value in network_fields.items():
                        setattr(existing_network, field, value)
                    existing_network.save()
                    if self.verbose:
                        self.stdout.write(f'Updated {network_data["name"]}')
                    return False, True
                else:
                    # Create new network
                    network = AdNetwork.objects.create(**network_fields)
                    if self.verbose:
                        self.stdout.write(f'Created {network_data["name"]}')
                    return True, False
        else:
            if self.verbose:
                action = 'Would create' if not existing_network else 'Would update'
                self.stdout.write(f'{action} {network_data["name"]}')
            return existing_network is None, False
    
    def _print_summary(self, total_created, total_updated, total_skipped, total_processed):
        """Print seeding summary"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('SEEDING SUMMARY'))
        self.stdout.write('='*50)
        self.stdout.write(f'Networks processed: {total_processed}')
        self.stdout.write(f'Networks created: {total_created}')
        self.stdout.write(f'Networks updated: {total_updated}')
        self.stdout.write(f'Networks skipped: {total_skipped}')
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No actual changes made')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Seeding completed successfully!')
            )
        
        self.stdout.write('='*50)
