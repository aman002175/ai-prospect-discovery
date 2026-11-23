"""Application configuration and security settings."""
import os
from typing import Set
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# API Keys & Secrets (Loaded strictly from environment)
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "").strip()
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()

# Server Settings
PORT: int = int(os.getenv("PORT", "4000"))
HOST: str = os.getenv("HOST", "0.0.0.0")

# Outbound HTTP Requests (Mandatory 10-second timeout)
REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "10.0"))

# SSRF Protection: Strict Domain Allowlist
# Only outbound requests to search engines and recognized public platform profiles are permitted.
ALLOWLISTED_DOMAINS: Set[str] = {
    # Free Search Backends & Search APIs
    "duckduckgo.com",
    "html.duckduckgo.com",
    "lite.duckduckgo.com",
    "bing.com",
    "www.bing.com",
    "api.tavily.com",
    "tavily.com",
    # Platform Domains
    "linkedin.com",
    "www.linkedin.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "threads.net",
    "www.threads.net",
    "wa.me",
    "api.whatsapp.com",
    "chat.whatsapp.com",
    "whatsapp.com",
    "www.whatsapp.com",
    "google.com",
    "www.google.com",
    "generativelanguage.googleapis.com",
}
