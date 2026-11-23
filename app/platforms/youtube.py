"""YouTube platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class YouTubePlatform(BasePlatform):
    platform_name: PlatformName = "YouTube"
    is_limited: bool = False
    limit_reason: str = "Public YouTube channel pages and handle URLs (@handle) are publicly accessible."

youtube_platform = YouTubePlatform()
