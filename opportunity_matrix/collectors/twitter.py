"""Twitter collector — stub (blocked on API enrollment).

This collector is disabled by default. When enabled, it would use Rube MCP's
TWITTER_RECENT_SEARCH tool. Currently returns empty results because the
Twitter Developer App has a 'client-not-enrolled' error that needs to be
resolved in the Twitter Developer Portal.
"""

from __future__ import annotations

import logging

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import TwitterConfig, KeywordsConfig
from opportunity_matrix.storage.models import Signal

logger = logging.getLogger(__name__)


class TwitterCollector(BaseCollector):
    def __init__(
        self,
        config: TwitterConfig,
        keywords: KeywordsConfig,
        rube_token: str = "",
    ):
        self.config = config
        self.keywords = keywords
        self.rube_token = rube_token

    async def collect(self) -> list[Signal]:
        if not self.config.enabled:
            logger.info("Twitter collector disabled in config")
            return []

        if not self.rube_token:
            logger.warning("Twitter collector enabled but no RUBE_TOKEN configured")
            return []

        # TODO: Implement Rube MCP TWITTER_RECENT_SEARCH call
        # when client-not-enrolled error is resolved
        logger.info("Twitter collector: Rube MCP integration not yet implemented")
        return []

    async def health_check(self) -> bool:
        if not self.config.enabled:
            return False
        if not self.rube_token:
            return False
        # TODO: Check Rube MCP connectivity
        return False
