"""Reddit collector — OAuth2 + subreddit scraping with keyword filtering."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import RedditConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)

REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"


class RedditCollector(BaseCollector):
    def __init__(
        self,
        config: RedditConfig,
        keywords: KeywordsConfig,
        client_id: str = "",
        client_secret: str = "",
        username: str = "",
        password: str = "",
    ):
        self.config = config
        self.keywords = keywords
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password

    async def _get_access_token(self, client: httpx.AsyncClient) -> str | None:
        try:
            resp = await client.post(
                REDDIT_AUTH_URL,
                auth=(self.client_id, self.client_secret),
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                },
                headers={"User-Agent": "OpportunityMatrix/0.1"},
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            logger.error(f"Reddit auth failed: {e}")
            return None

    async def collect(self) -> list[Signal]:
        signals: list[Signal] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                token = await self._get_access_token(client)
                if not token:
                    return []

                headers = {
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "OpportunityMatrix/0.1",
                }

                for subreddit in self.config.subreddits:
                    sub_signals = await self._collect_subreddit(client, headers, subreddit)
                    signals.extend(sub_signals)
        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")
        return signals

    async def _collect_subreddit(
        self, client: httpx.AsyncClient, headers: dict, subreddit: str
    ) -> list[Signal]:
        try:
            resp = await client.get(
                f"{REDDIT_API_BASE}/r/{subreddit}/new",
                headers=headers,
                params={"limit": self.config.max_results_per_sub},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Reddit r/{subreddit} failed: {e}")
            return []

        signals: list[Signal] = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            body = post.get("selftext", "")
            content = f"{title} {body}".lower()

            all_keywords = self.keywords.all_keywords
            if all_keywords and not any(kw.lower() in content for kw in all_keywords):
                continue

            signals.append(Signal(
                platform=Platform.REDDIT,
                platform_id=post.get("id", ""),
                title=title,
                body=body,
                url=f"https://reddit.com{post.get('permalink', '')}",
                author=post.get("author", ""),
                upvotes=post.get("ups", 0),
                comments_count=post.get("num_comments", 0),
                created_at=datetime.fromtimestamp(
                    post.get("created_utc", 0), tz=timezone.utc
                ),
                raw_json=str(post),
                metadata={"subreddit": post.get("subreddit", subreddit)},
            ))
        return signals

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = await self._get_access_token(client)
                return token is not None
        except Exception:
            return False
