"""
Profile Extractor: extracts contact details (email, phone, wa.me)
from public web text and validates URLs with SSRF protection.
"""
import re
from typing import Optional, Tuple
import httpx
from bs4 import BeautifulSoup
from app.config import REQUEST_TIMEOUT
from app.utils.validators import is_safe_url, validate_email, validate_phone

class ProfileExtractor:
    @staticmethod
    def extract_contacts_from_text(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts public email, phone, and WhatsApp numbers from raw text.
        Returns: (email, phone, whatsapp)
        """
        email = None
        phone = None
        whatsapp = None

        # Public email
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", text)
        if email_match and validate_email(email_match.group(0)):
            email = email_match.group(0).strip()

        # WhatsApp link
        wa_match = re.search(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send\?phone=)/(\+?\d+)", text)
        if wa_match:
            whatsapp = wa_match.group(1).strip()

        # Public phone number
        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phone_match and validate_phone(phone_match.group(0)):
            phone = phone_match.group(0).strip()

        return email, phone, whatsapp

    @staticmethod
    async def enrich_from_public_page(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Attempts to fetch public page to extract listed contacts when permitted.
        Enforces SSRF safety checks and 10s timeout. Fails gracefully.
        """
        if not is_safe_url(url):
            return None, None, None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)
                    return ProfileExtractor.extract_contacts_from_text(text)
        except Exception:
            pass

        return None, None, None

profile_extractor = ProfileExtractor()
