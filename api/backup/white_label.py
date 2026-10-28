"""
White-Label / OEM Branding Support
Allows resellers and enterprise customers to brand the backup system
with their own logo, colours, domain, and email templates.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BrandTheme:
    primary_color: str = "#1A73E8"
    secondary_color: str = "#34A853"
    accent_color: str = "#FBBC04"
    background_color: str = "#FFFFFF"
    text_color: str = "#202124"
    font_family: str = "Inter, sans-serif"
    border_radius: str = "8px"

    def to_css_vars(self) -> str:
        return f"""
:root {{
  --brand-primary: {self.primary_color};
  --brand-secondary: {self.secondary_color};
  --brand-accent: {self.accent_color};
  --brand-bg: {self.background_color};
  --brand-text: {self.text_color};
  --brand-font: {self.font_family};
  --brand-radius: {self.border_radius};
}}""".strip()


@dataclass
class WhiteLabelConfig:
    tenant_id: str
    brand_name: str                        # shown in UI, emails, reports
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    custom_domain: Optional[str] = None    # e.g. backup.customer.com
    support_email: str = "support@example.com"
    support_url: Optional[str] = None
    privacy_url: Optional[str] = None
    terms_url: Optional[str] = None
    theme: BrandTheme = field(default_factory=BrandTheme)
    email_from_name: str = ""
    email_from_address: str = ""
    hide_powered_by: bool = False          # OEM: hide "Powered by BackupSystem"
    custom_css: str = ""
    custom_footer_html: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.email_from_name:
            self.email_from_name = self.brand_name
        if not self.email_from_address:
            self.email_from_address = f"noreply@{self.custom_domain or 'example.com'}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "logo_url": self.logo_url,
            "custom_domain": self.custom_domain,
            "support_email": self.support_email,
            "hide_powered_by": self.hide_powered_by,
            "enabled": self.enabled,
            "theme": {
                "primary_color": self.theme.primary_color,
                "font_family": self.theme.font_family,
            },
        }

    def validate(self):
        errors = {}
        if not self.brand_name.strip():
            errors["brand_name"] = "Brand name is required."
        if self.custom_domain:
            pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$'
            if not re.match(pattern, self.custom_domain):
                errors["custom_domain"] = f"Invalid domain: {self.custom_domain}"
        if errors:
            raise ValueError(errors)
        return True


class EmailTemplateRenderer:
    """Renders branded email templates using the tenant's white-label config"""

    BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body {{ font-family: {font_family}; color: {text_color}; background: {bg_color}; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: {radius}; padding: 32px; }}
  .header {{ border-bottom: 3px solid {primary_color}; padding-bottom: 16px; margin-bottom: 24px; }}
  .logo {{ max-height: 48px; }}
  .brand-name {{ font-size: 22px; font-weight: 600; color: {primary_color}; }}
  .footer {{ border-top: 1px solid #e0e0e0; margin-top: 24px; padding-top: 16px;
             font-size: 12px; color: #888; }}
  .btn {{ display: inline-block; background: {primary_color}; color: #fff; padding: 12px 24px;
          border-radius: {radius}; text-decoration: none; font-weight: 500; }}
  {custom_css}
</style></head>
<body><div class="container">
  <div class="header">
    {logo_html}
  </div>
  {body}
  <div class="footer">
    {footer}
    {powered_by}
  </div>
</div></body></html>"""

    def render(self, config: WhiteLabelConfig, body_html: str,
               subject: str = "") -> Dict[str, str]:
        logo_html = (
            f'<img src="{config.logo_url}" alt="{config.brand_name}" class="logo">'
            if config.logo_url
            else f'<span class="brand-name">{config.brand_name}</span>'
        )
        powered_by = (
            "" if config.hide_powered_by
            else '<br>Powered by BackupSystem'
        )
        footer = config.custom_footer_html or (
            f'<a href="{config.support_url}">{config.support_email}</a>'
            if config.support_url else config.support_email
        )
        html = self.BASE_TEMPLATE.format(
            font_family=config.theme.font_family,
            text_color=config.theme.text_color,
            bg_color=config.theme.background_color,
            radius=config.theme.border_radius,
            primary_color=config.theme.primary_color,
            custom_css=config.custom_css,
            logo_html=logo_html,
            body=body_html,
            footer=footer,
            powered_by=powered_by,
        )
        return {
            "subject": f"{config.brand_name} — {subject}" if subject else config.brand_name,
            "from_name": config.email_from_name,
            "from_address": config.email_from_address,
            "html": html,
        }

    def backup_completed_email(self, config: WhiteLabelConfig,
                                backup_name: str, size_human: str) -> Dict[str, str]:
        body = f"""
<h2>Backup completed ✓</h2>
<p>Your backup <strong>{backup_name}</strong> has completed successfully.</p>
<table style="width:100%;margin:16px 0;">
  <tr><td style="color:#888">Size</td><td style="text-align:right">{size_human}</td></tr>
  <tr><td style="color:#888">Time</td><td style="text-align:right">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
</table>
<p><a href="{config.support_url or '#'}" class="btn">View backup details</a></p>"""
        return self.render(config, body, "Backup completed")

    def backup_failed_email(self, config: WhiteLabelConfig,
                             backup_name: str, error: str) -> Dict[str, str]:
        body = f"""
<h2 style="color:#d93025">Backup failed ✗</h2>
<p>Your backup <strong>{backup_name}</strong> failed.</p>
<pre style="background:#f8f8f8;padding:12px;border-radius:4px;font-size:12px">{error[:500]}</pre>
<p>Please contact <a href="mailto:{config.support_email}">{config.support_email}</a> if this persists.</p>"""
        return self.render(config, body, "Backup failed — action required")


class WhiteLabelRegistry:
    """Registry of white-label configs keyed by tenant_id"""

    def __init__(self):
        self._configs: Dict[str, WhiteLabelConfig] = {}
        self._renderer = EmailTemplateRenderer()

    def register(self, config: WhiteLabelConfig) -> None:
        config.validate()
        self._configs[config.tenant_id] = config
        logger.info("White-label config registered: tenant=%s brand=%s domain=%s",
                    config.tenant_id, config.brand_name, config.custom_domain)

    def get(self, tenant_id: str) -> Optional[WhiteLabelConfig]:
        return self._configs.get(tenant_id)

    def get_by_domain(self, domain: str) -> Optional[WhiteLabelConfig]:
        return next((c for c in self._configs.values()
                     if c.custom_domain == domain and c.enabled), None)

    def update(self, tenant_id: str, updates: Dict[str, Any]) -> bool:
        config = self._configs.get(tenant_id)
        if not config:
            return False
        for k, v in updates.items():
            if hasattr(config, k):
                setattr(config, k, v)
        logger.info("White-label updated: tenant=%s", tenant_id)
        return True

    def delete(self, tenant_id: str) -> bool:
        if tenant_id in self._configs:
            del self._configs[tenant_id]
            return True
        return False

    def render_email(self, tenant_id: str, body_html: str,
                     subject: str = "") -> Optional[Dict[str, str]]:
        config = self.get(tenant_id)
        if not config:
            return None
        return self._renderer.render(config, body_html, subject)

    def list_all(self) -> List[WhiteLabelConfig]:
        return list(self._configs.values())
