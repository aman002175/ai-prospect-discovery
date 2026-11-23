"""
LLM Service for intent understanding and relevance scoring.
Integrates with Google Gemini 2.0 Flash REST API (Free Tier).
Includes deterministic rule-based fallback when GOOGLE_API_KEY is not configured or unavailable.
"""
import json
import logging
import re
from typing import Dict, Any, Optional
import httpx
from app.config import GOOGLE_API_KEY, REQUEST_TIMEOUT
from app.schemas import IntentData, LocationDetail

logger = logging.getLogger(__name__)

# Known cities, regions, and countries for accurate deterministic fallback parsing
LOCATION_MAP = {
    "washington dc": {"city": "Washington", "state": "DC", "country": "USA"},
    "washington": {"city": "Washington", "state": "DC", "country": "USA"},
    "new york": {"city": "New York", "state": "NY", "country": "USA"},
    "london": {"city": "London", "state": None, "country": "UK"},
    "ahmedabad": {"city": "Ahmedabad", "state": "Gujarat", "country": "India"},
    "dubai": {"city": "Dubai", "state": "Dubai", "country": "UAE"},
    "san francisco": {"city": "San Francisco", "state": "CA", "country": "USA"},
    "los angeles": {"city": "Los Angeles", "state": "CA", "country": "USA"},
    "chicago": {"city": "Chicago", "state": "IL", "country": "USA"},
    "boston": {"city": "Boston", "state": "MA", "country": "USA"},
    "toronto": {"city": "Toronto", "state": "ON", "country": "Canada"},
    "berlin": {"city": "Berlin", "state": None, "country": "Germany"},
    "paris": {"city": "Paris", "state": None, "country": "France"},
    "mumbai": {"city": "Mumbai", "state": "Maharashtra", "country": "India"},
    "delhi": {"city": "Delhi", "state": "Delhi", "country": "India"},
    "bangalore": {"city": "Bangalore", "state": "Karnataka", "country": "India"},
    "singapore": {"city": "Singapore", "state": None, "country": "Singapore"},
    "sydney": {"city": "Sydney", "state": "NSW", "country": "Australia"},
    "tokyo": {"city": "Tokyo", "state": None, "country": "Japan"},
}

TARGET_TYPE_BUSINESS_KEYWORDS = [
    "owner", "owners", "founder", "founders", "ceo", "director",
    "agency", "agencies", "restaurant", "restaurants", "shop", "shops",
    "company", "companies", "business", "firm", "firms", "startup", "startups"
]

class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or GOOGLE_API_KEY).strip()

    def _get_api_key(self) -> str:
        import os
        return os.getenv("GOOGLE_API_KEY", "").strip() or self.api_key

    async def extract_intent(self, query: str) -> IntentData:
        key = self._get_api_key()
        if key:
            try:
                intent = await self._call_gemini_intent(query, key)
                if intent:
                    logger.info("Parsed intent using Gemini 2.0 Flash for: '%s'", query)
                    return intent
            except Exception as e:
                logger.warning("Gemini intent call failed (%s), using rule-based parser.", type(e).__name__)
        else:
            logger.info("No GOOGLE_API_KEY found, using rule-based intent parser.")

        return self._rule_based_intent(query)

    async def _call_gemini_intent(self, query: str, key: str) -> Optional[IntentData]:
        """Calls Google Gemini 2.0 Flash REST API to parse query intent."""
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        system_prompt = (
            "You are an expert search query intent parser. Extract structured parameters from the user's prospect discovery query.\n"
            "Return strictly valid JSON matching this schema:\n"
            "{\n"
            '  "interest": "string (the domain, hobby, industry, or topic e.g. Football, Digital marketing, Cricket, Restaurants)",\n'
            '  "audience": "string (target persona e.g. lovers, agency owners, startup founders, restaurant owners)",\n'
            '  "target_type": "individual" or "business",\n'
            '  "location": {\n'
            '    "city": "string or null",\n'
            '    "state": "string or null",\n'
            '    "country": "string or null"\n'
            "  }\n"
            "}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\nQuery: {query}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                loc_data = parsed.get("location", {})
                return IntentData(
                    interest=parsed.get("interest", query),
                    audience=parsed.get("audience", "prospects"),
                    target_type=parsed.get("target_type", "individual"),
                    location=LocationDetail(
                        city=loc_data.get("city"),
                        state=loc_data.get("state"),
                        country=loc_data.get("country")
                    ),
                    raw_query=query
                )
        return None

    def _rule_based_intent(self, query: str) -> IntentData:
        """
        Deterministic rule-based query parser that handles standard queries
        without relying on external API availability.
        """
        q_lower = query.lower().strip()

        # 1. Location extraction
        city, state, country = None, None, None

        # Check dictionary of known cities first
        for loc_key, loc_info in LOCATION_MAP.items():
            if loc_key in q_lower:
                city = loc_info["city"]
                state = loc_info["state"]
                country = loc_info["country"]
                break

        # Check common country names if country wasn't found
        if not country:
            for c_name, c_code in [("usa", "USA"), ("united states", "USA"), ("uk", "UK"),
                                   ("united kingdom", "UK"), ("india", "India"), ("uae", "UAE"),
                                   ("dubai", "UAE"), ("canada", "Canada"), ("germany", "Germany")]:
                if re.search(r"\b" + re.escape(c_name) + r"\b", q_lower):
                    country = c_code
                    break

        # Regex fallback for "in <City> in <Country>" or "in <City>, <Country>"
        if not city:
            match = re.search(r"\bin\s+([A-Za-z\s]+?)\s+in\s+([A-Za-z\s]+)", query, re.IGNORECASE)
            if match:
                city = match.group(1).strip()
                country = match.group(2).strip()
            else:
                match_single = re.search(r"\bin\s+([A-Za-z\s]+)", query, re.IGNORECASE)
                if match_single:
                    city = match_single.group(1).strip()

        # 2. Target type detection
        target_type = "individual"
        for kw in TARGET_TYPE_BUSINESS_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                target_type = "business"
                break

        # 3. Interest and Audience extraction
        # Strip location part to isolate persona & topic
        topic_part = query
        for prep in [" in ", " near ", " around "]:
            if prep in topic_part.lower():
                idx = topic_part.lower().find(prep)
                topic_part = topic_part[:idx]
                break

        topic_clean = topic_part.strip()

        # Parse audience & interest
        if "agency owners" in topic_clean.lower():
            interest = "Digital marketing"
            audience = "Agency owners"
        elif "startup founders" in topic_clean.lower() or "founders" in topic_clean.lower():
            interest = "Startups"
            audience = "Founders"
        elif "restaurant owners" in topic_clean.lower():
            interest = "Restaurants"
            audience = "Restaurant owners"
        elif "football" in topic_clean.lower():
            interest = "Football"
            audience = "Football enthusiasts"
        elif "cricket" in topic_clean.lower():
            interest = "Cricket"
            audience = "Cricket enthusiasts"
        else:
            words = topic_clean.split()
            if len(words) >= 2:
                interest = " ".join(words[:-1])
                audience = words[-1]
            else:
                interest = topic_clean or query
                audience = "prospects"

        return IntentData(
            interest=interest,
            audience=audience,
            target_type=target_type,
            location=LocationDetail(city=city, state=state, country=country),
            raw_query=query
        )

# Global singleton
llm_service = LLMService()
