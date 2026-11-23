"""Base Platform class and common parsing logic."""
from abc import ABC
from typing import List, Optional
from app.schemas import PlatformName, IntentData, RawSearchResult, ExtractedProfile
from app.services.query_service import query_service
from app.services.search_service import search_service
from app.services.profile_extractor import profile_extractor
from app.utils.validators import clean_to_profile_url
from app.utils.normalizers import normalize_name, normalize_location

class BasePlatform(ABC):
    platform_name: PlatformName
    is_limited: bool = False
    limit_reason: str = ""

    async def discover(self, intent: IntentData) -> List[RawSearchResult]:
        all_queries = query_service.build_platform_queries(intent)
        platform_queries = all_queries.get(self.platform_name, [])
        results: List[RawSearchResult] = []

        # Use the primary search query for this platform
        for q in platform_queries[:1]:
            try:
                found = await search_service.search(q, self.platform_name, max_results=3)
                results.extend(found)
            except Exception:
                # Keep platform failures isolated
                pass

        return results

    def extract_profile(self, result: RawSearchResult, intent: IntentData) -> Optional[ExtractedProfile]:
        clean_name = normalize_name(result.title)
        if not clean_name or clean_name == "Unknown" or len(clean_name) < 2:
            return None

        # Clean to canonical profile URL (drops post/tweet/reel URLs)
        profile_url = clean_to_profile_url(self.platform_name, result.url)

        # Extract public email, phone, and WhatsApp contacts
        email, phone, whatsapp = profile_extractor.extract_contacts_from_text(
            f"{result.title} {result.snippet} {result.url}"
        )

        # Match location if mentioned in the snippet or query intent
        location = None
        loc_text = f"{result.title} {result.snippet}".lower()
        if intent.location.city and intent.location.city.lower() in loc_text:
            location = normalize_location(intent.location.city, intent.location.state, intent.location.country)
        elif intent.location.country and intent.location.country.lower() in loc_text:
            location = normalize_location(None, None, intent.location.country)

        # Must have either a valid profile URL or a direct contact
        if not profile_url and not email and not phone and not whatsapp:
            return None

        return ExtractedProfile(
            name=clean_name,
            location=location,
            platform=self.platform_name,
            profile_url=profile_url,
            email=email,
            phone=phone,
            whatsapp=whatsapp,
            snippet=result.snippet
        )
