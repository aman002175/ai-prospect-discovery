"""Google discovery platform module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class GooglePlatform(BasePlatform):
    platform_name: PlatformName = "Google"
    is_limited: bool = False
    limit_reason: str = "Used as primary search indexing and public business discovery backend."

google_platform = GooglePlatform()
