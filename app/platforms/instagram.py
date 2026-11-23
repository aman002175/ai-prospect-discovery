"""Instagram platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class InstagramPlatform(BasePlatform):
    platform_name: PlatformName = "Instagram"
    is_limited: bool = True
    limit_reason: str = (
        "Instagram redirects automated requests to login dialogs. Public accounts, usernames, "
        "and bio snippets are discovered via search index metadata without bypassing authentication."
    )

instagram_platform = InstagramPlatform()
