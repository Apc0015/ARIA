"""Authenticated platform handlers."""

from aria.access.platforms.acm import ACMHandler
from aria.access.platforms.base import BasePlatformHandler
from aria.access.platforms.elsevier import ElsevierHandler
from aria.access.platforms.ieee import IEEEHandler
from aria.access.platforms.jstor import JSTORHandler
from aria.access.platforms.springer import SpringerHandler
from aria.access.platforms.university_proxy import UniversityProxyHandler
from aria.access.platforms.web_of_science import WebOfScienceHandler

__all__ = [
    "ACMHandler",
    "BasePlatformHandler",
    "ElsevierHandler",
    "IEEEHandler",
    "JSTORHandler",
    "SpringerHandler",
    "UniversityProxyHandler",
    "WebOfScienceHandler",
]
