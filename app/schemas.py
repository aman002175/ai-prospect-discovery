"""Pydantic schemas adhering to the exact API contract and internal pipeline models."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

# The 9 exact supported platform names specified by the API contract
PlatformName = Literal[
    "Google",
    "LinkedIn",
    "X",
    "YouTube",
    "Instagram",
    "WhatsApp",
    "Facebook",
    "Email",
    "Threads"
]

class SocialLink(BaseModel):
    """Represents a verified public social or contact link."""
    platform: PlatformName
    link: str

class Prospect(BaseModel):
    """Represents a discovered prospect record."""
    name: str = Field(..., description="Required full name or business entity name")
    location: Optional[str] = Field(default=None, description="City, Country when available")
    social_link: List[SocialLink] = Field(
        default_factory=list,
        description="List of verified public social or contact links"
    )

class ProspectDiscoveryRequest(BaseModel):
    """Incoming request model for prospect discovery."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Natural language search query (1-300 chars)"
    )

    @field_validator("query")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace only.")
        if len(v.strip()) > 300:
            raise ValueError("Query exceeds maximum allowed length of 300 characters.")
        return v.strip()

class ProspectDiscoveryResponse(BaseModel):
    """Outgoing response matching the exact specified API contract."""
    success: bool = True
    query: str
    total_prospects: int
    prospects: List[Prospect]

# Internal pipeline data models
class LocationDetail(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class IntentData(BaseModel):
    """Structured query intent extracted by LLM or rule-based parser."""
    interest: str
    audience: str
    target_type: Literal["individual", "business"] = "individual"
    location: LocationDetail = Field(default_factory=LocationDetail)
    raw_query: str = ""

class RawSearchResult(BaseModel):
    """Raw result returned by search backend."""
    title: str
    url: str
    snippet: str
    platform: PlatformName

class ExtractedProfile(BaseModel):
    """Candidate profile extracted from public search snippet or page."""
    name: str
    location: Optional[str] = None
    platform: PlatformName
    profile_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    snippet: str = ""
    relevance_score: float = 0.0
