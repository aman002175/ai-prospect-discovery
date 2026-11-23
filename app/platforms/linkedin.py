"""LinkedIn platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class LinkedInPlatform(BasePlatform):
    platform_name: PlatformName = "LinkedIn"
    is_limited: bool = True
    limit_reason: str = (
        "LinkedIn enforces strict anti-scraping controls, requiring authenticated login sessions. "
        "Public profiles are discovered via search engine indexing, and metadata is parsed from "
        "public search snippets without accessing private or login-walled pages."
    )

linkedin_platform = LinkedInPlatform()
