"""Search backend integration with fallback handling."""
import asyncio
import base64
import logging
import os
import re
import urllib.parse
from typing import List, Optional, Tuple
import httpx
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, TAVILY_API_KEY
from app.schemas import RawSearchResult, PlatformName
from app.utils.validators import is_safe_url

logger = logging.getLogger(__name__)

USER_AGENT_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Text signatures indicating anti-bot or CAPTCHA challenges
CHALLENGE_SIGNATURES = [
    "unfortunately, bots use duckduckgo too",
    "confirm this search was made by a human",
    "select all squares containing",
    "please complete the following challenge",
    "unusual traffic from your computer network",
    "please verify you are a human",
    "cf-challenge",
    "recaptcha",
    "hcaptcha",
]

class SearchService:
    def __init__(self):
        self.endpoint_ddg_html = "https://html.duckduckgo.com/html/"
        self.endpoint_ddg_lite = "https://lite.duckduckgo.com/lite/"
        self.endpoint_bing = "https://www.bing.com/search"
        self.endpoint_tavily = "https://api.tavily.com/search"

    def _get_tavily_key(self) -> str:
        return os.getenv("TAVILY_API_KEY", "").strip() or TAVILY_API_KEY

    @staticmethod
    def is_bot_challenge(text: str) -> bool:
        lower = text.lower()
        return any(sig in lower for sig in CHALLENGE_SIGNATURES)

    async def search(self, query: str, platform: PlatformName, max_results: int = 5) -> List[RawSearchResult]:
        # Tavily is tried first if a key is provided
        tavily_key = self._get_tavily_key()
        if tavily_key:
            results = await self._search_tavily(query, platform, tavily_key, max_results)
            if results:
                logger.info("Search succeeded via Tavily for platform %s (found %d)", platform, len(results))
                return results
            await asyncio.sleep(0.3)

        # Fallback to DuckDuckGo HTML
        results = await self._search_ddg_html(query, platform, max_results)
        if results:
            logger.info("Search succeeded via DuckDuckGo HTML for platform %s (found %d)", platform, len(results))
            return results
        await asyncio.sleep(0.3)

        # Fallback to DuckDuckGo Lite if HTML was challenged or returned empty
        results = await self._search_ddg_lite(query, platform, max_results)
        if results:
            logger.info("Search succeeded via DuckDuckGo Lite for platform %s (found %d)", platform, len(results))
            return results
        await asyncio.sleep(0.3)

        # Final fallback to Bing HTML
        results = await self._search_bing_html(query, platform, max_results)
        if results:
            logger.info("Search succeeded via Bing HTML for platform %s (found %d)", platform, len(results))
            return results

        logger.warning("All search backends in fallback chain returned 0 results for query: '%s' [%s]", query, platform)
        return []

    async def _search_tavily(
        self, query: str, platform: PlatformName, api_key: str, max_results: int
    ) -> List[RawSearchResult]:
        if not is_safe_url(self.endpoint_tavily):
            return []

        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(self.endpoint_tavily, json=payload)
                logger.info("Tavily API responded with HTTP %d for query: '%s'", resp.status_code, query)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_items = data.get("results", [])
                    results: List[RawSearchResult] = []
                    for item in raw_items:
                        url = item.get("url", "")
                        title = item.get("title", "")
                        snippet = item.get("content", "")
                        if url and is_safe_url(url):
                            results.append(RawSearchResult(
                                title=title,
                                url=url,
                                snippet=snippet,
                                platform=platform
                            ))
                    if results:
                        return results
                    else:
                        logger.info("Tavily returned 0 results for query: '%s'", query)
        except Exception as e:
            logger.warning("Tavily API request failed: %s", type(e).__name__)

        return []

    async def _search_ddg_html(self, query: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        if not is_safe_url(self.endpoint_ddg_html):
            return []

        headers = {
            "User-Agent": USER_AGENT_BROWSER,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.post(
                    self.endpoint_ddg_html,
                    data={"q": query},
                    headers=headers
                )
                is_challenge = self.is_bot_challenge(resp.text)
                logger.info(
                    "DuckDuckGo HTML responded with HTTP %d (Bot Challenge: %s) for query: '%s'",
                    resp.status_code, is_challenge, query
                )

                if is_challenge:
                    logger.warning("Bot challenge encountered on DuckDuckGo HTML. Advancing to next backend.")
                    return []

                if resp.status_code in (200, 202):
                    results = self._parse_ddg_html(resp.text, platform, max_results)
                    if results:
                        return results
                    self._log_zero_result_diagnostic("DuckDuckGo HTML", resp.text)
        except Exception as e:
            logger.warning("DuckDuckGo HTML request failed: %s", type(e).__name__)

        return []

    async def _search_ddg_lite(self, query: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        lite_url = f"{self.endpoint_ddg_lite}?q={urllib.parse.quote(query)}"
        if not is_safe_url(lite_url):
            return []

        headers = {
            "User-Agent": USER_AGENT_BROWSER,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(lite_url, headers=headers)
                is_challenge = self.is_bot_challenge(resp.text)
                logger.info(
                    "DuckDuckGo Lite responded with HTTP %d (Bot Challenge: %s) for query: '%s'",
                    resp.status_code, is_challenge, query
                )

                if is_challenge:
                    logger.warning("Bot challenge encountered on DuckDuckGo Lite. Advancing to next backend.")
                    return []

                if resp.status_code in (200, 202):
                    results = self._parse_ddg_lite(resp.text, platform, max_results)
                    if results:
                        return results
                    self._log_zero_result_diagnostic("DuckDuckGo Lite", resp.text)
        except Exception as e:
            logger.warning("DuckDuckGo Lite request failed: %s", type(e).__name__)

        return []

    async def _search_bing_html(self, query: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        bing_url = f"{self.endpoint_bing}?q={urllib.parse.quote(query)}"
        if not is_safe_url(bing_url):
            return []

        headers = {
            "User-Agent": USER_AGENT_BROWSER,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(bing_url, headers=headers)
                is_challenge = self.is_bot_challenge(resp.text)
                logger.info(
                    "Bing HTML responded with HTTP %d (Bot Challenge: %s) for query: '%s'",
                    resp.status_code, is_challenge, query
                )

                if is_challenge:
                    logger.warning("Bot challenge encountered on Bing HTML.")
                    return []

                if resp.status_code == 200:
                    results = self._parse_bing_html(resp.text, platform, max_results)
                    if results:
                        return results
                    self._log_zero_result_diagnostic("Bing HTML", resp.text)
        except Exception as e:
            logger.warning("Bing HTML search request failed: %s", type(e).__name__)

        return []

    # --- Parsers ---

    def _parse_ddg_html(self, html_text: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        results: List[RawSearchResult] = []
        soup = BeautifulSoup(html_text, "html.parser")

        for result_div in soup.find_all("div", class_="result__body"):
            title_tag = result_div.find("a", class_="result__url") or result_div.find("a", class_="result__a")
            snippet_tag = result_div.find("a", class_="result__snippet")

            if not title_tag:
                continue

            raw_url = title_tag.get("href", "")
            title = title_tag.get_text(strip=True)
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            clean_url = self._extract_clean_url(raw_url)
            if clean_url and is_safe_url(clean_url):
                results.append(RawSearchResult(
                    title=title,
                    url=clean_url,
                    snippet=snippet,
                    platform=platform
                ))
                if len(results) >= max_results:
                    break

        return results

    def _parse_ddg_lite(self, html_text: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        results: List[RawSearchResult] = []
        soup = BeautifulSoup(html_text, "html.parser")

        links = soup.find_all("a", class_="result-link")
        snippets = soup.find_all("td", class_="result-snippet")

        for i, link in enumerate(links):
            title = link.get_text(strip=True)
            raw_url = link.get("href", "")
            snippet = snippets[i].get_text(strip=True) if i < len(snippets) else ""

            clean_url = self._extract_clean_url(raw_url)
            if clean_url and is_safe_url(clean_url):
                results.append(RawSearchResult(
                    title=title,
                    url=clean_url,
                    snippet=snippet,
                    platform=platform
                ))
                if len(results) >= max_results:
                    break

        return results

    def _parse_bing_html(self, html_text: str, platform: PlatformName, max_results: int) -> List[RawSearchResult]:
        """Parses Bing HTML .b_algo result blocks and decodes redirected URLs."""
        results: List[RawSearchResult] = []
        soup = BeautifulSoup(html_text, "html.parser")

        blocks = soup.select(".b_algo")
        for b in blocks:
            h2 = b.find("h2")
            if not h2:
                continue
            a_tag = h2.find("a")
            if not a_tag:
                continue

            title = h2.get_text(strip=True)
            raw_href = a_tag.get("href", "")
            clean_url = self._decode_bing_url(raw_href)

            snippet_el = b.select_one(".b_caption p") or b.select_one("p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            if clean_url and is_safe_url(clean_url):
                results.append(RawSearchResult(
                    title=title,
                    url=clean_url,
                    snippet=snippet,
                    platform=platform
                ))
                if len(results) >= max_results:
                    break

        return results

    @staticmethod
    def _extract_clean_url(raw_url: str) -> str:
        """Extracts true destination URL from DuckDuckGo redirect paths."""
        if not raw_url:
            return ""
        if "/l/?" in raw_url or "duckduckgo.com/l/" in raw_url:
            parsed = urllib.parse.urlparse(raw_url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return qs["uddg"][0]
        return raw_url

    @staticmethod
    def _decode_bing_url(href: str) -> str:
        """Decodes base64 destination URL from Bing click tracking redirects."""
        if not href:
            return ""
        if "bing.com/ck/a?" in href and "u=" in href:
            try:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                if "u" in qs and qs["u"]:
                    u_val = qs["u"][0]
                    # Bing encodes URLs with 'a1' prefix + standard base64
                    if u_val.startswith("a1"):
                        b64 = u_val[2:]
                        b64 += "=" * ((4 - len(b64) % 4) % 4)
                        decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                        if decoded.startswith("http://") or decoded.startswith("https://"):
                            return decoded
            except Exception:
                pass
        return href

    @staticmethod
    def _log_zero_result_diagnostic(backend_name: str, html_text: str):
        """Logs page title and first 500 characters when 0 results are extracted without leaking secrets."""
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            page_title = soup.title.string.strip() if soup.title and soup.title.string else "(no title)"
            text_preview = soup.get_text(separator=" ", strip=True)[:500]
            # Sanitize preview text to ensure no sensitive tokens or environment data
            clean_preview = re.sub(r"[\n\r\t]+", " ", text_preview)
            logger.info(
                "[%s Diagnostic] 0 links extracted. Page title: '%s' | Body Preview: '%s'",
                backend_name, page_title, clean_preview
            )
        except Exception:
            pass

search_service = SearchService()
