"""X (formerly Twitter) platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class XPlatform(BasePlatform):
    platform_name: PlatformName = "X"
    is_limited: bool = True
    limit_reason: str = (
        "X restricts unauthenticated profile inspection with login requirements. "
        "Public handles, account names, and bio snippets are discovered through public search "
        "indexing and validated against authentic x.com profiles."
    )

x_platform = XPlatform()
