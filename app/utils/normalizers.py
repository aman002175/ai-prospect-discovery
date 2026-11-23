"""Text, contact, and URL normalization utilities."""
import re
from typing import Optional

def normalize_name(raw_name: str) -> str:
    """
    Cleans raw title text from search results to extract clean prospect names.
    Strips platform suffixes, trailing @handles, and post/article headlines.
    Returns 'Unknown' if the string is a listicle or non-entity headline.
    """
    if not raw_name:
        return "Unknown"

    name = raw_name

    # Detect and filter out listicles or long article headlines
    non_entity_patterns = [
        r"^Top\s+\d+",
        r"^\d+\s+Best",
        r"^\d+\s+Things",
        r"^How\s+to\b",
        r"^Why\s+\b",
        r"^The\s+\d+\s+Best",
    ]
    for pat in non_entity_patterns:
        if re.search(pat, name, re.IGNORECASE):
            return "Unknown"

    # If title has headline prefixes/suffixes like "ABC News on Facebook: ...", extract entity
    platform_splitters = [
        r"\s+on\s+X:\s*.*$",
        r"\s+on\s+Facebook:\s*.*$",
        r"\s+on\s+Threads:\s*.*$",
        r"\s+on\s+Instagram:\s*.*$",
    ]
    for ps in platform_splitters:
        name = re.sub(ps, "", name, flags=re.IGNORECASE)

    # Remove platform branding patterns
    platform_patterns = [
        r"[-|•]\s*LinkedIn.*$",
        r"[-|•]\s*YouTube.*$",
        r"[-|•]\s*Instagram.*$",
        r"[-|•]\s*Facebook.*$",
        r"[-|•]\s*Twitter.*$",
        r"[-|•]\s*X.*$",
        r"[-|•]\s*Threads.*$",
        r"\(@[a-zA-Z0-9_.]+\)\s*[-|/•]\s*X.*$",
        r"\(@[a-zA-Z0-9_.]+\)\s*[-|/•]\s*Twitter.*$",
        r"on Instagram:.*$",
        r"on Threads:.*$",
        r"• Instagram photos and videos",
        r"[-|•]\s*Google Search.*$",
    ]

    for pat in platform_patterns:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)

    # If title has headline splitters like " - ", " | ", take the first segment
    for sep in [" | ", " - ", " : ", " – ", " — "]:
        if sep in name:
            segments = name.split(sep)
            candidate = segments[0].strip()
            if candidate and len(candidate.split()) <= 6:
                name = candidate
                break

    # Strip trailing handle if present (e.g. 'Mike Butcher @mikebutcher' -> 'Mike Butcher')
    name = re.sub(r"\s+@[a-zA-Z0-9_.]+$", "", name).strip()

    # Strip remaining trailing symbols and excess whitespace
    name = re.sub(r"[\"'\(\)\[\]{}|,–—]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Ensure length is reasonable for a person/business name
    if len(name) > 60 or len(name.split()) > 7:
        return "Unknown"

    return name if name else "Unknown"

def normalize_location(city: Optional[str] = None, state: Optional[str] = None, country: Optional[str] = None) -> Optional[str]:
    """Combines city, state, country into a standard 'City, Country' or 'City, State, Country' format."""
    parts = []
    if city and city.strip():
        parts.append(city.strip().title())
    if state and state.strip() and state.strip().lower() != (city or "").strip().lower():
        parts.append(state.strip().title())
    if country and country.strip():
        # Keep acronyms uppercase (USA, UK, UAE)
        c = country.strip()
        parts.append(c.upper() if len(c) <= 3 else c.title())

    if not parts:
        return None
    return ", ".join(parts)

def normalize_email(email: str) -> str:
    """Formats an email according to the API contract: mailto:<public email>."""
    clean = email.strip().lower()
    if clean.startswith("mailto:"):
        return clean
    return f"mailto:{clean}"

def normalize_phone(phone: str) -> str:
    """Formats a phone according to the API contract: tel:<public phone>."""
    digits = re.sub(r"[^\d+]", "", phone.strip())
    if not digits.startswith("+") and len(digits) == 10:
        digits = f"+1{digits}"
    return f"tel:{digits}"

def normalize_whatsapp(wa_or_phone: str) -> str:
    """Formats a WhatsApp contact according to the API contract: https://wa.me/<digits>."""
    digits = re.sub(r"\D", "", wa_or_phone.strip())
    return f"https://wa.me/{digits}"
