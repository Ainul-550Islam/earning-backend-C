from django.urls import path
from .views import (
    # Basic Networks (1-6)
    AdMobWebhookView, UnityAdsWebhookView, IronSourceWebhookView,
    AppLovinWebhookView, TapjoyWebhookView, VungleWebhookView,
    
    # Top Offerwalls (7-26)
    AdscendWebhookView, OfferToroWebhookView, AdGemWebhookView,
    AyetStudiosWebhookView, LootablyWebhookView, RevenueUniverseWebhookView,
    AdGateWebhookView, CPAleadWebhookView, AdWorkMediaWebhookView,
    WannadsWebhookView, PersonaLyWebhookView, KiwiWallWebhookView,
    MonlixWebhookView, NotikWebhookView, OfferDaddyWebhookView,
    OfferTownWebhookView, AdLockMediaWebhookView, OfferwallProWebhookView,
    WallAdsWebhookView, WallportWebhookView, WallToroWebhookView,
    
    # Survey Specialists (27-41)
    PollfishWebhookView, CPXResearchWebhookView, BitLabsWebhookView,
    InBrainWebhookView, TheoremReachWebhookView, YourSurveysWebhookView,
    SurveySavvyWebhookView, OpinionWorldWebhookView, TolunaWebhookView,
    SurveyMonkeyWebhookView, SwagbucksWebhookView, PrizeRebelWebhookView,
    GrabPointsWebhookView, InstaGCWebhookView, Points2ShopWebhookView,
    
    # Video & Easy Tasks (42-56)
    LootTVWebhookView, HideoutTVWebhookView, RewardRackWebhookView,
    EarnHoneyWebhookView, RewardXPWebhookView, IdleEmpireWebhookView,
    GainWebhookView, GrindaBuckWebhookView, TimeBucksWebhookView,
    ClixSenseWebhookView, NeoBuxWebhookView, ProBuxWebhookView,
    ClixWallWebhookView, FyberWebhookView, OfferStationWebhookView,
    
    # Gaming & App Install (57-70)
    ChartboostWebhookView, SupersonicWebhookView, AppNextWebhookView,
    DigitalTurbineWebhookView, GlispaWebhookView, AdColonyWebhookView,
    InMobiWebhookView, MoPubWebhookView, PangleWebhookView,
    MintegralWebhookView, OguryWebhookView, VerizonMediaWebhookView,
    SmaatoWebhookView, MobileFuseWebhookView,
    
    # More Networks (71-80)
    LeadboltWebhookView, StartAppWebhookView, MediabrixWebhookView,
    NativeXWebhookView, HeyzapWebhookView, KidozWebhookView,
    PokktWebhookView, YouAppiWebhookView, AmpiriWebhookView,
    AdinCubeWebhookView,
    
    # Future Expansion (81-90)
    CustomNetwork1WebhookView, CustomNetwork2WebhookView,
    CustomNetwork3WebhookView, CustomNetwork4WebhookView, CustomNetwork5WebhookView,
)

urlpatterns = [
    # Basic Networks (1-6)
    path('admob/', AdMobWebhookView.as_view(), name='admob-webhook'),
    path('unity/', UnityAdsWebhookView.as_view(), name='unity-webhook'),
    path('ironsource/', IronSourceWebhookView.as_view(), name='ironsource-webhook'),
    path('applovin/', AppLovinWebhookView.as_view(), name='applovin-webhook'),
    path('tapjoy/', TapjoyWebhookView.as_view(), name='tapjoy-webhook'),
    path('vungle/', VungleWebhookView.as_view(), name='vungle-webhook'),
    
    # Top Offerwalls (7-26)
    path('adscend/', AdscendWebhookView.as_view(), name='adscend-webhook'),
    path('offertoro/', OfferToroWebhookView.as_view(), name='offertoro-webhook'),
    path('adgem/', AdGemWebhookView.as_view(), name='adgem-webhook'),
    path('ayetstudios/', AyetStudiosWebhookView.as_view(), name='ayetstudios-webhook'),
    path('lootably/', LootablyWebhookView.as_view(), name='lootably-webhook'),
    path('revenueuniverse/', RevenueUniverseWebhookView.as_view(), name='revenueuniverse-webhook'),
    path('adgate/', AdGateWebhookView.as_view(), name='adgate-webhook'),
    path('cpalead/', CPAleadWebhookView.as_view(), name='cpalead-webhook'),
    path('adworkmedia/', AdWorkMediaWebhookView.as_view(), name='adworkmedia-webhook'),
    path('wannads/', WannadsWebhookView.as_view(), name='wannads-webhook'),
    path('personaly/', PersonaLyWebhookView.as_view(), name='personaly-webhook'),
    path('kiwiwall/', KiwiWallWebhookView.as_view(), name='kiwiwall-webhook'),
    path('monlix/', MonlixWebhookView.as_view(), name='monlix-webhook'),
    path('notik/', NotikWebhookView.as_view(), name='notik-webhook'),
    path('offerdaddy/', OfferDaddyWebhookView.as_view(), name='offerdaddy-webhook'),
    path('offertown/', OfferTownWebhookView.as_view(), name='offertown-webhook'),
    path('adlockmedia/', AdLockMediaWebhookView.as_view(), name='adlockmedia-webhook'),
    path('offerwallpro/', OfferwallProWebhookView.as_view(), name='offerwallpro-webhook'),
    path('wallads/', WallAdsWebhookView.as_view(), name='wallads-webhook'),
    path('wallport/', WallportWebhookView.as_view(), name='wallport-webhook'),
    path('walltoro/', WallToroWebhookView.as_view(), name='walltoro-webhook'),
    
    # Survey Specialists (27-41)
    path('pollfish/', PollfishWebhookView.as_view(), name='pollfish-webhook'),
    path('cpxresearch/', CPXResearchWebhookView.as_view(), name='cpxresearch-webhook'),
    path('bitlabs/', BitLabsWebhookView.as_view(), name='bitlabs-webhook'),
    path('inbrain/', InBrainWebhookView.as_view(), name='inbrain-webhook'),
    path('theoremreach/', TheoremReachWebhookView.as_view(), name='theoremreach-webhook'),
    path('yoursurveys/', YourSurveysWebhookView.as_view(), name='yoursurveys-webhook'),
    path('surveysavvy/', SurveySavvyWebhookView.as_view(), name='surveysavvy-webhook'),
    path('opinionworld/', OpinionWorldWebhookView.as_view(), name='opinionworld-webhook'),
    path('toluna/', TolunaWebhookView.as_view(), name='toluna-webhook'),
    path('surveymonkey/', SurveyMonkeyWebhookView.as_view(), name='surveymonkey-webhook'),
    path('swagbucks/', SwagbucksWebhookView.as_view(), name='swagbucks-webhook'),
    path('prizerebel/', PrizeRebelWebhookView.as_view(), name='prizerebel-webhook'),
    path('grabpoints/', GrabPointsWebhookView.as_view(), name='grabpoints-webhook'),
    path('instagc/', InstaGCWebhookView.as_view(), name='instagc-webhook'),
    path('points2shop/', Points2ShopWebhookView.as_view(), name='points2shop-webhook'),
    
    # Video & Easy Tasks (42-56)
    path('loottv/', LootTVWebhookView.as_view(), name='loottv-webhook'),
    path('hideouttv/', HideoutTVWebhookView.as_view(), name='hideouttv-webhook'),
    path('rewardrack/', RewardRackWebhookView.as_view(), name='rewardrack-webhook'),
    path('earnhoney/', EarnHoneyWebhookView.as_view(), name='earnhoney-webhook'),
    path('rewardxp/', RewardXPWebhookView.as_view(), name='rewardxp-webhook'),
    path('idleempire/', IdleEmpireWebhookView.as_view(), name='idleempire-webhook'),
    path('gain/', GainWebhookView.as_view(), name='gain-webhook'),
    path('grindabuck/', GrindaBuckWebhookView.as_view(), name='grindabuck-webhook'),
    path('timebucks/', TimeBucksWebhookView.as_view(), name='timebucks-webhook'),
    path('clixsense/', ClixSenseWebhookView.as_view(), name='clixsense-webhook'),
    path('neobux/', NeoBuxWebhookView.as_view(), name='neobux-webhook'),
    path('probux/', ProBuxWebhookView.as_view(), name='probux-webhook'),
    path('clixwall/', ClixWallWebhookView.as_view(), name='clixwall-webhook'),
    path('fyber/', FyberWebhookView.as_view(), name='fyber-webhook'),
    path('offerstation/', OfferStationWebhookView.as_view(), name='offerstation-webhook'),
    
    # Gaming & App Install (57-70)
    path('chartboost/', ChartboostWebhookView.as_view(), name='chartboost-webhook'),
    path('supersonic/', SupersonicWebhookView.as_view(), name='supersonic-webhook'),
    path('appnext/', AppNextWebhookView.as_view(), name='appnext-webhook'),
    path('digitalturbine/', DigitalTurbineWebhookView.as_view(), name='digitalturbine-webhook'),
    path('glispa/', GlispaWebhookView.as_view(), name='glispa-webhook'),
    path('adcolony/', AdColonyWebhookView.as_view(), name='adcolony-webhook'),
    path('inmobi/', InMobiWebhookView.as_view(), name='inmobi-webhook'),
    path('mopub/', MoPubWebhookView.as_view(), name='mopub-webhook'),
    path('pangle/', PangleWebhookView.as_view(), name='pangle-webhook'),
    path('mintegral/', MintegralWebhookView.as_view(), name='mintegral-webhook'),
    path('ogury/', OguryWebhookView.as_view(), name='ogury-webhook'),
    path('verizonmedia/', VerizonMediaWebhookView.as_view(), name='verizonmedia-webhook'),
    path('smaato/', SmaatoWebhookView.as_view(), name='smaato-webhook'),
    path('mobilefuse/', MobileFuseWebhookView.as_view(), name='mobilefuse-webhook'),
    
    # More Networks (71-80)
    path('leadbolt/', LeadboltWebhookView.as_view(), name='leadbolt-webhook'),
    path('startapp/', StartAppWebhookView.as_view(), name='startapp-webhook'),
    path('mediabrix/', MediabrixWebhookView.as_view(), name='mediabrix-webhook'),
    path('nativex/', NativeXWebhookView.as_view(), name='nativex-webhook'),
    path('heyzap/', HeyzapWebhookView.as_view(), name='heyzap-webhook'),
    path('kidoz/', KidozWebhookView.as_view(), name='kidoz-webhook'),
    path('pokkt/', PokktWebhookView.as_view(), name='pokkt-webhook'),
    path('youappi/', YouAppiWebhookView.as_view(), name='youappi-webhook'),
    path('ampiri/', AmpiriWebhookView.as_view(), name='ampiri-webhook'),
    path('adincube/', AdinCubeWebhookView.as_view(), name='adincube-webhook'),
    
    # Future Expansion (81-90)
    path('custom1/', CustomNetwork1WebhookView.as_view(), name='custom1-webhook'),
    path('custom2/', CustomNetwork2WebhookView.as_view(), name='custom2-webhook'),
    path('custom3/', CustomNetwork3WebhookView.as_view(), name='custom3-webhook'),
    path('custom4/', CustomNetwork4WebhookView.as_view(), name='custom4-webhook'),
    path('custom5/', CustomNetwork5WebhookView.as_view(), name='custom5-webhook'),
]