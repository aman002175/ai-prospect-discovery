"""
Relevance Service: scores discovered prospects based on semantic match to intent,
keyword presence, location validation, and evidence verification.
"""
import re
from typing import List
from app.schemas import ExtractedProfile, IntentData

class RelevanceService:
    @staticmethod
    def score_profile(profile: ExtractedProfile, intent: IntentData) -> float:
        """
        Calculates a relevance score [0.0 - 1.0] for a discovered candidate:
        - Interest/Domain keyword match (+0.4)
        - Audience persona match (+0.2)
        - Location match (+0.3)
        - Verified profile URL / contact details (+0.1)
        """
        score = 0.0
        combined_text = f"{profile.name} {profile.snippet} {profile.location or ''}".lower()

        # 1. Interest match
        interest_words = [w.lower() for w in re.findall(r"\w+", intent.interest) if len(w) > 2]
        if interest_words:
            matched_interest = sum(1 for w in interest_words if w in combined_text)
            score += 0.4 * (matched_interest / len(interest_words))

        # 2. Audience match
        audience_words = [w.lower() for w in re.findall(r"\w+", intent.audience) if len(w) > 2]
        if audience_words:
            matched_audience = sum(1 for w in audience_words if w in combined_text)
            score += 0.2 * (matched_audience / len(audience_words))

        # 3. Location match
        city = (intent.location.city or "").lower()
        country = (intent.location.country or "").lower()
        if city and city in combined_text:
            score += 0.2
        if country and country in combined_text:
            score += 0.1

        # 4. Evidence / contact boost
        if profile.profile_url:
            score += 0.05
        if profile.email or profile.phone or profile.whatsapp:
            score += 0.05

        return min(round(score, 2), 1.0)

    def filter_relevant(
        self,
        profiles: List[ExtractedProfile],
        intent: IntentData,
        min_threshold: float = 0.2
    ) -> List[ExtractedProfile]:
        """Scores candidate profiles and removes low-relevance results."""
        scored: List[ExtractedProfile] = []
        for p in profiles:
            p.relevance_score = self.score_profile(p, intent)
            if p.relevance_score >= min_threshold:
                scored.append(p)

        # Sort highest scoring prospects first
        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored

relevance_service = RelevanceService()
