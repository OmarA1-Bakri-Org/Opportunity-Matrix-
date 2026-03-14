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
                # Cap limit at 5 to avoid Rube data_preview truncation.
                # Rube returns full post dicts only when the response
                # payload is small; above ~5 items it switches to
                # data_preview which truncates both the list and each
                # item's fields.
                tools = [{
                    "tool_slug": "REDDIT_SEARCH_ACROSS_SUBREDDITS",
                    "arguments": {
                        "search_query": query,
                        "limit": min(self.config.max_results_per_sub, 5),
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
        """Parse Rube REDDIT_SEARCH response into Signal objects.

        Each item in *results* is a per-tool result dict from Rube:
            {response: {successful: bool, data_preview: {posts: [...]}}, tool_slug: str, ...}
        """
        signals: list[Signal] = []
        if not results:
            return signals

        for result in results:
            data = result if isinstance(result, dict) else {}
            resp = data.get("response", data)

            # Rube wraps Reddit data in 'data_preview' or 'data'
            preview = resp.get("data_preview", resp.get("data", {}))
            posts = []
            if isinstance(preview, dict):
                posts = preview.get("posts", [])
                # Fallback: raw Reddit structure with children
                if not posts:
                    posts = preview.get("children", [])
                # Fallback: items list
                if not posts:
                    posts = preview.get("items", [])

            for child in posts:
                # Skip truncation markers like "...8 more items"
                if not isinstance(child, dict):
                    continue
                post = child.get("data", child)
                title = post.get("title", "")
                body = post.get("selftext", "")

                # No redundant keyword re-filter: the Rube search query
                # already contains keyword terms, so returned posts are
                # relevance-matched by Reddit.  Re-filtering with exact
                # substring match would drop most results.

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
                    upvotes=post.get("score", post.get("ups", 0)),
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
