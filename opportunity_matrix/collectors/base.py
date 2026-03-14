"""Abstract base class for all collectors."""
from __future__ import annotations
from abc import ABC, abstractmethod
from opportunity_matrix.storage.models import Signal

class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> list[Signal]:
        """Collect signals from the platform. Returns empty list on failure."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the platform API is reachable."""
        ...
