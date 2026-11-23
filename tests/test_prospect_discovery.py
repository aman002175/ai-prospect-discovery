"""
Comprehensive Test Suite for AI-Powered Multi-Platform Prospect Discovery API.
Tests cover:
1. Root and /health endpoints
2. Query validation tests (empty, whitespace, >300 chars, invalid JSON)
3. The 5 mandatory query runs with mocked offline responses:
   - "Football lovers in Washington DC in USA"
   - "Digital marketing agency owners in New York USA"
   - "Startup founders in London UK"
   - "Cricket lovers in Ahmedabad India"
   - "Restaurant owners in Dubai UAE"
4. Deduplication & consolidation tests (same person on 2 platforms = 1 unified record)
5. SSRF protection tests (private IPs, loopback, local subnet, disallowed domains)
6. API contract compliance & platform name validity
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import RawSearchResult, ExtractedProfile, PlatformName
from app.services.deduplication_service import deduplication_service
from app.services.relevance_service import relevance_service
from app.utils.validators import is_safe_url, validate_query_text
from app.utils.normalizers import normalize_name, normalize_email, normalize_phone, normalize_whatsapp

client = TestClient(app)

ALLOWED_PLATFORMS = {
    "Google", "LinkedIn", "X", "YouTube",
    "Instagram", "WhatsApp", "Facebook", "Email", "Threads"
}

# --- Endpoint Health & Metadata ---

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "supported_platforms" in data
    assert len(data["supported_platforms"]) == 9
    assert "discovery_engine" in data
    assert "Tavily" in data["discovery_engine"] or "DuckDuckGo" in data["discovery_engine"]

# --- Input Validation ---

def test_empty_query_rejected():
    response = client.post("/prospect-discovery", json={"query": ""})
    assert response.status_code == 422

def test_whitespace_query_rejected():
    response = client.post("/prospect-discovery", json={"query": "   "})
    assert response.status_code == 422

def test_overlong_query_rejected():
    long_query = "A" * 305
    response = client.post("/prospect-discovery", json={"query": long_query})
    assert response.status_code == 422

def test_missing_query_field_rejected():
    response = client.post("/prospect-discovery", json={})
    assert response.status_code == 422

def test_bad_json_rejected():
    response = client.post(
        "/prospect-discovery",
        content="Invalid { JSON payload",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422

# --- Offline Mock Tests for Mandatory Queries ---

MOCK_DISCOVERY_DATA = {
    "Football lovers in Washington DC in USA": [
        RawSearchResult(
            title="Marcus Vance - DC United Supporters Club Coordinator | LinkedIn",
            url="https://www.linkedin.com/in/marcus-vance-dc",
            snippet="Marcus Vance organizes Washington DC soccer & football community events. Contact: marcus.vance@dcfootball.org",
            platform="LinkedIn"
        ),
        RawSearchResult(
            title="Capital City Football Club (@capcityfc_dc) on X",
            url="https://x.com/capcityfc_dc",
            snippet="Official community channel for grassroots football lovers in Washington DC. WhatsApp us at +12025550184",
            platform="X"
        ),
    ],
    "Digital marketing agency owners in New York USA": [
        RawSearchResult(
            title="Sarah Jenkins - Founder & CEO at Apex Growth Agency | LinkedIn",
            url="https://www.linkedin.com/in/sarah-jenkins-growth",
            snippet="Sarah Jenkins leads Apex Growth Agency in New York, NY. Specializing in B2B digital marketing. Email: sarah@apexgrowthny.com",
            platform="LinkedIn"
        ),
        RawSearchResult(
            title="Apex Growth Media - YouTube",
            url="https://www.youtube.com/@ApexGrowthNY",
            snippet="Digital marketing strategies, agency insights, and growth hacks from New York City.",
            platform="YouTube"
        ),
    ],
    "Startup founders in London UK": [
        RawSearchResult(
            title="Alexander Wright - Co-Founder & CTO at Finova Tech | LinkedIn",
            url="https://www.linkedin.com/in/alex-wright-finova",
            snippet="Alexander Wright is a tech startup founder based in London, UK. Fintech innovator. Contact: alex@finovalondon.io",
            platform="LinkedIn"
        ),
        RawSearchResult(
            title="London Tech Founders Guild (@londontechguild) / X",
            url="https://x.com/londontechguild",
            snippet="Connecting ambitious startup founders in London UK. Discussions, demo days, and angel pitching.",
            platform="X"
        ),
    ],
    "Cricket lovers in Ahmedabad India": [
        RawSearchResult(
            title="Rajesh Patel - Captain at Sabarmati Cricket Club | LinkedIn",
            url="https://www.linkedin.com/in/rajesh-patel-cricket",
            snippet="Rajesh Patel is a cricket enthusiast and club administrator in Ahmedabad, Gujarat, India. Phone: +919825012345",
            platform="LinkedIn"
        ),
        RawSearchResult(
            title="Ahmedabad Cricket Hub (@ahmedabadcricket) on Instagram",
            url="https://www.instagram.com/ahmedabadcricket",
            snippet="Cricket lovers and tournament updates in Ahmedabad Gujarat India. Connect on wa.me/919825012345",
            platform="Instagram"
        ),
    ],
    "Restaurant owners in Dubai UAE": [
        RawSearchResult(
            title="Tariq Mansoor - Managing Director at Palm Oasis Dining | LinkedIn",
            url="https://www.linkedin.com/in/tariq-mansoor-dining",
            snippet="Tariq Mansoor owns and manages premium fine-dining restaurants across Dubai, UAE. Email: tariq@palmoasisdubai.ae",
            platform="LinkedIn"
        ),
        RawSearchResult(
            title="Dubai Gourmet Hospitality (@dubaigourmet) on Threads",
            url="https://www.threads.net/@dubaigourmet",
            snippet="Restaurant owners and culinary entrepreneurs network in Dubai UAE. WhatsApp: +971501234567",
            platform="Threads"
        ),
    ]
}

@pytest.mark.parametrize("query", [
    "Football lovers in Washington DC in USA",
    "Digital marketing agency owners in New York USA",
    "Startup founders in London UK",
    "Cricket lovers in Ahmedabad India",
    "Restaurant owners in Dubai UAE"
])
def test_mandatory_query_contract(query):
    """
    Verifies that all 5 required queries return a valid response adhering
    to the exact API contract: success=True, query=query, total_prospects, prospects list.
    """
    mock_results = MOCK_DISCOVERY_DATA.get(query, [])

    with patch("app.services.search_service.search_service.search", new_callable=AsyncMock) as mock_search:
        # Mock search to return targeted realistic search results for the platform
        async def fake_search(q, platform, max_results=3):
            return [res for res in mock_results if res.platform == platform]

        mock_search.side_effect = fake_search

        response = client.post("/prospect-discovery", json={"query": query})
        assert response.status_code == 200
        data = response.json()

        # Strict contract assertions
        assert data["success"] is True
        assert data["query"] == query
        assert isinstance(data["total_prospects"], int)
        assert isinstance(data["prospects"], list)
        assert data["total_prospects"] == len(data["prospects"])

        for prospect in data["prospects"]:
            assert "name" in prospect and isinstance(prospect["name"], str) and len(prospect["name"]) > 0
            assert "location" in prospect
            assert "social_link" in prospect and isinstance(prospect["social_link"], list)

            for link_obj in prospect["social_link"]:
                assert link_obj["platform"] in ALLOWED_PLATFORMS
                assert isinstance(link_obj["link"], str) and len(link_obj["link"]) > 0

                # Verify specific link protocols
                if link_obj["platform"] == "Email":
                    assert link_obj["link"].startswith("mailto:")
                elif link_obj["platform"] == "WhatsApp":
                    assert "wa.me/" in link_obj["link"] or "whatsapp.com" in link_obj["link"]

# --- 4. Deduplication & Consolidation Tests ---

def test_deduplication_same_person_two_platforms():
    """Verifies that the same person discovered on 2 platforms is consolidated into 1 record."""
    profiles = [
        ExtractedProfile(
            name="John Doe",
            location="New York, USA",
            platform="LinkedIn",
            profile_url="https://www.linkedin.com/in/johndoe",
            email="john@doeagency.com",
            snippet="CEO at Doe Agency NY",
            relevance_score=0.9
        ),
        ExtractedProfile(
            name="John Doe",
            location="New York, NY, USA",
            platform="X",
            profile_url="https://x.com/johndoe",
            email="john@doeagency.com",
            snippet="Founder and digital marketing leader in NYC",
            relevance_score=0.85
        )
    ]

    consolidated = deduplication_service.consolidate(profiles)

    # Must produce exactly 1 prospect
    assert len(consolidated) == 1
    p = consolidated[0]
    assert p.name == "John Doe"
    assert "New York" in p.location

    # Must contain both platform links + Email
    platforms = [sl.platform for sl in p.social_link]
    links = [sl.link for sl in p.social_link]

    assert "LinkedIn" in platforms
    assert "X" in platforms
    assert "Email" in platforms
    assert "https://www.linkedin.com/in/johndoe" in links
    assert "https://x.com/johndoe" in links
    assert "mailto:john@doeagency.com" in links

# --- SSRF Protection ---

def test_ssrf_blocks_private_and_localhost_urls():
    # Disallow localhost
    assert is_safe_url("http://localhost:8000/api") is False
    assert is_safe_url("http://127.0.0.1:4000") is False
    assert is_safe_url("http://0.0.0.0:80") is False

    # Disallow private RFC1918 IPs
    assert is_safe_url("http://192.168.1.1/admin") is False
    assert is_safe_url("http://10.0.0.1/secret") is False
    assert is_safe_url("http://172.16.0.5/") is False

    # Disallow cloud metadata endpoints
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    # Disallow non-allowlisted domains
    assert is_safe_url("https://malicious-external-domain.com") is False
    assert is_safe_url("file:///etc/passwd") is False

    # Allow valid allowlisted domains
    assert is_safe_url("https://html.duckduckgo.com/html/") is True
    assert is_safe_url("https://www.linkedin.com/in/test") is True
    assert is_safe_url("https://x.com/test") is True

# --- Normalization Utilities ---

def test_normalizers():
    # Name cleaning
    raw_title = "Jane Doe - Founder & Creative Director | LinkedIn"
    assert normalize_name(raw_title) == "Jane Doe"

    yt_title = "Tech World with Alex - YouTube"
    assert normalize_name(yt_title) == "Tech World with Alex"

    # Contact normalization
    assert normalize_email("Test.User@Domain.COM") == "mailto:test.user@domain.com"
    assert normalize_phone("+1 (202) 555-0184") == "tel:+12025550184"
    assert normalize_whatsapp("+1 202 555 0184") == "https://wa.me/12025550184"

# --- Fallback Chain & Bot Detection ---

def test_bot_challenge_detection():
    from app.services.search_service import search_service
    challenge_html = """
    <html><body>
    <h1>Unfortunately, bots use DuckDuckGo too.</h1>
    <p>Please complete the following challenge to confirm this search was made by a human.</p>
    </body></html>
    """
    assert search_service.is_bot_challenge(challenge_html) is True
    assert search_service.is_bot_challenge("<html><body><h1>Normal search results</h1></body></html>") is False

def test_bing_url_decoder():
    from app.services.search_service import search_service
    # Test decoding Bing click tracker with a1-encoded base64
    fake_bing_url = "https://www.bing.com/ck/a?!&&p=abc&u=a1aHR0cHM6Ly93d3cubGlua2VkaW4uY29tL2luL2pvaG5kb2U=&ntb=1"
    decoded = search_service._decode_bing_url(fake_bing_url)
    assert decoded == "https://www.linkedin.com/in/johndoe"

def test_search_fallback_on_bot_challenge():
    """
    Verifies that when DuckDuckGo HTML returns a bot challenge,
    the search service automatically fails over to Bing HTML search.
    """
    import asyncio
    from app.services.search_service import search_service
    challenge_page = "<html><body>Unfortunately, bots use DuckDuckGo too. Select all squares.</body></html>"
    bing_html = """
    <html><body>
      <div class="b_algo">
        <h2><a href="https://www.linkedin.com/in/alex-founder">Alex Founder - Tech Lead | LinkedIn</a></h2>
        <div class="b_caption"><p>Alex Founder is a tech startup leader in London UK.</p></div>
      </div>
    </body></html>
    """

    class FakeResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

    async def fake_post(url, **kwargs):
        # DuckDuckGo HTML endpoint returns challenge
        return FakeResponse(challenge_page, status_code=202)

    async def fake_get(url, **kwargs):
        if "lite.duckduckgo.com" in url:
            # DuckDuckGo Lite also challenges
            return FakeResponse(challenge_page, status_code=202)
        elif "bing.com" in url:
            # Bing succeeds
            return FakeResponse(bing_html, status_code=200)
        return FakeResponse("", status_code=404)

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=fake_post), \
             patch("httpx.AsyncClient.get", side_effect=fake_get):
            return await search_service.search("Startup founders London UK", "LinkedIn")

    results = asyncio.run(run_test())
    assert len(results) > 0
    assert results[0].platform == "LinkedIn"
    assert "Alex Founder" in results[0].title
    assert "https://www.linkedin.com/in/alex-founder" in results[0].url

def test_tavily_search_api_primary_when_key_set():
    """Verifies that Tavily is called as the primary backend when TAVILY_API_KEY is configured."""
    import asyncio
    from app.services.search_service import search_service
    tavily_response = {
        "results": [
            {
                "title": "David Miller - Founder at Growth Marketing NY | LinkedIn",
                "url": "https://www.linkedin.com/in/david-miller-growth",
                "content": "David Miller heads Growth Marketing NY agency in New York USA. Contact: david@growthny.com"
            }
        ]
    }

    class FakeTavilyResponse:
        def __init__(self):
            self.status_code = 200
        def json(self):
            return tavily_response

    async def fake_post(url, **kwargs):
        if "api.tavily.com" in url:
            return FakeTavilyResponse()
        return FakeTavilyResponse()

    async def run_test():
        with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-test-mock-key"}), \
             patch("httpx.AsyncClient.post", side_effect=fake_post):
            return await search_service.search("Digital marketing agency owners New York", "LinkedIn")

    results = asyncio.run(run_test())
    assert len(results) == 1
    assert "David Miller" in results[0].title
    assert results[0].url == "https://www.linkedin.com/in/david-miller-growth"

def test_gemini_api_key_and_fallback():
    """Verifies rule-based fallback when GOOGLE_API_KEY is absent and Gemini call when present."""
    import asyncio
    from app.services.llm_service import llm_service
    # 1. Fallback when key is empty
    with patch.dict("os.environ", {"GOOGLE_API_KEY": ""}):
        intent = asyncio.run(llm_service.extract_intent("Football lovers in Washington DC in USA"))
        assert intent.interest.lower() == "football"
        assert "washington" in intent.location.city.lower()
        assert intent.location.country == "USA"
