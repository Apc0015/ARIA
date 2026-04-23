"""Abstract base class for authenticated platform handlers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("aria")


class BasePlatformHandler(ABC):
    """Abstract base for platform-specific authenticated fetch handlers."""

    def __init__(self) -> None:
        self._authenticated = False
        self._session_data: dict = {}

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Authenticate with the platform using the provided credentials.

        Args:
            credentials: Platform-specific credential dict.

        Returns:
            True if authentication succeeded.
        """
        ...

    @abstractmethod
    async def fetch(self, url: str) -> Optional[str]:
        """Fetch the content at the given URL using the authenticated session.

        Args:
            url: URL to fetch.

        Returns:
            Page/document content as a string, or None if unavailable.
        """
        ...

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated
