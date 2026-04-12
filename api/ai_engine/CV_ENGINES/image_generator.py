"""
api/ai_engine/CV_ENGINES/image_generator.py
============================================
Image Generator — AI image generation।
Ad creative, banner, thumbnail generation।
DALL-E 3, Stable Diffusion, Midjourney API।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class ImageGenerator:
    """AI-powered image generation engine।"""

    STYLE_PRESETS = {
        "ad_banner":     "professional advertisement banner, clean design, marketing",
        "thumbnail":     "eye-catching thumbnail, vibrant colors, mobile-friendly",
        "product":       "product photography style, white background, professional",
        "social_media":  "social media post, engaging, modern design",
        "logo":          "minimal logo design, vector style, clean",
    }

    def __init__(self, provider: str = "openai"):
        self.provider = provider

    def generate(self, prompt: str, style: str = None,
                 size: str = "1024x1024",
                 quality: str = "standard") -> dict:
        """Image generate করো।"""
        full_prompt = self._build_prompt(prompt, style)

        if self.provider == "openai":
            return self._openai_generate(full_prompt, size, quality)
        elif self.provider == "stability":
            return self._stability_generate(full_prompt, size)
        return self._openai_generate(full_prompt, size, quality)

    def _build_prompt(self, prompt: str, style: Optional[str]) -> str:
        if style and style in self.STYLE_PRESETS:
            return f"{prompt}, {self.STYLE_PRESETS[style]}"
        return prompt

    def _openai_generate(self, prompt: str, size: str, quality: str) -> dict:
        """DALL-E 3 image generation।"""
        try:
            from ..INTEGRATIONS.openai_integration import OpenAIIntegration
            client = OpenAIIntegration()
            result = client.generate_image(
                prompt=prompt,
                size=size,
                quality=quality,
                model="dall-e-3",
            )
            return {
                "url":      result.get("url", ""),
                "provider": "openai_dalle3",
                "prompt":   prompt,
                "size":     size,
                "success":  bool(result.get("url")),
            }
        except Exception as e:
            logger.error(f"DALL-E generation error: {e}")
            return {"success": False, "error": str(e)}

    def _stability_generate(self, prompt: str, size: str) -> dict:
        """Stability AI (Stable Diffusion) generation।"""
        try:
            import requests
            width, height = (int(d) for d in size.split("x"))
            resp = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={"Accept": "application/json", "Authorization": f"Bearer {self._get_api_key()}"},
                json={"text_prompts": [{"text": prompt}], "cfg_scale": 7,
                      "width": width, "height": height, "steps": 30, "samples": 1},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            import base64
            img_b64 = data["artifacts"][0]["base64"]
            return {"base64": img_b64, "provider": "stability_ai", "success": True}
        except Exception as e:
            logger.error(f"Stability AI error: {e}")
            return {"success": False, "error": str(e)}

    def _get_api_key(self) -> str:
        from django.conf import settings
        return getattr(settings, "STABILITY_AI_API_KEY", "")

    def generate_ad_creative(self, product_name: str, tagline: str,
                              style: str = "ad_banner") -> dict:
        prompt = f"Professional advertisement for {product_name}. Tagline: {tagline}. High quality marketing image."
        return self.generate(prompt, style=style)

    def generate_batch(self, prompts: List[str], style: str = None) -> List[Dict]:
        return [self.generate(p, style=style) for p in prompts]

    def edit_image(self, image_path: str, edit_prompt: str) -> dict:
        """Existing image edit করো।"""
        try:
            from ..INTEGRATIONS.openai_integration import OpenAIIntegration
            client = OpenAIIntegration()
            result = client.edit_image(image_path=image_path, prompt=edit_prompt)
            return {"url": result.get("url", ""), "success": bool(result.get("url"))}
        except Exception as e:
            return {"success": False, "error": str(e)}
