# api/publisher_tools/ad_unit_management/rewarded_video_unit.py
"""Rewarded Video Ad Unit — Reward configuration."""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class RewardedVideoConfig(TimeStampedModel):
    """Rewarded video ad settings and reward config."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_rewardedconf_tenant", db_index=True)
    ad_unit              = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="rewarded_config")
    reward_name          = models.CharField(max_length=100, default="Coins")
    reward_amount        = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    reward_type          = models.CharField(max_length=20, choices=[("coins","Coins"),("gems","Gems"),("lives","Lives"),("power_up","Power-up"),("custom","Custom")], default="coins")
    min_video_watch_pct  = models.IntegerField(default=100, validators=[MinValueValidator(50)], help_text="% of video user must watch")
    reward_callback_url  = models.URLField(blank=True)
    server_side_verify   = models.BooleanField(default=True)
    ssv_secret_key       = models.CharField(max_length=100, blank=True)
    daily_reward_limit   = models.IntegerField(default=5, validators=[MinValueValidator(1)])
    prompt_dialog_title  = models.CharField(max_length=200, default="Watch video for reward?")
    prompt_dialog_message= models.CharField(max_length=500, default="Watch a short video to earn coins!")
    completion_dialog    = models.CharField(max_length=200, default="Reward earned!")
    no_ad_dialog         = models.CharField(max_length=200, default="No ads available. Try again later.")
    max_video_length_sec = models.IntegerField(default=30)

    class Meta:
        db_table = "publisher_tools_rewarded_video_configs"
        verbose_name = _("Rewarded Video Config")

    def __str__(self):
        return f"Rewarded: {self.ad_unit.unit_id} — {self.reward_amount} {self.reward_name}"
