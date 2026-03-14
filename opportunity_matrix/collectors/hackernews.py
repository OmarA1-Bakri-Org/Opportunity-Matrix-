"""Hacker News collector — Firebase API + keyword filtering."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
import httpx
from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import HackerNewsConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)
HN_BASE = "https://hacker-news.firebaseio.com/v0"

class HackerNewsCollector(BaseCollector):
    def __init__(self, config: HackerNewsConfig, keywords: KeywordsConfig):
        self.config = config
        self.keywords = keywords

    async def collect(self) -> list[Signal]:
        signals: list[Signal] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for feed in self.config.feeds:
                    feed_signals = await self._collect_feed(client, feed)
                    signals.extend(feed_signals)
        except Exception as e:
            logger.error(f"HN collection failed: {e}")
        return signals

    async def _collect_feed(self, client: httpx.AsyncClient, feed: str) -> list[Signal]:
        try:
            resp = await client.get(f"{HN_BASE}/{feed}.json")
            resp.raise_for_status()
            item_ids = resp.json()
        except (httpx.HTTPError, Exception) as e:
            logger.error(f"HN feed {feed} failed: {e}")
            return []
        item_ids = item_ids[: self.config.max_results]
        signals: list[Signal] = []
        for batch_start in range(0, len(item_ids), 20):
            batch = item_ids[batch_start : batch_start + 20]
            tasks = [self._fetch_item(client, item_id) for item_id in batch]
            items = await asyncio.gather(*tasks, return_exceptions=True)
            for item in items:
                if isinstance(item, Signal):
                    signals.append(item)
        return signals

    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> Signal | None:
        try:
            resp = await client.get(f"{HN_BASE}/item/{item_id}.json")
            resp.raise_for_status()
            data = resp.json()
            if not data or data.get("type") != "story":
                return None
            title = data.get("title", "")
            text = data.get("text", "")
            content = f"{title} {text}".lower()
            all_keywords = self.keywords.all_keywords
            if all_keywords and not any(kw.lower() in content for kw in all_keywords):
                return None
            return Signal(
                platform=Platform.HACKERNEWS,
                platform_id=str(data["id"]),
                title=title,
                body=text,
                url=data.get("url", f"https://news.ycombinator.com/item?id={data['id']}"),
                author=data.get("by", ""),
                upvotes=data.get("score", 0),
                comments_count=data.get("descendants", 0),
                created_at=datetime.fromtimestamp(data.get("time", 0), tz=timezone.utc),
                raw_json=str(data),
                metadata={"feed": "showstories" if "Show HN" in title else "askstories"},
            )
        except Exception as e:
            logger.warning(f"HN item {item_id} failed: {e}")
            return None

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{HN_BASE}/topstories.json")
                return resp.status_code == 200
        except Exception:
            return False
