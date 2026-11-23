"""Facebook platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class FacebookPlatform(BasePlatform):
    platform_name: PlatformName = "Facebook"
    is_limited: bool = True
    limit_reason: str = (
        "Facebook enforces authentication walls on personal profiles and community groups. "
        "Public business page links and snippets are discovered via search engine indexes."
    )

facebook_platform = FacebookPlatform()
