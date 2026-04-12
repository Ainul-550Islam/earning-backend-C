"""AD_CREATIVES/banner_generator.py — Banner creative builder."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class BannerCreativeSpec:
    width: int
    height: int
    background_color: str = "#FFFFFF"
    text: str = ""
    text_color: str = "#000000"
    font_size: int = 14
    image_url: str = ""
    cta_text: str = "Click Here"
    cta_color: str = "#007BFF"
    border_color: str = "#CCCCCC"
    border_width: int = 1


class BannerGenerator:
    """Generates banner creative specifications and HTML snippets."""

    @classmethod
    def build_spec(cls, width: int, height: int, text: str,
                    image_url: str = "", cta: str = "Learn More") -> BannerCreativeSpec:
        return BannerCreativeSpec(width=width, height=height, text=text,
                                   image_url=image_url, cta_text=cta)

    @classmethod
    def to_html(cls, spec: BannerCreativeSpec) -> str:
        img_tag = f'''<img src="{spec.image_url}" style="max-width:100%;"/>''' if spec.image_url else ""
        return (
            f'''<div style="width:{spec.width}px;height:{spec.height}px;'''
            f'''background:{spec.background_color};border:{spec.border_width}px solid {spec.border_color};'''
            f'''display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;">'''
            f'''{img_tag}'''
            f'''<p style="color:{spec.text_color};font-size:{spec.font_size}px;margin:4px 0;">{spec.text}</p>'''
            f'''<button style="background:{spec.cta_color};color:#fff;border:none;padding:6px 12px;cursor:pointer;">'''
            f'''{spec.cta_text}</button></div>'''
        )

    @classmethod
    def validate(cls, spec: BannerCreativeSpec) -> list:
        errors = []
        if spec.width <= 0 or spec.height <= 0:
            errors.append("Width and height must be positive.")
        if not spec.text and not spec.image_url:
            errors.append("Either text or image_url required.")
        return errors
