"""
adapters/networks.py – All 91 network adapters for postback/adapters/

Bridges our postback app adapter interface with postback_engine's
BaseNetworkAdapter, which handles field mapping, status normalisation,
and macro expansion.

Networks are grouped by category:
  Group A: Top Offerwalls (CPAlead, AdGate, AdScend, OfferToro, etc.)
  Group B: Survey Networks (Pollfish, CPX Research, BitLabs, etc.)
  Group C: GPT / Reward Sites (Swagbucks, PrizeRebel, etc.)
  Group D: Video/Task Networks (HideoutTV, LoottV, EarnHoney, etc.)
  Group E: Mobile Ad Networks (AdMob, Unity, IronSource, AppLovin, etc.)
  Group F: DSP / Programmatic (Fyber, AdColony, Chartboost, etc.)
  Group G: Custom slots (custom1–custom10)
"""
from .base import BasePostbackAdapter


# ─────────────────────────────────────────────────────────────────────────────
# BASE BRIDGE — wraps postback_engine.BaseNetworkAdapter interface
# ─────────────────────────────────────────────────────────────────────────────

class EngineAdapterBridge(BasePostbackAdapter):
    """
    Bridge between our BasePostbackAdapter and postback_engine adapters.
    Subclasses set FIELD_MAP + STATUS_MAP; adapt() applies them.
    """
    network_keys: list = []
    FIELD_MAP: dict = {}
    STATUS_MAP: dict = {}

    def adapt(self, raw_payload: dict, network_config) -> dict:
        try:
            fm = getattr(network_config, "field_mapping", {}) or {}
            merged = {**self.FIELD_MAP, **fm}
            adapted = {}

            for std_name, net_param in merged.items():
                val = self._get(raw_payload, net_param, default="")
                if val:
                    adapted[std_name] = val

            # Standard fields with aliases
            adapted.setdefault("lead_id",         self._get(raw_payload, "lead_id","click_id","sub1","aff_sub","lid","cid"))
            adapted.setdefault("offer_id",        self._get(raw_payload, "offer_id","oid","campaign_id","aff_id"))
            adapted.setdefault("user_id",         self._get(raw_payload, "user_id","uid","pub_id","publisher_id","pid"))
            adapted.setdefault("payout",          self._get_decimal(raw_payload, "payout","amount","commission","revenue","usd"))
            adapted.setdefault("currency",        self._get(raw_payload, "currency","cur", default="USD"))
            adapted.setdefault("transaction_id",  self._get(raw_payload, "transaction_id","txn_id","tid","sid","trans_id","conversion_id"))
            adapted.setdefault("timestamp",       self._get(raw_payload, "timestamp","ts","time","datetime"))
            adapted.setdefault("goal_id",         self._get(raw_payload, "goal_id","goal","event","event_id","type","goal_name"))
            adapted.setdefault("sub_id1",         self._get(raw_payload, "sub1","sub_id","aff_sub","s1","subid"))
            adapted.setdefault("sub_id2",         self._get(raw_payload, "sub2","sub_id2","aff_sub2","s2"))
            adapted.setdefault("sub_id3",         self._get(raw_payload, "sub3","sub_id3","aff_sub3","s3"))
            adapted.setdefault("country",         self._get(raw_payload, "country","geo","country_code","cc"))
            adapted.setdefault("device",          self._get(raw_payload, "device","device_type","platform"))
            adapted.setdefault("os",              self._get(raw_payload, "os","operating_system","os_name"))

            # Status normalisation
            raw_status = self._get(raw_payload, "status","conversion_status","state", default="1")
            adapted["cpalead_status"] = self._normalise_status(raw_status)
            adapted["is_reversal"] = adapted["cpalead_status"] in ("rejected","reversed","chargeback","fraud")
            adapted["event_type"] = self._derive_event_type(adapted.get("goal_id",""))
            adapted["_adapter"] = self.__class__.__name__
            adapted["_network_key"] = getattr(network_config, "network_key", "")
            return adapted

        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Adapter %s error: %s", self.__class__.__name__, exc)
            return {"_error": str(exc), "_raw": raw_payload}

    def _normalise_status(self, raw: str) -> str:
        v = str(raw).lower().strip()
        approved = {"1","approved","approve","success","paid","confirmed","accepted","true","yes","converted","rewarded","complete"}
        rejected = {"0","rejected","reject","failed","declined","fraud","chargeback","reversed","refunded","no","false"}
        pending  = {"2","pending","hold","review","processing","waiting"}
        if v in self.STATUS_MAP: return self.STATUS_MAP[v]
        if v in approved: return "approved"
        if v in rejected: return "reversed"
        if v in pending:  return "pending"
        return "approved"

    def _derive_event_type(self, goal_id: str) -> str:
        if not goal_id: return "unknown"
        g = goal_id.lower()
        for kw,ev in [("install","install"),("app","install"),("sale","sale"),("purchase","sale"),
                      ("order","sale"),("lead","lead"),("form","lead"),("submit","lead"),
                      ("signup","registration"),("register","registration"),("registration","registration"),
                      ("trial","trial"),("deposit","deposit"),("ftd","deposit"),
                      ("survey","survey"),("video","video"),("view","video"),
                      ("subscription","subscription"),("sub","subscription")]:
            if kw in g: return ev
        return "custom"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP A: TOP OFFERWALLS
# ─────────────────────────────────────────────────────────────────────────────

class CPALeadNetworkAdapter(EngineAdapterBridge):
    """CPAlead — GET postback, sub1=user, oid=offer, amount=payout, sid=txn"""
    network_keys = ["cpalead", "cpa_lead", "cpaleadnet"]
    FIELD_MAP = {"lead_id":"sub1","offer_id":"oid","payout":"amount",
                 "transaction_id":"sid","sub_id1":"sub2","user_id":"sub3","goal_id":"goal"}

    def is_lead_reversed(self, adapted: dict) -> bool:
        return adapted.get("cpalead_status", "") in ("reversed","chargeback","rejected")

    def is_lead_pending(self, adapted: dict) -> bool:
        return adapted.get("cpalead_status", "") == "pending"

class AdGateMediaAdapter(EngineAdapterBridge):
    """AdGate Media — GET postback"""
    network_keys = ["adgate","adgatemedia","adgate_media"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id","sub_id1":"sub_id"}

class AdScendMediaAdapter(EngineAdapterBridge):
    """AdScend Media — GET postback, uid=user"""
    network_keys = ["adscend","adscendmedia","adscend_media"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"payout",
                 "transaction_id":"tid","sub_id1":"sid"}

class OfferToroAdapter(EngineAdapterBridge):
    """OfferToro — GET postback"""
    network_keys = ["offertoro","offer_toro"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id","sub_id1":"sub_id1","sub_id2":"sub_id2"}

class AdGemAdapter(EngineAdapterBridge):
    """AdGem — GET postback, player_id=user"""
    network_keys = ["adgem","ad_gem"]
    FIELD_MAP = {"lead_id":"player_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class AyetStudiosAdapter(EngineAdapterBridge):
    """Ayet Studios — GET postback"""
    network_keys = ["ayetstudios","ayet_studios","ayet"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id","sub_id1":"custom_1","sub_id2":"custom_2"}

class LootablyAdapter(EngineAdapterBridge):
    """Lootably — GET postback"""
    network_keys = ["lootably","loot_ably"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id","sub_id1":"pub_sub_id"}

class RevenueUniverseAdapter(EngineAdapterBridge):
    """Revenue Universe — GET postback, user_external_id=user"""
    network_keys = ["revenueuniverse","revenue_universe","revuniv"]
    FIELD_MAP = {"lead_id":"user_external_id","offer_id":"campaign_id","payout":"payout",
                 "transaction_id":"transaction_id"}

class AdWorkMediaAdapter(EngineAdapterBridge):
    """AdWork Media — GET postback"""
    network_keys = ["adworkmedia","adwork_media","adwork"]
    FIELD_MAP = {"lead_id":"user","offer_id":"oid","payout":"payout",
                 "transaction_id":"tid","sub_id1":"sub1","sub_id2":"sub2"}

class WannadsAdapter(EngineAdapterBridge):
    """Wannads — GET postback"""
    network_keys = ["wannads"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"points",
                 "transaction_id":"trans_id"}

class PersonalyAdapter(EngineAdapterBridge):
    """Personaly — GET postback"""
    network_keys = ["personaly"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class KiwiwallAdapter(EngineAdapterBridge):
    """Kiwiwall — GET postback"""
    network_keys = ["kiwiwall","kiwi_wall"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"oid","payout":"reward",
                 "transaction_id":"tid","sub_id1":"subid"}

class MonlixAdapter(EngineAdapterBridge):
    """Monlix — GET postback"""
    network_keys = ["monlix"]
    FIELD_MAP = {"lead_id":"userid","offer_id":"offerid","payout":"amount",
                 "transaction_id":"conversionid"}

class NotikAdapter(EngineAdapterBridge):
    """Notik — GET postback"""
    network_keys = ["notik"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount",
                 "transaction_id":"tid"}

class OfferDaddyAdapter(EngineAdapterBridge):
    """OfferDaddy — GET postback"""
    network_keys = ["offerdaddy","offer_daddy"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id"}

class OfferTownAdapter(EngineAdapterBridge):
    """OfferTown — GET postback"""
    network_keys = ["offertown","offer_town"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"rev",
                 "transaction_id":"tid"}

class AdlockMediaAdapter(EngineAdapterBridge):
    """Adlock Media — GET postback"""
    network_keys = ["adlockmedia","adlock_media","adlock"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class OfferwallProAdapter(EngineAdapterBridge):
    """OfferwallPro — GET postback"""
    network_keys = ["offerwallpro","offerwall_pro"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount",
                 "transaction_id":"tid","sub_id1":"subid"}

class WallAdsAdapter(EngineAdapterBridge):
    """WallAds — GET postback"""
    network_keys = ["wallads","wall_ads"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"txn_id"}

class WallPortAdapter(EngineAdapterBridge):
    """WallPort — GET postback"""
    network_keys = ["wallport","wall_port"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount","transaction_id":"tid"}

class WallToroAdapter(EngineAdapterBridge):
    """WallToro — GET postback"""
    network_keys = ["walltoro","wall_toro"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount","transaction_id":"tid"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP B: SURVEY NETWORKS
# ─────────────────────────────────────────────────────────────────────────────

class PollfishAdapter(EngineAdapterBridge):
    """Pollfish — POST JSON postback"""
    network_keys = ["pollfish","poll_fish"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"survey_id","payout":"cpa",
                 "transaction_id":"uuid","country":"geo_code","goal_id":"survey_format"}

class CPXResearchAdapter(EngineAdapterBridge):
    """CPX Research — GET postback"""
    network_keys = ["cpxresearch","cpx_research","cpx"]
    FIELD_MAP = {"lead_id":"ext_user_id","offer_id":"cpx_id","payout":"payout_publisher",
                 "transaction_id":"trans_id","sub_id1":"subid_1","sub_id2":"subid_2"}

class BitlabsAdapter(EngineAdapterBridge):
    """BitLabs — GET postback"""
    network_keys = ["bitlabs","bit_labs"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"survey_id","payout":"reward",
                 "transaction_id":"uid","goal_id":"type"}

class InbrainAdapter(EngineAdapterBridge):
    """InBrain.ai — GET/POST postback"""
    network_keys = ["inbrain","in_brain"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"survey_id","payout":"reward",
                 "transaction_id":"survey_answer_id"}

class TheoremReachAdapter(EngineAdapterBridge):
    """TheoremReach — GET postback"""
    network_keys = ["theoremreach","theorem_reach"]
    FIELD_MAP = {"lead_id":"api_user_id","offer_id":"survey_token","payout":"amount",
                 "transaction_id":"transaction_id"}

class YourSurveysAdapter(EngineAdapterBridge):
    """YourSurveys — GET postback"""
    network_keys = ["yoursurveys","your_surveys"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"study_id","payout":"revenue",
                 "transaction_id":"session_id"}

class SurveySavvyAdapter(EngineAdapterBridge):
    """SurveySavvy — GET postback"""
    network_keys = ["surveysavvy","survey_savvy"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"sid","payout":"amount","transaction_id":"tid"}

class OpinionWorldAdapter(EngineAdapterBridge):
    """OpinionWorld — GET postback"""
    network_keys = ["opinionworld","opinion_world"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount","transaction_id":"tid"}

class TolunaAdapter(EngineAdapterBridge):
    """Toluna — GET postback"""
    network_keys = ["toluna"]
    FIELD_MAP = {"lead_id":"MemberId","offer_id":"QuestionnaireId","payout":"PointAmount",
                 "transaction_id":"WaveId"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP C: GPT / REWARD SITES
# ─────────────────────────────────────────────────────────────────────────────

class SwagbucksAdapter(EngineAdapterBridge):
    """Swagbucks — GET postback"""
    network_keys = ["swagbucks","swag_bucks","sb"]
    FIELD_MAP = {"lead_id":"memberId","offer_id":"offerId","payout":"sb",
                 "transaction_id":"transactionId"}

class PrizeRebelAdapter(EngineAdapterBridge):
    """PrizeRebel — GET postback"""
    network_keys = ["prizerebel","prize_rebel"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"points","transaction_id":"tid"}

class GrabPointsAdapter(EngineAdapterBridge):
    """GrabPoints — GET postback"""
    network_keys = ["grabpoints","grab_points"]
    FIELD_MAP = {"lead_id":"userId","offer_id":"offerId","payout":"points",
                 "transaction_id":"transId"}

class InstaGCAdapter(EngineAdapterBridge):
    """InstaGC — GET postback"""
    network_keys = ["instagc","insta_gc"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"credits","transaction_id":"tid"}

class Points2ShopAdapter(EngineAdapterBridge):
    """Points2Shop — GET postback"""
    network_keys = ["points2shop","points_2_shop"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"points","transaction_id":"tid"}

class RewardRackAdapter(EngineAdapterBridge):
    """RewardRack — GET postback"""
    network_keys = ["rewardrack","reward_rack"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class RewardXPAdapter(EngineAdapterBridge):
    """RewardXP — GET postback"""
    network_keys = ["rewardxp","reward_xp"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"xp","transaction_id":"tid"}

class IdleEmpireAdapter(EngineAdapterBridge):
    """Idle-Empire — GET postback"""
    network_keys = ["idleempire","idle_empire"]
    FIELD_MAP = {"lead_id":"steam_id","offer_id":"offer_id","payout":"points",
                 "transaction_id":"transaction_id"}

class GainGGAdapter(EngineAdapterBridge):
    """Gain.gg — GET postback"""
    network_keys = ["gain","gaingg","gain_gg"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"gems","transaction_id":"tid"}

class GrindabuckAdapter(EngineAdapterBridge):
    """Grindabuck — GET postback"""
    network_keys = ["grindabuck","grinda_buck"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"payout","transaction_id":"tid"}

class TimebucksAdapter(EngineAdapterBridge):
    """Timebucks — GET postback"""
    network_keys = ["timebucks","time_bucks"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"task_id","payout":"payout",
                 "transaction_id":"payment_id"}

class ClixsenseAdapter(EngineAdapterBridge):
    """ClixSense/ySense — GET postback"""
    network_keys = ["clixsense","ysense","y_sense"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"rev","transaction_id":"tid"}

class NeobuxAdapter(EngineAdapterBridge):
    """Neobux — GET postback"""
    network_keys = ["neobux","neo_bux"]
    FIELD_MAP = {"lead_id":"user","offer_id":"offer","payout":"amount","transaction_id":"ref"}

class ProbuxAdapter(EngineAdapterBridge):
    """Probux — GET postback"""
    network_keys = ["probux","pro_bux"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount","transaction_id":"tid"}

class ClixwallAdapter(EngineAdapterBridge):
    """ClixWall — GET postback"""
    network_keys = ["clixwall","clix_wall"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"reward","transaction_id":"tid"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP D: VIDEO / TASK NETWORKS
# ─────────────────────────────────────────────────────────────────────────────

class LootTVAdapter(EngineAdapterBridge):
    """LootTV — GET postback, video completion"""
    network_keys = ["loottv","loot_tv"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"video_id","payout":"payout",
                 "transaction_id":"session_id","goal_id":"event_type"}

class HideoutTVAdapter(EngineAdapterBridge):
    """HideoutTV — GET postback"""
    network_keys = ["hideouttv","hideout_tv","hideout"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"content_id","payout":"reward",
                 "transaction_id":"session_id"}

class EarnHoneyAdapter(EngineAdapterBridge):
    """EarnHoney — GET postback"""
    network_keys = ["earnhoney","earn_honey"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"hc",
                 "transaction_id":"transaction_id"}

class OfferStationAdapter(EngineAdapterBridge):
    """OfferStation — GET postback"""
    network_keys = ["offerstation","offer_station"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"oid","payout":"amount","transaction_id":"tid"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP E: MOBILE AD NETWORKS
# ─────────────────────────────────────────────────────────────────────────────

class AdMobAdapter(EngineAdapterBridge):
    """Google AdMob — server-side conversion postback"""
    network_keys = ["admob","ad_mob","google_admob"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"ad_unit_id","payout":"reward_amount",
                 "transaction_id":"transaction_id","goal_id":"reward_type"}

class UnityAdsAdapter(EngineAdapterBridge):
    """Unity Ads — server-side reward postback"""
    network_keys = ["unity","unity_ads","unityads"]
    FIELD_MAP = {"lead_id":"productId","offer_id":"gameId","payout":"value",
                 "transaction_id":"sid","goal_id":"type"}

class IronSourceAdapter(EngineAdapterBridge):
    """IronSource — server-side reward"""
    network_keys = ["ironsource","iron_source"]
    FIELD_MAP = {"lead_id":"userId","offer_id":"placementId","payout":"rewardAmount",
                 "transaction_id":"uniqueId","goal_id":"rewardName"}

class AppLovinAdapter(EngineAdapterBridge):
    """AppLovin MAX — server-side reward postback"""
    network_keys = ["applovin","app_lovin","max"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"zone_id","payout":"amount",
                 "transaction_id":"idfa","goal_id":"currency"}

class TapjoyAdapter(EngineAdapterBridge):
    """Tapjoy — server-side reward"""
    network_keys = ["tapjoy","tap_joy"]
    FIELD_MAP = {"lead_id":"id","offer_id":"offerid","payout":"price",
                 "transaction_id":"mac_opt","sub_id1":"snid"}

class VungleAdapter(EngineAdapterBridge):
    """Vungle — server-side reward"""
    network_keys = ["vungle"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"placement_ref_id","payout":"incentivized",
                 "transaction_id":"transaction_id"}

class FyberAdapter(EngineAdapterBridge):
    """Fyber (Digital Turbine) — server-side postback"""
    network_keys = ["fyber","digital_turbine","digitalturbine"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"sid","payout":"payout",
                 "transaction_id":"id","goal_id":"ad_format"}

class AdColonyAdapter(EngineAdapterBridge):
    """AdColony — server-side reward"""
    network_keys = ["adcolony","ad_colony"]
    FIELD_MAP = {"lead_id":"custom_id","offer_id":"zone_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class ChartboostAdapter(EngineAdapterBridge):
    """Chartboost — server-side reward"""
    network_keys = ["chartboost","chart_boost"]
    FIELD_MAP = {"lead_id":"userId","offer_id":"location","payout":"rewardAmount",
                 "transaction_id":"transactionId"}

class InMobiAdapter(EngineAdapterBridge):
    """InMobi — server-side conversion"""
    network_keys = ["inmobi","in_mobi"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"aid","payout":"payout","transaction_id":"id"}

class PangleAdapter(EngineAdapterBridge):
    """Pangle (TikTok for Business) — server-side postback"""
    network_keys = ["pangle","tiktok_ads","tiktok_for_business"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"ad_slot_id","payout":"reward_amount",
                 "transaction_id":"trans_id","goal_id":"reward_name"}

class MintegralAdapter(EngineAdapterBridge):
    """Mintegral — server-side postback"""
    network_keys = ["mintegral","mint_egral"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"amount",
                 "transaction_id":"click_id"}

class LeadboltAdapter(EngineAdapterBridge):
    """Leadbolt — server-side reward"""
    network_keys = ["leadbolt","lead_bolt"]
    FIELD_MAP = {"lead_id":"publisher_user_id","offer_id":"placement_id","payout":"reward_amount",
                 "transaction_id":"trans_id"}

class StartAppAdapter(EngineAdapterBridge):
    """StartApp — server-side reward"""
    network_keys = ["startapp","start_app"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"appId","payout":"reward","transaction_id":"tid"}

class YouAppiAdapter(EngineAdapterBridge):
    """YouAppi — server-side postback"""
    network_keys = ["youappi","you_appi"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"app_id","payout":"payout",
                 "transaction_id":"transaction_id"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP F: TRACKING PLATFORMS (HasOffers/TUNE, Cake, Everflow, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class HasOffersAdapter(EngineAdapterBridge):
    """HasOffers / TUNE — standard postback"""
    network_keys = ["hasoffers","has_offers","tune","tune_platform"]
    FIELD_MAP = {"lead_id":"aff_sub","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id","sub_id1":"aff_sub2",
                 "sub_id2":"aff_sub3","sub_id3":"aff_sub4","goal_id":"goal_id"}

class CakeAdapter(EngineAdapterBridge):
    """Cake Platform — standard postback"""
    network_keys = ["cake","cake_platform"]
    FIELD_MAP = {"lead_id":"s1","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id","sub_id1":"s2","sub_id2":"s3",
                 "goal_id":"goal_name","country":"country_code"}

class EverflowAdapter(EngineAdapterBridge):
    """Everflow — standard postback"""
    network_keys = ["everflow","ever_flow"]
    FIELD_MAP = {"lead_id":"sub1","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"tid","sub_id1":"sub2","sub_id2":"sub3",
                 "sub_id3":"sub4","goal_id":"goal_name","country":"country"}
    STATUS_MAP = {"approved":"approved","rejected":"reversed","pending":"pending"}

class LinkTrustAdapter(EngineAdapterBridge):
    """LinkTrust — standard postback"""
    network_keys = ["linktrust","link_trust"]
    FIELD_MAP = {"lead_id":"clickId","offer_id":"campaignId","payout":"payout",
                 "transaction_id":"conversionId","sub_id1":"sub1","goal_id":"goalName"}

class ImpactAdapter(EngineAdapterBridge):
    """Impact.com — server postback"""
    network_keys = ["impact","impact_com","impact_radius"]
    FIELD_MAP = {"lead_id":"ClickId","offer_id":"CampaignId","payout":"Payout",
                 "transaction_id":"OrderId","goal_id":"ActionTrackerId"}

class FacebookAdsAdapter(EngineAdapterBridge):
    """Facebook Ads — Conversions API"""
    network_keys = ["facebook","facebook_ads","fb_ads","meta"]
    FIELD_MAP = {"lead_id":"event_id","offer_id":"campaign_id","payout":"value",
                 "transaction_id":"purchase_id","country":"country","goal_id":"event_name"}

class GoogleAdsAdapter(EngineAdapterBridge):
    """Google Ads — conversion postback"""
    network_keys = ["google","google_ads","googleads"]
    FIELD_MAP = {"lead_id":"gclid","offer_id":"campaign_id","payout":"value",
                 "transaction_id":"order_id","goal_id":"conversion_action"}

class SnapchatAdapter(EngineAdapterBridge):
    """Snapchat Ads — Conversions API"""
    network_keys = ["snapchat","snap","snapchat_ads"]
    FIELD_MAP = {"lead_id":"client_dedup_id","offer_id":"campaign_id","payout":"price",
                 "transaction_id":"order_id","goal_id":"event_type"}

class TikTokAdapter(EngineAdapterBridge):
    """TikTok Ads — Events API"""
    network_keys = ["tiktok","tiktok_ads","tt_ads"]
    FIELD_MAP = {"lead_id":"event_id","offer_id":"campaign_id","payout":"value",
                 "transaction_id":"order_id","goal_id":"event","country":"ip"}

class TwitterAdapter(EngineAdapterBridge):
    """Twitter/X Ads — Conversions API"""
    network_keys = ["twitter","twitter_ads","x_ads"]
    FIELD_MAP = {"lead_id":"event_id","offer_id":"line_item_id","payout":"value",
                 "transaction_id":"order_id","goal_id":"conversion_id"}

class AppNextAdapter(EngineAdapterBridge):
    """AppNext — server-side postback"""
    network_keys = ["appnext","app_next"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"aid","payout":"payout",
                 "transaction_id":"tid","goal_id":"type"}

class GlispaAdapter(EngineAdapterBridge):
    """Glispa (Avocarrot) — server postback"""
    network_keys = ["glispa","avocarrot"]
    FIELD_MAP = {"lead_id":"sub_id","offer_id":"campaign_id","payout":"payout",
                 "transaction_id":"transaction_id"}

class OguryAdapter(EngineAdapterBridge):
    """Ogury — server postback"""
    network_keys = ["ogury"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"placement_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class MediaBrixAdapter(EngineAdapterBridge):
    """MediaBrix — server postback"""
    network_keys = ["mediabrix","media_brix"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"aid","payout":"reward","transaction_id":"tid"}

class NativeXAdapter(EngineAdapterBridge):
    """NativeX — server postback"""
    network_keys = ["nativex","native_x"]
    FIELD_MAP = {"lead_id":"uid","offer_id":"placementid","payout":"rewardamount",
                 "transaction_id":"tid","goal_id":"rewardname"}

class KidozAdapter(EngineAdapterBridge):
    """Kidoz — server postback"""
    network_keys = ["kidoz","kid_oz"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"app_id","payout":"amount",
                 "transaction_id":"transaction_id"}

class OfferWallNetworkAdapter(EngineAdapterBridge):
    """Generic OfferWall — standard GET postback (revenuewall, etc.)"""
    network_keys = ["offerwall","revenuewall","revenue_wall","generic_offerwall"]
    FIELD_MAP = {"lead_id":"user_id","offer_id":"offer_id","payout":"payout",
                 "transaction_id":"transaction_id","sub_id1":"sub_id1"}

class SupersonicAdapter(EngineAdapterBridge):
    """Supersonic (IronSource) — server postback"""
    network_keys = ["supersonic"]
    FIELD_MAP = {"lead_id":"userId","offer_id":"placementId","payout":"rewardAmount",
                 "transaction_id":"uniqueId","goal_id":"rewardName"}


# ─────────────────────────────────────────────────────────────────────────────
# GROUP G: CUSTOM SLOTS (custom1–custom10)
# ─────────────────────────────────────────────────────────────────────────────

class CustomSlotAdapter(EngineAdapterBridge):
    """
    Custom network slots — fully configurable via NetworkPostbackConfig.field_mapping.
    Admin sets the field_mapping in the config; adapter applies it.
    """
    network_keys = [f"custom{i}" for i in range(1, 11)]
    FIELD_MAP = {}  # All mapping comes from NetworkPostbackConfig.field_mapping


# ─────────────────────────────────────────────────────────────────────────────
# COMPLETE ADAPTER LIST (used by registry)
# ─────────────────────────────────────────────────────────────────────────────

ALL_NETWORK_ADAPTERS = [
    # Group A — Offerwalls
    CPALeadNetworkAdapter, AdGateMediaAdapter, AdScendMediaAdapter, OfferToroAdapter,
    AdGemAdapter, AyetStudiosAdapter, LootablyAdapter, RevenueUniverseAdapter,
    AdWorkMediaAdapter, WannadsAdapter, PersonalyAdapter, KiwiwallAdapter,
    MonlixAdapter, NotikAdapter, OfferDaddyAdapter, OfferTownAdapter,
    AdlockMediaAdapter, OfferwallProAdapter, WallAdsAdapter, WallPortAdapter, WallToroAdapter,
    # Group B — Surveys
    PollfishAdapter, CPXResearchAdapter, BitlabsAdapter, InbrainAdapter,
    TheoremReachAdapter, YourSurveysAdapter, SurveySavvyAdapter,
    OpinionWorldAdapter, TolunaAdapter,
    # Group C — GPT/Reward
    SwagbucksAdapter, PrizeRebelAdapter, GrabPointsAdapter, InstaGCAdapter,
    Points2ShopAdapter, RewardRackAdapter, RewardXPAdapter, IdleEmpireAdapter,
    GainGGAdapter, GrindabuckAdapter, TimebucksAdapter, ClixsenseAdapter,
    NeobuxAdapter, ProbuxAdapter, ClixwallAdapter,
    # Group D — Video/Task
    LootTVAdapter, HideoutTVAdapter, EarnHoneyAdapter, OfferStationAdapter,
    # Group E — Mobile
    AdMobAdapter, UnityAdsAdapter, IronSourceAdapter, AppLovinAdapter,
    TapjoyAdapter, VungleAdapter, FyberAdapter, AdColonyAdapter,
    ChartboostAdapter, InMobiAdapter, PangleAdapter, MintegralAdapter,
    LeadboltAdapter, StartAppAdapter, YouAppiAdapter,
    # Group F — Platforms
    HasOffersAdapter, CakeAdapter, EverflowAdapter, LinkTrustAdapter,
    ImpactAdapter, FacebookAdsAdapter, GoogleAdsAdapter, SnapchatAdapter,
    TikTokAdapter, TwitterAdapter, AppNextAdapter, GlispaAdapter,
    OguryAdapter, MediaBrixAdapter, NativeXAdapter, KidozAdapter,
    OfferWallNetworkAdapter, SupersonicAdapter,
    # Group G — Custom
    CustomSlotAdapter,
]
