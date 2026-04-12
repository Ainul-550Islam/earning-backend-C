"""
AD_FORMATS/rich_media_ad.py
============================
Rich Media ad format handler.
Supports expandable banners, floating ads, push-down ads,
and interactive overlays — all HTML5-based.

Rich media ads have significantly higher eCPM than standard banners
due to higher engagement and viewability rates.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


# ── Configuration Dataclass ───────────────────────────────────────────────────

@dataclass
class RichMediaAdConfig:
    """Configuration for a rich media ad unit."""

    # Dimensions
    collapsed_width:   int  = 320
    collapsed_height:  int  = 50
    expanded_width:    int  = 320
    expanded_height:   int  = 480
    max_z_index:       int  = 9999

    # Behaviour
    expand_type:       str  = "overlay"        # overlay | push_down | floating | sticky
    expand_trigger:    str  = "user_initiated" # user_initiated | auto (auto after delay)
    expand_delay_ms:   int  = 0                # ms delay for auto-expand (0 = manual)
    close_button_delay_ms: int = 3000          # ms before close button appears
    can_close_anytime: bool = False            # allow immediate close

    # Animation
    animation_in:      str  = "slide_up"       # slide_up | fade | zoom | none
    animation_out:     str  = "slide_down"
    animation_duration_ms: int = 300

    # Interaction
    is_expandable:     bool = True
    is_floating:       bool = False
    float_position:    str  = "bottom_right"   # bottom_right | bottom_left | top_right | top_left
    is_sticky:         bool = False
    sticky_position:   str  = "bottom"         # top | bottom

    # Content
    mraid_version:     str  = "2.0"
    html_asset_url:    str  = ""
    fallback_image_url: str = ""
    click_url:         str  = ""
    tracking_pixels:   List[str] = field(default_factory=list)
    impression_url:    str  = ""

    # Display limits
    auto_close_after_sec: int = 0              # 0 = never auto-close
    frequency_cap:     int  = 1               # per session
    min_dwell_sec:     float = 1.0            # minimum visible before counting impression


# ── eCPM Benchmarks ───────────────────────────────────────────────────────────

RICH_MEDIA_ECPM_TABLE = {
    # format_type       US      GB      BD      IN      global
    "expandable":    (6.50,  5.00,  0.50,  0.60,  2.00),
    "floating":      (5.00,  4.00,  0.40,  0.50,  1.80),
    "push_down":     (4.00,  3.50,  0.35,  0.45,  1.50),
    "sticky":        (3.00,  2.50,  0.30,  0.35,  1.20),
    "overlay":       (7.00,  5.50,  0.55,  0.65,  2.50),
    "interstitial_rich": (8.00, 6.50, 0.60, 0.70, 3.00),
}

COUNTRY_COLUMN = {"US": 0, "GB": 1, "BD": 2, "IN": 3}


class RichMediaAdHandler:
    """
    Handles rich media ad formats — expandable, floating, push-down, sticky.
    These formats achieve 2x–5x higher eCPM vs standard banners.
    """

    # Supported expand types and their MRAID equivalents
    EXPAND_TYPES = {
        "overlay":   "expand",
        "push_down": "resize",
        "floating":  "expand",
        "sticky":    "resize",
    }

    # Minimum collapsed sizes (IAB standard)
    MIN_COLLAPSED_SIZES = {
        "320x50":  (320, 50),
        "320x100": (320, 100),
        "728x90":  (728, 90),
        "300x50":  (300, 50),
    }

    @classmethod
    def get_config(cls,
                   expand_type:   str = "overlay",
                   collapsed_w:   int = 320,
                   collapsed_h:   int = 50,
                   expanded_w:    int = 320,
                   expanded_h:    int = 480,
                   html_url:      str = "",
                   click_url:     str = "") -> RichMediaAdConfig:
        """Build a RichMediaAdConfig with validated dimensions."""
        return RichMediaAdConfig(
            collapsed_width=collapsed_w,
            collapsed_height=collapsed_h,
            expanded_width=expanded_w,
            expanded_height=expanded_h,
            expand_type=expand_type,
            html_asset_url=html_url,
            click_url=click_url,
        )

    @classmethod
    def get_ecpm_estimate(cls,
                          expand_type: str = "expandable",
                          country:     str = "US") -> Decimal:
        """
        Estimate eCPM for a rich media format + country combination.
        Returns USD eCPM as Decimal.
        """
        row    = RICH_MEDIA_ECPM_TABLE.get(expand_type,
                 RICH_MEDIA_ECPM_TABLE["expandable"])
        col    = COUNTRY_COLUMN.get(country.upper() if country else "US", 4)
        ecpm   = Decimal(str(row[col]))
        return ecpm.quantize(Decimal("0.0001"))

    @classmethod
    def build_mraid_tag(cls, config: RichMediaAdConfig) -> str:
        """
        Generate the MRAID HTML wrapper for a rich media ad.
        This is injected into the ad container on the device.
        """
        mraid_api    = cls.EXPAND_TYPES.get(config.expand_type, "expand")
        close_delay  = config.close_button_delay_ms
        anim_in      = config.animation_in
        anim_out     = config.animation_out
        anim_dur     = config.animation_duration_ms
        tracking_js  = "\n".join(
            f'new Image().src = "{px}";'
            for px in config.tracking_pixels
        )
        imp_js = f'new Image().src = "{config.impression_url}";' if config.impression_url else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="mraid.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      width:    {config.collapsed_width}px;
      height:   {config.collapsed_height}px;
      overflow: hidden;
      position: relative;
      background: transparent;
    }}
    #ad-collapsed {{
      width: 100%; height: 100%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    #ad-expanded {{
      width:    {config.expanded_width}px;
      height:   {config.expanded_height}px;
      position: fixed;
      top: 0; left: 0;
      z-index:  {config.max_z_index};
      display: none;
      background: #fff;
    }}
    #close-btn {{
      position: absolute;
      top: 8px; right: 8px;
      width: 30px; height: 30px;
      background: rgba(0,0,0,0.6);
      color: #fff;
      border: none;
      border-radius: 50%;
      font-size: 16px;
      cursor: pointer;
      display: none;
      z-index: {config.max_z_index + 1};
      line-height: 30px;
      text-align: center;
    }}
    .fade-in  {{ animation: fadeIn  {anim_dur}ms ease forwards; }}
    .fade-out {{ animation: fadeOut {anim_dur}ms ease forwards; }}
    @keyframes fadeIn  {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes fadeOut {{ from {{ opacity: 1; }} to {{ opacity: 0; }} }}
  </style>
</head>
<body>
  <div id="ad-collapsed" onclick="expandAd()">
    <img src="{config.fallback_image_url}"
         width="{config.collapsed_width}"
         height="{config.collapsed_height}"
         alt="Advertisement"
         onerror="this.style.display='none'">
  </div>

  <div id="ad-expanded">
    <button id="close-btn" onclick="collapseAd()">&#x2715;</button>
    <iframe id="rich-frame"
            src="{config.html_asset_url}"
            width="{config.expanded_width}"
            height="{config.expanded_height}"
            frameborder="0"
            scrolling="no"
            allow="autoplay">
    </iframe>
  </div>

  <script>
    var expanded        = false;
    var closeTimer      = null;
    var closeDelay      = {close_delay};
    var impressionFired = false;

    function fireImpression() {{
      if (impressionFired) return;
      impressionFired = true;
      {imp_js}
      {tracking_js}
    }}

    function expandAd() {{
      if (typeof mraid !== 'undefined') {{
        mraid.{mraid_api}({{
          width:  {config.expanded_width},
          height: {config.expanded_height}
        }});
      }}
      var ex = document.getElementById('ad-expanded');
      var cl = document.getElementById('ad-collapsed');
      cl.style.display = 'none';
      ex.style.display = 'block';
      ex.className = '{anim_in == "fade" and "fade-in" or ""}';
      expanded = true;
      fireImpression();
      if (closeDelay > 0) {{
        closeTimer = setTimeout(function() {{
          document.getElementById('close-btn').style.display = 'block';
        }}, closeDelay);
      }} else {{
        document.getElementById('close-btn').style.display = 'block';
      }}
    }}

    function collapseAd() {{
      if (typeof mraid !== 'undefined') {{
        mraid.close();
      }}
      var ex = document.getElementById('ad-expanded');
      var cl = document.getElementById('ad-collapsed');
      ex.style.display = 'none';
      cl.style.display = 'flex';
      expanded = false;
      if (closeTimer) clearTimeout(closeTimer);
    }}

    // MRAID ready handler
    if (typeof mraid !== 'undefined') {{
      if (mraid.getState() === 'loading') {{
        mraid.addEventListener('ready', function() {{
          mraid.setExpandProperties({{
            width:  {config.expanded_width},
            height: {config.expanded_height},
            useCustomClose: true,
            isModal: true
          }});
        }});
      }}
    }}

    // Auto-close after configured time
    {'setTimeout(function() { collapseAd(); }, ' + str(config.auto_close_after_sec * 1000) + ');' if config.auto_close_after_sec > 0 else '// no auto-close'}

    // Auto-expand if configured
    {'setTimeout(function() { expandAd(); }, ' + str(config.expand_delay_ms) + ');' if config.expand_delay_ms > 0 else '// manual expand only'}
  </script>
</body>
</html>"""

    @classmethod
    def validate(cls, config: RichMediaAdConfig) -> list:
        """
        Validate rich media config.
        Returns list of error strings; empty = valid.
        """
        errors = []

        if config.expanded_width < config.collapsed_width:
            errors.append("expanded_width must be >= collapsed_width")
        if config.expanded_height < config.collapsed_height:
            errors.append("expanded_height must be >= collapsed_height")
        if not config.html_asset_url:
            errors.append("html_asset_url is required")
        if not config.html_asset_url.startswith(("http://", "https://")):
            errors.append("html_asset_url must be an absolute HTTP/HTTPS URL")
        if config.expand_type not in cls.EXPAND_TYPES:
            errors.append(
                f"expand_type must be one of: {list(cls.EXPAND_TYPES.keys())}"
            )
        if config.close_button_delay_ms < 0:
            errors.append("close_button_delay_ms cannot be negative")
        if config.animation_duration_ms < 0:
            errors.append("animation_duration_ms cannot be negative")

        return errors

    @classmethod
    def build_floating_config(cls,
                               html_url:     str,
                               position:     str = "bottom_right",
                               size:         int = 100) -> RichMediaAdConfig:
        """Shortcut to build a floating (corner) rich media ad."""
        return RichMediaAdConfig(
            collapsed_width=size,
            collapsed_height=size,
            expanded_width=size * 3,
            expanded_height=size * 4,
            expand_type="floating",
            is_floating=True,
            float_position=position,
            html_asset_url=html_url,
            animation_in="fade",
            animation_out="fade",
        )

    @classmethod
    def build_sticky_config(cls,
                             html_url:  str,
                             position:  str = "bottom",
                             height:    int = 60) -> RichMediaAdConfig:
        """Shortcut to build a sticky (full-width) rich media banner."""
        return RichMediaAdConfig(
            collapsed_width=0,      # full width (CSS)
            collapsed_height=height,
            expanded_width=0,
            expanded_height=height * 5,
            expand_type="sticky",
            is_sticky=True,
            sticky_position=position,
            is_expandable=True,
            html_asset_url=html_url,
            animation_in="slide_up",
            animation_out="slide_down",
        )

    @classmethod
    def build_push_down_config(cls,
                                html_url:       str,
                                collapsed_h:    int = 90,
                                expanded_h:     int = 400) -> RichMediaAdConfig:
        """Shortcut for push-down (banner that pushes page content down)."""
        return RichMediaAdConfig(
            collapsed_width=728,
            collapsed_height=collapsed_h,
            expanded_width=728,
            expanded_height=expanded_h,
            expand_type="push_down",
            is_expandable=True,
            html_asset_url=html_url,
            animation_in="slide_up",
            animation_out="slide_down",
            close_button_delay_ms=2000,
        )

    @classmethod
    def get_viewability_requirements(cls, expand_type: str) -> dict:
        """
        MRC/IAB viewability requirements per rich media type.
        Returns dict with min_visible_pct and min_duration_sec.
        """
        requirements = {
            "overlay":          {"min_visible_pct": 50.0, "min_duration_sec": 1.0},
            "expandable":       {"min_visible_pct": 50.0, "min_duration_sec": 1.0},
            "floating":         {"min_visible_pct": 50.0, "min_duration_sec": 1.0},
            "push_down":        {"min_visible_pct": 30.0, "min_duration_sec": 0.5},
            "sticky":           {"min_visible_pct": 50.0, "min_duration_sec": 1.0},
            "interstitial_rich":{"min_visible_pct": 100.0,"min_duration_sec": 2.0},
        }
        return requirements.get(expand_type, {"min_visible_pct": 50.0, "min_duration_sec": 1.0})

    @classmethod
    def format_size_label(cls, config: RichMediaAdConfig) -> str:
        """Return human-readable size label."""
        return (
            f"{config.collapsed_width}x{config.collapsed_height} "
            f"→ {config.expanded_width}x{config.expanded_height} "
            f"[{config.expand_type}]"
        )
