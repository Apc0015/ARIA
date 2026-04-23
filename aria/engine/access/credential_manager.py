"""Credential management for authenticated platform access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class CredentialManager:
    """Loads, stores, and provides access to platform credentials.

    Credentials are stored as a JSON file with platform names as keys.
    Each platform entry is a dict with provider-specific fields.
    """

    def __init__(self, credentials_file: Optional[Path] = None) -> None:
        self._credentials: dict[str, Any] = {}
        self._file: Optional[Path] = None

        if credentials_file:
            self._file = Path(credentials_file)
            self._load(self._file)

    def _load(self, path: Path) -> None:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                # Support both {"platforms": {...}} wrapper and flat dict
                self._credentials = data.get("platforms", data) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError):
                self._credentials = {}

    @property
    def credentials(self) -> dict[str, Any]:
        """Return the full credentials dict."""
        return self._credentials

    @credentials.setter
    def credentials(self, value: dict[str, Any]) -> None:
        """Replace the full credentials dict."""
        self._credentials = value

    def has(self, platform: str) -> bool:
        """Return True if credentials exist for the given platform."""
        return platform in self._credentials

    def get(self, platform: str) -> dict:
        """Return credentials for a specific platform.

        Args:
            platform: Platform name (e.g., 'twitter', 'openai').

        Returns:
            Credential dict for the platform, or empty dict if not found.
        """
        return self._credentials.get(platform, {})

    def set(self, platform: str, data: dict) -> None:
        """Set credentials for a platform.

        Args:
            platform: Platform name.
            data: Credential data dict.
        """
        self._credentials[platform] = data

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist credentials to disk.

        Args:
            path: Override file path. Uses the path from __init__ if None.

        Returns:
            Path to the saved credentials file.

        Raises:
            ValueError: If no path is available.
        """
        target = path or self._file
        if not target:
            raise ValueError("No credentials file path configured.")

        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        with target.open("w", encoding="utf-8") as f:
            json.dump({"platforms": self._credentials}, f, indent=2, ensure_ascii=False)

        self._file = target
        return target
