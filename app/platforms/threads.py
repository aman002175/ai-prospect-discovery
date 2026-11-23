"""Threads platform discovery module."""
from app.platforms.base import BasePlatform
from app.schemas import PlatformName

class ThreadsPlatform(BasePlatform):
    platform_name: PlatformName = "Threads"
    is_limited: bool = True
    limit_reason: str = (
        "Threads web endpoints restrict automated scraping. Public @handle profile links "
        "and bio snippets are discovered via search engine indexing."
    )

threads_platform = ThreadsPlatform()
