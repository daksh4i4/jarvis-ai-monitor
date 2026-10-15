import httpx, feedparser
from datetime import datetime, timezone
from .config import NEWS_RSS_URLS

async def fetch_news():
    items = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in NEWS_RSS_URLS:
            try:
                response = await client.get(url)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                source = feed.feed.get("title", url)
                for entry in feed.entries[:25]:
                    items.append({
                      "published_at": entry.get("published", entry.get("updated", datetime.now(timezone.utc).isoformat())),
                      "title": entry.get("title", "Untitled"), "link": entry.get("link", url),
                      "source": source, "summary": entry.get("summary", "")[:1000]})
            except Exception as e:
                items.append({"published_at": datetime.now(timezone.utc).isoformat(),
                  "title": "RSS fetch failed", "link": url, "source": "JARVIS", "summary": type(e).__name__})
    return items
