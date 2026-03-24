"""Web search and URL content fetching utilities"""
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

import httpx

logger = logging.getLogger(__name__)

MAX_AUTO_INGEST_URLS = 3
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)

WEB_SEARCH_KEYWORDS = [
    "research", "найди в интернете", "ищи", "поищи", "search",
    "գտир", "փнтrir", "փнтrel", "qорqнир", "qорqел"
]

_STOP_WORDS = [
    "barev", "բарев", "привет", "hello", "hi", "salam",
    "vonc es", "inch ka", "mersi", "shnorhakalutyun"
]


async def brave_web_search(query: str) -> Optional[List[dict]]:
    """Search the web using Brave Search API.
    Returns list of {"title": str, "url": str, "description": str}
    """
    brave_api_key = os.environ.get('BRAVE_API_KEY', '')
    if not brave_api_key:
        logger.warning("BRAVE_API_KEY not set, skipping web search")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": brave_api_key, "Accept": "application/json"},
                params={"q": query, "count": 5, "search_lang": "en"}
            )
            if response.status_code != 200:
                logger.error(f"Brave Search API error: {response.status_code}")
                return None

            data = response.json()
            web_results = data.get("web", {}).get("results", [])
            if not web_results:
                return None

            results = [
                {
                    "title": r.get("title", "Untitled"),
                    "url": r.get("url", ""),
                    "description": r.get("description", "")
                }
                for r in web_results[:5]
            ]
            logger.info(f"Brave Search returned {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"Brave Search error: {str(e)}")
        return None


async def fetch_page_texts(
    results: list,
    top_n: int = 2,
    per_page: int = 500,
    total_limit: int = 1000
) -> list:
    """Fetch actual page content for top-N Brave results. Never raises."""
    enriched = []
    total_chars = 0

    try:
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for result in results[:top_n]:
                if total_chars >= total_limit:
                    break
                url = result.get("url", "")
                if not url:
                    enriched.append(result)
                    continue
                try:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; PlanetBot/1.0)"},
                    )
                    if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                            tag.decompose()
                        text = " ".join(soup.get_text(separator=" ", strip=True).split())[:per_page]
                        total_chars += len(text)
                        enriched.append({**result, "page_text": text})
                    else:
                        enriched.append(result)
                except Exception:
                    enriched.append(result)

        for result in results[len(enriched):]:
            enriched.append(result)

    except Exception as e:
        logger.warning(f"Page fetch enrichment failed: {e}")
        return results

    return enriched


def should_use_web_search(user_message: str, has_relevant_rag: bool) -> bool:
    """Determine if web search should be triggered.
    - Explicit research keywords → always yes
    - Short/greeting messages → always no
    - RAG has relevant results → no
    """
    content = user_message.strip()
    message_lower = content.lower()

    if len(content.split()) <= 4:
        return False

    if any(word in message_lower for word in _STOP_WORDS):
        return False

    for keyword in WEB_SEARCH_KEYWORDS:
        if keyword in message_lower:
            return True

    return False


async def fetch_url_content(url: str) -> Optional[str]:
    """Fetch and extract text from URL (HTML or PDF). Returns max 8000 chars or None."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            if response.status_code != 200:
                logger.warning(f"URL fetch failed: {url} - status {response.status_code}")
                return None

            content_type = response.headers.get('content-type', '').lower()
            extracted_text = ""

            if url.endswith('.pdf') or 'application/pdf' in content_type:
                try:
                    from pypdf import PdfReader
                    from io import BytesIO
                    pdf_reader = PdfReader(BytesIO(response.content))
                    extracted_text = '\n\n'.join(
                        page.extract_text() for page in pdf_reader.pages[:10]
                    )
                    logger.info(f"Extracted {len(extracted_text)} chars from PDF: {url}")
                except Exception as pdf_error:
                    logger.error(f"PDF extraction failed for {url}: {str(pdf_error)}")
                    return None
            else:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    text_parts = []
                    if soup.title:
                        text_parts.append(f"Title: {soup.title.string}")
                    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'article', 'main']):
                        text = tag.get_text(strip=True)
                        if text and len(text) > 20:
                            text_parts.append(text)
                    extracted_text = '\n\n'.join(text_parts)
                    logger.info(f"Extracted {len(extracted_text)} chars from HTML: {url}")
                except Exception as html_error:
                    logger.error(f"HTML extraction failed for {url}: {str(html_error)}")
                    return None

            return extracted_text[:8000] if extracted_text else None

    except Exception as e:
        logger.error(f"URL fetch error for {url}: {str(e)}")
        return None


def extract_urls_from_text(text: str) -> List[str]:
    """Extract unique URLs from text (max 3)."""
    urls = URL_PATTERN.findall(text)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;:!?)]}"\'')
        if url and url not in cleaned:
            cleaned.append(url)
    return cleaned[:MAX_AUTO_INGEST_URLS]


async def auto_ingest_url(db, url: str, project_id: str) -> Optional[dict]:
    """Auto-ingest a URL: fetch, extract text, chunk, and store as a source."""
    from services.file_processor import chunk_text, extract_text_from_html

    try:
        existing = await db.sources.find_one({"url": url, "projectId": project_id})
        if existing:
            return existing

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as http_client:
            response = await http_client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            return None

        extracted_text = extract_text_from_html(response.text)
        if not extracted_text or len(extracted_text.strip()) < 10:
            return None

        source_id = str(uuid.uuid4())
        chunks = chunk_text(extracted_text)

        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        display_name = f"{parsed_url.netloc}{parsed_url.path[:50]}"

        source_doc = {
            "id": source_id,
            "projectId": project_id,
            "kind": "url",
            "originalName": display_name,
            "url": url,
            "mimeType": "text/html",
            "sizeBytes": len(response.text.encode('utf-8')),
            "storagePath": None,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.sources.insert_one(source_doc)

        for i, chunk_content in enumerate(chunks):
            await db.source_chunks.insert_one({
                "id": str(uuid.uuid4()),
                "sourceId": source_id,
                "projectId": project_id,
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": datetime.now(timezone.utc).isoformat()
            })

        return source_doc

    except Exception as e:
        logger.error(f"Error auto-ingesting URL {url}: {str(e)}")
        return None
