"""
Deduplication Service: consolidates profiles of the same individual or business
discovered across multiple platforms into single, unified prospect records.
"""
import re
from typing import List, Dict
from app.schemas import ExtractedProfile, Prospect, SocialLink
from app.utils.normalizers import normalize_email, normalize_whatsapp

class DeduplicationService:
    @staticmethod
    def _simplify_name(name: str) -> str:
        """Simplifies name for fuzzy identity matching."""
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
        return cleaned

    def consolidate(self, profiles: List[ExtractedProfile]) -> List[Prospect]:
        """
        Consolidates profiles:
        - If two profiles share the exact same normalized name or same email/phone/wa,
          they are merged into a single prospect.
        - Combines verified links into social_link array without duplicates.
        - Preserves the most complete location.
        """
        grouped: Dict[str, Dict] = {}

        for p in profiles:
            key = None

            # Check matching email first
            if p.email:
                for k, existing in grouped.items():
                    if p.email.lower() in existing["emails"]:
                        key = k
                        break

            # Check matching phone / whatsapp next
            if not key and (p.phone or p.whatsapp):
                target_phone = (p.whatsapp or p.phone or "").strip()
                for k, existing in grouped.items():
                    if target_phone in existing["phones"]:
                        key = k
                        break

            # Check matching simplified name
            if not key:
                name_key = self._simplify_name(p.name)
                if name_key in grouped:
                    key = name_key
                else:
                    key = name_key

            if key not in grouped:
                grouped[key] = {
                    "name": p.name,
                    "location": p.location,
                    "social_links": [],
                    "seen_links": set(),
                    "emails": set(),
                    "phones": set(),
                }

            entry = grouped[key]

            # Merge location if existing has none or new is more specific
            if not entry["location"] and p.location:
                entry["location"] = p.location
            elif p.location and len(p.location) > len(entry["location"] or ""):
                entry["location"] = p.location

            # Add primary platform profile link
            # Note: Google is a discovery source, so we do not add generic Google search URLs
            if p.profile_url and p.platform != "Google" and p.profile_url not in entry["seen_links"]:
                entry["seen_links"].add(p.profile_url)
                entry["social_links"].append(SocialLink(platform=p.platform, link=p.profile_url))

            # Add Email as mailto:<email>
            if p.email:
                entry["emails"].add(p.email.lower())
                mailto_link = normalize_email(p.email)
                if mailto_link not in entry["seen_links"]:
                    entry["seen_links"].add(mailto_link)
                    entry["social_links"].append(SocialLink(platform="Email", link=mailto_link))

            # Add WhatsApp as wa.me link
            if p.whatsapp:
                entry["phones"].add(p.whatsapp)
                wa_link = normalize_whatsapp(p.whatsapp)
                if wa_link not in entry["seen_links"]:
                    entry["seen_links"].add(wa_link)
                    entry["social_links"].append(SocialLink(platform="WhatsApp", link=wa_link))

        # Convert grouped entries to final Prospect records
        prospects: List[Prospect] = []
        for item in grouped.values():
            # Ensure name is valid and not unknown
            if not item["name"] or item["name"] == "Unknown":
                continue
            prospects.append(Prospect(
                name=item["name"],
                location=item["location"],
                social_link=item["social_links"]
            ))

        return prospects

deduplication_service = DeduplicationService()
