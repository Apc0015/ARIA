"""Secret scrubbing for user-facing error messages.

Single source of truth — used by the run manager, the orchestrator, and any
API route that echoes exception text to a client.
"""

from __future__ import annotations

import re

# Patterns that indicate a secret leaked into an exception message.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),      # OpenAI / Anthropic style
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),           # GitHub PAT
    re.compile(r"[A-Za-z0-9_-]{40,}"),             # generic long opaque token
)


def scrub_secrets(message: str) -> str:
    """Replace anything that looks like a credential with [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message
