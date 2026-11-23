"""
Query Service: generates platform-specific targeted search queries
from intent parameters to find authentic public profiles.
"""
from typing import Dict, List
from app.schemas import IntentData, PlatformName

class QueryService:
    @staticmethod
    def build_platform_queries(intent: IntentData) -> Dict[PlatformName, List[str]]:
        """
        Generates platform-specific search dorks using targeted keywords,
        city/country filters, and platform site restrictions.
        """
        loc_str = ""
        if intent.location.city and intent.location.country:
            loc_str = f'"{intent.location.city}" "{intent.location.country}"'
        elif intent.location.city:
            loc_str = f'"{intent.location.city}"'
        elif intent.location.country:
            loc_str = f'"{intent.location.country}"'

        interest = intent.interest.strip()
        audience = intent.audience.strip()

        queries: Dict[PlatformName, List[str]] = {
            "LinkedIn": [
                f'site:linkedin.com/in/ "{interest}" {loc_str}',
                f'site:linkedin.com/in/ "{audience}" {loc_str}'
            ],
            "X": [
                f'site:x.com "{interest}" {loc_str}',
                f'site:twitter.com "{audience}" {loc_str}'
            ],
            "YouTube": [
                f'site:youtube.com/@ "{interest}" {loc_str}',
                f'site:youtube.com/channel/ "{interest}" {loc_str}'
            ],
            "Instagram": [
                f'site:instagram.com "{interest}" {loc_str}',
                f'site:instagram.com "{audience}" {loc_str}'
            ],
            "Facebook": [
                f'site:facebook.com "{interest}" {loc_str}',
                f'site:facebook.com "{audience}" {loc_str}'
            ],
            "Threads": [
                f'site:threads.net/@ "{interest}" {loc_str}',
                f'site:threads.net/@ "{audience}" {loc_str}'
            ],
            "WhatsApp": [
                f'"wa.me/" "{interest}" {loc_str}',
                f'site:chat.whatsapp.com "{interest}" {loc_str}'
            ],
            "Google": [
                f'"{interest}" "{audience}" {loc_str} "contact" OR "profile"',
                f'"{interest}" {loc_str} "email" OR "phone"'
            ],
            "Email": []
        }

        return queries

query_service = QueryService()
