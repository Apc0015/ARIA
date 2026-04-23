"""Pydantic schemas for the ARIA API surface."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RunFlags(BaseModel):
    """Feature flags that modify how a run is executed."""

    collect_only: bool = False
    clean_only: bool = False
    validate_credentials: bool = False
    authenticated_only: bool = False
    public_only: bool = False
    resume: bool = False


class ProviderOverride(BaseModel):
    """Override the default LLM provider for a specific run."""

    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class StartRunRequest(BaseModel):
    """Request body for starting a new collection run."""

    mission_yaml: str
    provider: Optional[ProviderOverride] = None
    flags: RunFlags = RunFlags()
    credentials: Optional[dict] = None


class ValidateMissionRequest(BaseModel):
    """Request body for validating a mission YAML."""

    mission_yaml: str


class CredentialsRequest(BaseModel):
    """Request body for updating platform credentials."""

    platforms: dict
