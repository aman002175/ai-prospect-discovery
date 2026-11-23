"""Security validators, SSRF protection, and contact information verification."""
import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Optional
from app.config import ALLOWLISTED_DOMAINS
from app.schemas import PlatformName

# Strict email regex pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Regex to detect false-positive file extensions in email patterns
DISALLOWED_EMAIL_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

# Dummy / placeholder domains that must never be returned
DUMMY_EMAIL_DOMAINS = {
    "example.com", "sample.com", "test.com", "domain.com",
    "email.com", "yourdomain.com", "company.com", "placeholder.com"
}

def validate_query_text(query: str) -> str:
    """
    Validates user query string.
    Rejects empty, whitespace-only, or oversized queries (>300 chars).
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string.")
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query cannot be blank.")
    if len(cleaned) > 300:
        raise ValueError("Query exceeds maximum allowed length of 300 characters.")
    return cleaned

def is_safe_url(url: str) -> bool:
    # Verifies domain allowlist and resolves IP to prevent SSRF attacks against internal networks or cloud metadata
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname = hostname.lower().strip()

    # Reject localhost or common loopback string aliases
    if hostname in ("localhost", "0.0.0.0", "127.0.0.1", "::1", "ip6-localhost"):
        return False

    # Check if hostname matches or is a subdomain of an allowlisted domain
    domain_allowed = False
    for allowed in ALLOWLISTED_DOMAINS:
        if hostname == allowed or hostname.endswith("." + allowed):
            domain_allowed = True
            break

    if not domain_allowed:
        return False

    # Resolve IP and check against private / reserved ranges
    try:
        addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_reserved
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_unspecified
            ):
                return False
    except (socket.gaierror, ValueError):
        return False

    return True

def validate_email(email: Optional[str]) -> bool:
    """Validates public email address syntax and screens dummy values."""
    if not email:
        return False
    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return False
    lower = email.lower()
    for ext in DISALLOWED_EMAIL_EXTS:
        if lower.endswith(ext):
            return False
    domain = lower.split("@")[-1]
    if domain in DUMMY_EMAIL_DOMAINS:
        return False
    return True

def validate_phone(phone: Optional[str]) -> bool:
    """Validates public phone number format (between 7 and 15 digits)."""
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15

def validate_social_url(platform: PlatformName, url: str) -> bool:
    """Verifies that the social link matches the domain and structure of the platform."""
    return clean_to_profile_url(platform, url) is not None

def clean_to_profile_url(platform: PlatformName, url: str) -> Optional[str]:
    """
    Transforms public search, status, post, and video URLs into verified canonical
    public profile, channel, or business page URLs.
    Rejects generic search results, post/tweet/reel URLs that cannot be mapped to a profile,
    and non-profile pages.
    """
    if not url or not is_safe_url(url):
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    netloc = parsed.netloc.lower()
    path = parsed.path.strip()

    if platform == "LinkedIn":
        # Match /in/<slug> or /company/<slug>
        m_in = re.search(r"/(in/[a-zA-Z0-9_\-]+)", path, re.IGNORECASE)
        if m_in:
            slug = m_in.group(1).rstrip("/")
            return f"https://www.linkedin.com/{slug}"
        m_co = re.search(r"/(company/[a-zA-Z0-9_\-]+)", path, re.IGNORECASE)
        if m_co:
            slug = m_co.group(1).rstrip("/")
            return f"https://www.linkedin.com/{slug}"
        return None

    elif platform == "X":
        # Match x.com/<username> or twitter.com/<username>
        # Converts x.com/<username>/status/<id> -> https://x.com/<username>
        if "x.com" in netloc or "twitter.com" in netloc:
            parts = [p for p in path.split("/") if p]
            if parts:
                username = parts[0]
                reserved = {
                    "search", "explore", "home", "intent", "share", "login",
                    "signup", "hashtag", "i", "settings", "notifications",
                    "tos", "privacy", "help", "about", "rules", "download"
                }
                if username.lower() not in reserved and re.match(r"^[a-zA-Z0-9_]{1,30}$", username):
                    return f"https://x.com/{username}"
        return None

    elif platform == "Threads":
        # Match threads.net/@<handle>
        # Converts threads.net/@<handle>/post/<id> -> https://www.threads.net/@<handle>
        if "threads.net" in netloc:
            m = re.search(r"(@[a-zA-Z0-9_.]+)", path)
            if m:
                handle = m.group(1)
                return f"https://www.threads.net/{handle}"
        return None

    elif platform == "YouTube":
        # Match youtube.com/@<handle> or youtube.com/channel/<id> or youtube.com/c/<name>
        # Converts youtube.com/@<handle>/videos, /playlists -> https://www.youtube.com/@<handle>
        if "youtube.com" in netloc:
            m_at = re.search(r"(@[a-zA-Z0-9_.-]+)", path)
            if m_at:
                return f"https://www.youtube.com/{m_at.group(1)}"
            m_ch = re.search(r"/(channel/[a-zA-Z0-9_\-]+)", path)
            if m_ch:
                return f"https://www.youtube.com/{m_ch.group(1)}"
            m_c = re.search(r"/(c/[a-zA-Z0-9_\-]+)", path)
            if m_c:
                return f"https://www.youtube.com/{m_c.group(1)}"
        return None

    elif platform == "Instagram":
        # Match instagram.com/<username>
        # Rejects reels, p, explore, accounts
        if "instagram.com" in netloc:
            parts = [p for p in path.split("/") if p]
            if parts:
                candidate = parts[0]
                reserved = {
                    "p", "reel", "reels", "explore", "stories", "accounts",
                    "direct", "tv", "about", "developer", "legal"
                }
                if candidate.lower() not in reserved and re.match(r"^[a-zA-Z0-9_.]+$", candidate):
                    return f"https://www.instagram.com/{candidate}"
        return None

    elif platform == "Facebook":
        # Match facebook.com/<page_or_user>
        # Converts facebook.com/<page>/posts/... -> https://www.facebook.com/<page>
        if "facebook.com" in netloc:
            parts = [p for p in path.split("/") if p]
            if parts:
                reserved = {
                    "login", "help", "sharer", "share", "watch", "events",
                    "policies", "photo", "photos", "groups", "pages", "group"
                }
                candidate = parts[0]
                if candidate.lower() not in reserved and re.match(r"^[a-zA-Z0-9.-]+$", candidate):
                    return f"https://www.facebook.com/{candidate}"
        return None

    elif platform == "WhatsApp":
        # Must be wa.me/<digits>
        m = re.search(r"(?:wa\.me/|phone=)(\+?\d+)", f"{url} {path}")
        if m:
            digits = re.sub(r"\D", "", m.group(1))
            if 7 <= len(digits) <= 15:
                return f"https://wa.me/{digits}"
        return None

    elif platform == "Google":
        # Google is only a discovery source; reject generic search URLs!
        if "google.com" in netloc and ("business.google.com" in netloc or "/maps/place/" in path):
            return url
        return None

    return None
