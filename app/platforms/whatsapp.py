"""WhatsApp contact and direct link discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class WhatsAppPlatform(BasePlatform):
    platform_name: PlatformName = "WhatsApp"
    is_limited: bool = False
    limit_reason: str = "Public wa.me direct links and public chat links are discovered from publicly listed contacts."

whatsapp_platform = WhatsAppPlatform()
