"""Reddit collector — searches Reddit via Rube MCP."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import RedditConfig, KeywordsConfig
from opportunity_matrix.rube_client import RubeClient
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    def __init__(
        self,
        config: RedditConfig,
        keywords: KeywordsConfig,
        rube: RubeClient | None = None,
        # Keep old params for backwards compat but unused
        client_id: str = "",
        client_secret: str = "",
        username: str = "",
        password: str = "",
    ):
        self.config = config
        self.keywords = keywords
        self.rube = rube

    async def collect(self) -> list[Signal]:
        if not self.rube or not self.rube.token:
            logger.warning("Rube not configured, skipping Reddit collection")
            return []

        signals: list[Signal] = []
        try:
            all_kw = self.keywords.all_keywords
            # Build search queries from keywords, or use subreddit names
            queries = []
            if all_kw:
                # Search across Reddit using keywords in batches
                for i in range(0, len(all_kw), 3):
                    batch = all_kw[i:i + 3]
                    queries.append(" OR ".join(batch))
            else:
                # If no keywords, search by subreddit names as topics
                for sub in self.config.subreddits:
                    queries.append(f"subreddit:{sub}")

            for query in queries:
                tools = [{
                    "tool_slug": "REDDIT_SEARCH_ACROSS_SUBREDDITS",
                    "arguments": {
                        "search_query": query,
                        "limit": min(self.config.max_results_per_sub, 100),
                        "restrict_sr": True,
                        "sort": "new",
                    },
                }]
                results = await self.rube.execute_tools(tools)
                parsed = self._parse_results(results)
                signals.extend(parsed)
        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")
        return signals

    def _parse_results(self, results: list) -> list[Signal]:
        """Parse Rube REDDIT_SEARCH response into Signal objects."""
        signals: list[Signal] = []
        if not results:
            return signals

        # Navigate the Rube response structure
        # results may be a list of tool execution results
        for result in results:
            data = result if isinstance(result, dict) else {}

            # The response might be nested under 'response' or 'data'
            response_data = data.get("response", data).get("data", data)

            # Reddit search returns children array
            children = response_data.get("data", {}).get("children", [])
            if not children:
                # Try flat items list
                children = response_data.get("items", [])

            for child in children:
                post = child.get("data", child)
                title = post.get("title", "")
                body = post.get("selftext", "")

                # Keyword filter
                content = f"{title} {body}".lower()
                all_keywords = self.keywords.all_keywords
                if all_keywords and not any(kw.lower() in content for kw in all_keywords):
                    continue

                created_utc = post.get("created_utc", 0)
                if isinstance(created_utc, (int, float)) and created_utc > 0:
                    created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                else:
                    created_at = datetime.now(timezone.utc)

                signals.append(Signal(
                    platform=Platform.REDDIT,
                    platform_id=str(post.get("id", "")),
                    title=title,
                    body=body,
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    author=post.get("author", ""),
                    upvotes=post.get("ups", 0),
                    comments_count=post.get("num_comments", 0),
                    created_at=created_at,
                    raw_json=str(post),
                    metadata={"subreddit": post.get("subreddit", "")},
                ))
        return signals

    async def health_check(self) -> bool:
        if not self.rube:
            return False
        return await self.rube.health_check()
