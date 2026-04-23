"""Output validation helpers."""

from __future__ import annotations

from typing import Any


class QualityValidator:
    """Validate cleaned records against required schema keys."""

    def validate(self, document: dict[str, Any], required_keys: list[str]) -> dict[str, Any]:
        missing = [key for key in required_keys if key not in document]
        return {"valid": not missing, "missing_keys": missing}
