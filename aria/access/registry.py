"""Platform registry surface with canonical ARIA naming."""

from __future__ import annotations

import importlib

from aria.engine.access.platform_registry import PLATFORM_REGISTRY as LEGACY_PLATFORM_REGISTRY


PLATFORM_REGISTRY = dict(LEGACY_PLATFORM_REGISTRY)
PLATFORM_REGISTRY.update(
    {
        "web_of_science": {
            "name": "Web of Science",
            "base_url": "https://www.webofscience.com",
            "handler": "aria.access.platforms.web_of_science.WebOfScienceHandler",
            "supports_search": True,
            "rate_limit_seconds": 4,
        },
        "university_proxy": {
            "name": "University Proxy",
            "base_url": None,
            "handler": "aria.access.platforms.university_proxy.UniversityProxyHandler",
            "supports_search": False,
            "is_proxy": True,
            "rate_limit_seconds": 2,
        },
    }
)


def get_handler_class(platform_name: str) -> type:
    """Dynamically import and return the handler class for a platform."""

    platform = PLATFORM_REGISTRY.get(platform_name)
    if not platform:
        raise ValueError(f"Unknown platform: {platform_name}")
    module_path, class_name = platform["handler"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


__all__ = ["PLATFORM_REGISTRY", "get_handler_class"]
