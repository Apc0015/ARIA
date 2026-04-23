"""Authenticated access layer."""

from aria.access.credentials import CredentialManager
from aria.access.paywall import PaywallResolver
from aria.access.registry import PLATFORM_REGISTRY, get_handler_class
from aria.access.sessions import SessionManager

__all__ = ["CredentialManager", "PaywallResolver", "PLATFORM_REGISTRY", "SessionManager", "get_handler_class"]
