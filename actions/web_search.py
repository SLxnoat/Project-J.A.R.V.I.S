# web_search.py
# Hybrid Omni-Search & Playwright Stealth Deep Scraper with ChromaDB RAG Integration
# Replaces old OpenRouter LLM-based search with Serper API + async deep scraping
# Uses .env configuration with python-dotenv support

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Union

import requests

# python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
    load_dotenv()  # Load .env from project root
except ImportError:
    HAS_DOTENV = False

# Try to import playwright_stealth for bypassing anti-bot protections
try:
    import playwright_stealth
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

# Try to import playwright async API
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

BASE_DIR: Path = Path(__file__).resolve().parent.parent
API_CONFIG_PATH: Path = BASE_DIR / "config" / "api_keys.json"
SERPER_API_URL: str = "https://google.serper.dev/search"


def _get_env_api_key(key_name: str) -> str | None:
    """
    Load API key from environment variable with fallback to JSON config.
    Prioritizes .env file, then os.environ, then api_keys.json.
    """
    # First try environment variable (from .env or system)
    value = os.getenv(key_name)
    if value:
        return value

    # Fallback to JSON config if .env not available
    if API_CONFIG_PATH.exists():
        try:
            data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            key_map = {
                "gemini_api_key": "GEMINI_API_KEY",
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "serper_api_key": "SERPER_API_KEY",
            }
            if key_name in key_map:
                return data.get(key_map[key_name])
            return data.get(key_name.lower())
        except Exception as exc:
            print(f"[WebSearch] ⚠️ Failed to load API key from JSON: {exc}")  # Jarvis: JSON fallback failed
    return None


def _get_serper_api_key() -> str:
    """Load Serper API key from environment, or fallback to JSON."""
    return _get_env_api_key("SERPER_API_KEY") or ""


def _serper_search(query: str, max_results: int = 3) -> list[dict]:
    """
    Query the Serper API for search results.
    Returns top organic search result URLs and metadata.
    """
    serper_key = _get_serper_api_key()
    if not serper_key:
        # Fallback to OpenRouter if no Serper key
        try:
            from or_client import client
            result = client.chat(
                f"Search the web for: {query}",
                system="You are a web search assistant. Provide factually accurate results with sources.",
            )
            return [
                {
                    "title": "Search Result",
                    "snippet": result[:500],
                    "url": "https://example.com/search-result",
                }
            ]
        except Exception as e:
            print(f"[WebSearch] ⚠️ Serper key missing and OpenRouter failed: {e}")
            return []

    headers = {
        "X-API-KEY": serper_key,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "num": max_results,
        "gl": "us",
        "hl": "en",
    }

    try:
        response = requests.post(
            SERPER_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        organic_results = data.get("organic", [])

        results = []
        for r in organic_results[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "url": r.get("link", ""),
            })

        return results
    except requests.exceptions.RequestException as e:
        print(f"[WebSearch] ⚠️ Serper API request failed: {e}")
        return []
    except Exception as e:
        print(f"[WebSearch] ⚠️ Serper API parsing failed: {e}")
        return []


async def _scrape_page_with_stealth(
    page,
    url: str,
    title: str,
    timeout: int = 30000,
) -> tuple[str, str, str]:
    """
    Scrape a single page using Playwright with stealth mode.
    Returns (title, content, url).
    """
    try:
        # Apply playwright_stealth to bypass anti-bot protections
        if HAS_STEALTH:
            await playwright_stealth.stealth_async(page)

        # Set realistic User-Agent
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

        # Navigate with safe timeout
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout,
        )

        # Wait for any dynamic content to load
        await page.wait_for_timeout(2000)

        # Evaluate to extract clean content
        content = await page.evaluate(
            """
            () => {
                // Remove non-content elements
                const selectorsToRemove = [
                    'script',
                    'style',
                    'nav',
                    'footer',
                    'header',
                    'noscript',
                    'iframe',
                    'svg',
                    'canvas',
                    'form',
                    'button',
                    '[role="banner"]',
                    '[role="navigation"]',
                    '[class*="cookie"]',
                    '[class*="ad"]',
                    '[class*="promo"]',
                    '[class*="sidebar"]',
                    '[class*="newsletter"]',
                ];

                selectorsToRemove.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => el.remove());
                });

                // Get body innerText
                const body = document.body;
                if (!body) return '';

                let text = body.innerText || '';

                // Clean up: remove excessive whitespace, empty lines
                text = text.replace(/\\s+/g, ' ').replace(/\\n{3,}/g, '\\n\\n').trim();

                // Truncate to prevent context window issues
                if (text.length > 5000) {
                    text = text.substring(0, 5000) + '... [TRUNCATED]';
                }

                return text;
            }
            """
        )

        return (title, content, url)

    except Exception as e:
        print(f"[WebSearch] ⚠️ Failed to scrape {url}: {e}")
        # Jarvis-style error logging
        if "security" in str(e).lower() or "cloudflare" in str(e).lower():
            print(f"[WebSearch] ⚠️ Sir, I failed to bypass the security wall on {url}")
        return (title, "", url)


async def _scrape_urls_concurrently(
    urls_with_titles: list[tuple[str, str]]
) -> list[Union[tuple[str, str, str], Exception]]:
    """
    Scrape multiple URLs concurrently using Playwright with stealth.
    Returns list of (title, content, url) tuples or Exception objects for failed scrapes.
    """
    if not HAS_PLAYWRIGHT:
        print("[WebSearch] ⚠️ Playwright not installed - skipping deep scrape")
        return []

    results: list[Union[tuple[str, str, str], Exception]] = []

    try:
        async with async_playwright() as p:
            # Launch browser in headless mode
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )

            tasks = []
            for title, url in urls_with_titles:
                page = await context.new_page()
                task = _scrape_page_with_stealth(page, url, title)
                tasks.append(task)

            # Run all scrapes concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            await context.close()
            await browser.close()

        # Filter out exceptions
        results = [r for r in results if isinstance(r, tuple)]

    except Exception as e:
        print(f"[WebSearch] ⚠️ Playwright browser error: {e}")

    return results


def _clean_scraped_content(text: str) -> str:
    """Clean and normalize scraped text content."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text


async def _deep_scrape_and_store(
    search_results: list[dict],
) -> list[dict]:
    """
    Deep scrape top 3 URLs and store in ChromaDB via RAG.
    Returns enriched results with scraped content.
    """
    if not search_results:
        return []

    # Get top 3 URLs
    top_results = search_results[:3]

    # Prepare URLs for scraping (title, url tuples)
    urls_to_scrape = [(r.get("title", ""), r.get("url", "")) for r in top_results]

    # Scrape concurrently
    scraped_data = await _scrape_urls_concurrently(urls_to_scrape)

    enriched_results = []

    for (title, content, url) in scraped_data:
        # Clean content
        clean_content = _clean_scraped_content(content) if content else ""

        # Store in ChromaDB for long-term memory
        try:
            from memory.memory_manager import JarvisMemory

            memory = JarvisMemory()
            metadata = {"url": url, "title": title}

            if clean_content:
                memory.store_permanent_fact(clean_content, metadata=metadata)
                print(f"[WebSearch] ✅ Stored {url} in ChromaDB memory")

        except Exception as e:
            print(f"[WebSearch] ⚠️ Failed to store {url} in memory: {e}")

        enriched_results.append({
            "title": title,
            "snippet": clean_content[:500] if clean_content else "",  # Use scraped content as snippet
            "url": url,
            "full_content": clean_content,
        })

    return enriched_results


def _format_results_for_brain(
    query: str,
    search_results: list[dict],
    scraped_results: list[dict],
) -> str:
    """
    Format results for Gemini Brain synthesis.
    Includes titles, snippets, source URLs, and scraped content where available.
    """
    lines = [f"Search results for: {query}\n", "=" * 60]

    # Combine search and scraped results
    all_results = []
    for r in search_results:
        url = r.get("url", "")
        existing = next((x for x in scraped_results if x.get("url") == url), None)
        if existing:
            all_results.append(existing)
        else:
            all_results.append(r)

    for i, r in enumerate(all_results, 1):
        title = r.get("title", "").strip()
        snippet = r.get("snippet", "").strip()
        url = r.get("url", "").strip()

        lines.append(f"\n[{i}] {title}")
        lines.append(f"    Source: {url}")

        if snippet:
            # Truncate snippet if too long
            if len(snippet) > 800:
                snippet = snippet[:800] + "..."
            lines.append(f"    {snippet}")

    lines.append("\n" + "=" * 60)
    lines.append("Source URLs (for reference):")
    for r in all_results:
        url = r.get("url", "")
        if url:
            lines.append(f"    - {url}")

    return "\n".join(lines)


def web_search_action(parameters: dict, player=None) -> str:
    """
    Main synchronous wrapper function for web_search.
    Managed through asyncio.run() for compatibility with Jarvis's thread-safe executor.
    """
    params = parameters or {}
    query = params.get("query", "").strip()

    if not query:
        return "Please provide a search query, sir."

    if player:
        player.write_log(f"[Search] {query}")

    print(f"[WebSearch] 🔍 Query: {query!r}")

    try:
        # Step 1: Get search results from Serper API
        search_results = _serper_search(query, max_results=3)

        if not search_results:
            return f"No search results found for: {query}"

        print(f"[WebSearch] ✅ Serper API returned {len(search_results)} results")

        # Step 2: Deep scrape the top 3 URLs concurrently
        async def run_scrape():
            return await _deep_scrape_and_store(search_results)

        scraped_results = asyncio.run(run_scrape())

        # Step 3: Format results for Gemini Brain
        result = _format_results_for_brain(query, search_results, scraped_results)

        print(f"[WebSearch] ✅ Deep scraping complete - {len(scraped_results)} pages processed")
        return result

    except Exception as e:
        print(f"[WebSearch] ❌ Search failed: {e}")
        # Fallback to simple search if deep scrape fails
        return f"Search failed for '{query}', sir: {e}"


# Legacy function for compatibility
def web_search(parameters: dict, response=None, player=None, session_memory=None) -> str:
    """
    Legacy wrapper function - now delegates to web_search_action.
    """
    return web_search_action(parameters, player)


if __name__ == "__main__":
    # Test the search
    test_query = "What is the latest news in AI?"
    result = web_search_action({"query": test_query})
    print(result)
