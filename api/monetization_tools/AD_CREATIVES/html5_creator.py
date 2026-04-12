"""AD_CREATIVES/html5_creator.py — HTML5 rich media ad creator."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class HTML5AdConfig:
    width: int = 320
    height: int = 480
    title: str = ""
    cta_text: str = "Play Now"
    cta_url: str = ""
    bg_color: str = "#1a1a2e"
    text_color: str = "#ffffff"
    font_family: str = "Arial, sans-serif"
    animation: str = "fade"
    duration_ms: int = 5000
    scripts: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)
    mraid_enabled: bool = True


class HTML5AdCreator:
    """Generates HTML5 ad creative markup."""

    @classmethod
    def build(cls, config: HTML5AdConfig) -> str:
        mraid = '''<script src="mraid.js"></script>''' if config.mraid_enabled else ""
        extra_scripts = "\n".join(f'''<script src="{s}"></script>''' for s in config.scripts)
        extra_styles  = "\n".join(f'''<link rel="stylesheet" href="{s}">''' for s in config.styles)
        return f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{mraid}
{extra_styles}
<style>
  body{{margin:0;width:{config.width}px;height:{config.height}px;
       background:{config.bg_color};color:{config.text_color};
       font-family:{config.font_family};display:flex;
       flex-direction:column;align-items:center;justify-content:center;}}
  h1{{font-size:24px;text-align:center;padding:0 16px;}}
  .cta{{background:#FF6B35;color:#fff;border:none;padding:14px 28px;
        font-size:18px;border-radius:8px;cursor:pointer;margin-top:20px;}}
</style>
</head>
<body>
<h1>{config.title}</h1>
<button class="cta" onclick="window.open('{config.cta_url}')">{config.cta_text}</button>
{extra_scripts}
</body></html>"""

    @classmethod
    def validate(cls, config: HTML5AdConfig) -> list:
        errors = []
        if not config.title:
            errors.append("title required")
        if not config.cta_url:
            errors.append("cta_url required")
        if config.width <= 0 or config.height <= 0:
            errors.append("invalid dimensions")
        return errors
