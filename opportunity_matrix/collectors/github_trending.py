"""GitHub collector — search API for trending repos with keyword filtering."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import httpx

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import GitHubConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubCollector(BaseCollector):
    def __init__(self, config: GitHubConfig, keywords: KeywordsConfig, token: str = ""):
        self.config = config
        self.keywords = keywords
        self.token = token

    async def collect(self) -> list[Signal]:
        if not self.token:
            logger.warning("GitHub token not configured, skipping collection")
            return []

        signals: list[Signal] = []
        seen_ids: set[str] = set()
        try:
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "OpportunityMatrix/0.1",
            }
            async with httpx.AsyncClient(timeout=30, headers=headers) as client:
                # Search for recently created repos with stars
                since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
                for lang in self.config.languages:
                    lang_signals = await self._search_language(client, lang, since)
                    for sig in lang_signals:
                        if sig.platform_id not in seen_ids:
                            seen_ids.add(sig.platform_id)
                            signals.append(sig)
        except Exception as e:
            logger.error(f"GitHub collection failed: {e}")
        return signals

    async def _search_language(
        self, client: httpx.AsyncClient, language: str, since: str
    ) -> list[Signal]:
        try:
            query = f"language:{language} stars:>={self.config.min_stars} created:>={since}"
            resp = await client.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(self.config.max_results, 100),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"GitHub search for {language} failed: {e}")
            return []

        signals: list[Signal] = []
        for repo in data.get("items", []):
            name = repo.get("full_name", "")
            description = repo.get("description", "") or ""
            content = f"{name} {description}".lower()

            all_keywords = self.keywords.all_keywords
            if all_keywords and not any(kw.lower() in content for kw in all_keywords):
                continue

            signals.append(Signal(
                platform=Platform.GITHUB,
                platform_id=str(repo.get("id", "")),
                title=repo.get("full_name", ""),
                body=description,
                url=repo.get("html_url", ""),
                author=repo.get("owner", {}).get("login", ""),
                upvotes=repo.get("stargazers_count", 0),
                comments_count=repo.get("open_issues_count", 0),
                created_at=datetime.fromisoformat(
                    repo.get("created_at", "2026-01-01T00:00:00Z").replace("Z", "+00:00")
                ),
                raw_json=str(repo),
                metadata={
                    "language": repo.get("language", ""),
                    "forks": repo.get("forks_count", 0),
                    "topics": repo.get("topics", []),
                },
            ))
        return signals

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {}
                if self.token:
                    headers["Authorization"] = f"token {self.token}"
                resp = await client.get(f"{GITHUB_API}/rate_limit", headers=headers)
                return resp.status_code == 200
        except Exception:
            return False
