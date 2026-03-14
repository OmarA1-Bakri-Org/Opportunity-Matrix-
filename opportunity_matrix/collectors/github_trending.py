"""GitHub collector — searches repos via Rube MCP."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import GitHubConfig, KeywordsConfig
from opportunity_matrix.rube_client import RubeClient
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    def __init__(
        self,
        config: GitHubConfig,
        keywords: KeywordsConfig,
        rube: RubeClient | None = None,
        token: str = "",  # kept for backwards compat
    ):
        self.config = config
        self.keywords = keywords
        self.rube = rube

    async def collect(self) -> list[Signal]:
        if not self.rube or not self.rube.token:
            logger.warning("Rube not configured, skipping GitHub collection")
            return []

        signals: list[Signal] = []
        seen_ids: set[str] = set()
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
            for lang in self.config.languages:
                lang_signals = await self._search_language(lang, since)
                for sig in lang_signals:
                    if sig.platform_id not in seen_ids:
                        seen_ids.add(sig.platform_id)
                        signals.append(sig)
        except Exception as e:
            logger.error(f"GitHub collection failed: {e}")
        return signals

    async def _search_language(self, language: str, since: str) -> list[Signal]:
        query = f"language:{language} stars:>={self.config.min_stars} created:>={since}"

        # Cap per_page at 5 to avoid Rube data_preview truncation.
        # Rube returns full item dicts only when the response payload is
        # small enough; above ~5 items it switches to data_preview which
        # truncates both the array and each item's fields.
        tools = [{
            "tool_slug": "GITHUB_FIND_REPOSITORIES",
            "arguments": {
                "query": query,
                "per_page": min(self.config.max_results, 5),
                "sort": "stars",
                "order": "desc",
            },
        }]

        try:
            results = await self.rube.execute_tools(tools)
            return self._parse_results(results)
        except Exception as e:
            logger.error(f"GitHub search for {language} failed: {e}")
            return []

    def _parse_results(self, results: list) -> list[Signal]:
        """Parse Rube GITHUB_FIND_REPOSITORIES response into Signal objects.

        Each item in *results* is a per-tool result dict from Rube:
            {response: {successful: bool, data: {items: [...]}}, tool_slug: str, ...}
        """
        signals: list[Signal] = []
        if not results:
            return signals

        for result in results:
            data = result if isinstance(result, dict) else {}
            resp = data.get("response", data)

            # Rube wraps GitHub data under 'data' or 'data_preview'
            inner = resp.get("data", resp.get("data_preview", resp))

            items = []
            if isinstance(inner, dict):
                items = inner.get("items", [])
                if not items:
                    items = inner.get("repositories", [])

            for repo in items:
                # Skip truncation markers like "...98 more items"
                if not isinstance(repo, dict):
                    continue
                name = repo.get("full_name", "")
                description = repo.get("description", "") or ""

                created_str = repo.get("created_at", "2026-01-01T00:00:00Z")
                try:
                    created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    created_at = datetime.now(timezone.utc)

                signals.append(Signal(
                    platform=Platform.GITHUB,
                    platform_id=str(repo.get("id", "")),
                    title=name,
                    body=description,
                    url=repo.get("html_url", ""),
                    author=repo.get("owner", {}).get("login", ""),
                    upvotes=repo.get("stargazers_count", 0),
                    comments_count=repo.get("open_issues_count", 0),
                    created_at=created_at,
                    raw_json=str(repo),
                    metadata={
                        "language": repo.get("language", ""),
                        "forks": repo.get("forks_count", 0),
                        "topics": repo.get("topics", []),
                    },
                ))
        return signals

    async def health_check(self) -> bool:
        if not self.rube:
            return False
        return await self.rube.health_check()
