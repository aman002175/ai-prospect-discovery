"""
Prospect Service: orchestrates the multi-platform prospect discovery pipeline.
Validates input, runs concurrent searches across platforms with failure isolation,
extracts contact info, scores relevance, deduplicates, and formats output.
"""
import asyncio
import logging
from typing import List
from app.schemas import (
    ProspectDiscoveryResponse,
    Prospect,
    ExtractedProfile,
    RawSearchResult
)
from app.utils.validators import validate_query_text
from app.services.llm_service import llm_service
from app.services.relevance_service import relevance_service
from app.services.deduplication_service import deduplication_service
from app.platforms.google import google_platform
from app.platforms.linkedin import linkedin_platform
from app.platforms.x_platform import x_platform
from app.platforms.youtube import youtube_platform
from app.platforms.instagram import instagram_platform
from app.platforms.facebook import facebook_platform
from app.platforms.threads import threads_platform
from app.platforms.whatsapp import whatsapp_platform

logger = logging.getLogger(__name__)

PLATFORMS = [
    google_platform,
    linkedin_platform,
    x_platform,
    youtube_platform,
    instagram_platform,
    facebook_platform,
    threads_platform,
    whatsapp_platform
]

class ProspectService:
    async def discover_prospects(self, raw_query: str) -> ProspectDiscoveryResponse:
        clean_query = validate_query_text(raw_query)
        intent = await llm_service.extract_intent(clean_query)

        # return_exceptions=True isolates platform failures so one blocked network call does not abort the rest
        tasks = [platform.discover(intent) for platform in PLATFORMS]
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)

        all_raw_results: List[RawSearchResult] = []
        for i, res in enumerate(results_nested):
            if isinstance(res, Exception):
                logger.warning(
                    "Platform %s encountered error: %s",
                    PLATFORMS[i].platform_name,
                    type(res).__name__
                )
            elif isinstance(res, list):
                all_raw_results.extend(res)

        extracted_profiles: List[ExtractedProfile] = []
        for item in all_raw_results:
            platform_obj = next((p for p in PLATFORMS if p.platform_name == item.platform), None)
            if platform_obj:
                profile = platform_obj.extract_profile(item, intent)
                if profile:
                    extracted_profiles.append(profile)

        relevant_profiles = relevance_service.filter_relevant(extracted_profiles, intent)
        consolidated_prospects = deduplication_service.consolidate(relevant_profiles)

        return ProspectDiscoveryResponse(
            success=True,
            query=clean_query,
            total_prospects=len(consolidated_prospects),
            prospects=consolidated_prospects
        )

prospect_service = ProspectService()
