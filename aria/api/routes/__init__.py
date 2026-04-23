"""API route modules."""

from aria.api.routes.health import router as health_router
from aria.api.routes.runs import router as runs_router
from aria.api.routes.exports import router as exports_router
from aria.api.routes.credentials import router as credentials_router
from aria.api.routes.missions import router as missions_router
from aria.api.routes.flutter import router as flutter_router
from aria.api.routes.studio import router as studio_router
from aria.api.routes.domains import router as domains_router
from aria.api.routes.chat import router as chat_router

__all__ = [
    "health_router",
    "runs_router",
    "exports_router",
    "credentials_router",
    "missions_router",
    "flutter_router",
    "studio_router",
    "domains_router",
    "chat_router",
]
