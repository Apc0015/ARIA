from __future__ import annotations

from aria.access.platforms.web_of_science import WebOfScienceHandler


def test_web_of_science_handler_metadata():
    assert WebOfScienceHandler.platform_key == "web_of_science"
    assert "clarivate" in WebOfScienceHandler.base_url
