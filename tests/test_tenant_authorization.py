"""Tenant-boundary regression tests for direct run identifiers."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from aria.api.authorization import require_run_tenant


def _request(tenant_id: str):
    return SimpleNamespace(state=SimpleNamespace(user={"id": "user", "tenant_id": tenant_id}))


def _manager(tenant_id: str):
    return SimpleNamespace(runs={"run-a": SimpleNamespace(run_id="run-a", tenant_id=tenant_id)})


def test_run_owner_can_access_its_run():
    state = require_run_tenant(_request("tenant-a"), _manager("tenant-a"), "run-a")
    assert state.run_id == "run-a"


def test_foreign_tenant_cannot_confirm_or_access_run():
    with pytest.raises(HTTPException) as error:
        require_run_tenant(_request("tenant-b"), _manager("tenant-a"), "run-a")
    assert error.value.status_code == 404


def test_unauthenticated_request_is_rejected():
    request = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as error:
        require_run_tenant(request, _manager("tenant-a"), "run-a")
    assert error.value.status_code == 401
