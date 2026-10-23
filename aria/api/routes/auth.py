"""Browser session endpoints for the managed ARIA SaaS deployment."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, Response

from aria.api.authorization import current_user

router = APIRouter()
_COOKIE = "aria_session"


@router.post("/api/auth/login")
async def login(payload: dict, request: Request, response: Response) -> dict:
    email = str(payload.get("email", ""))
    password = str(payload.get("password", ""))
    user = request.app.state.tenant_store.authenticate(email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = request.app.state.tenant_store.create_session(user["id"])
    request.app.state.tenant_store.audit(user["tenant_id"], user["id"], "auth.login")
    secure_cookie = os.getenv("ARIA_COOKIE_SECURE", "true").lower() in {"true", "1", "yes"}
    response.set_cookie(_COOKIE, token, httponly=True, secure=secure_cookie, samesite="lax", max_age=43_200, path="/")
    return {"user": {"email": user["email"], "role": user["role"]}, "tenant_id": user["tenant_id"]}


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(_COOKIE)
    if token:
        user = getattr(request.state, "user", None)
        if user:
            request.app.state.tenant_store.audit(user["tenant_id"], user["id"], "auth.logout")
        request.app.state.tenant_store.delete_session(token)
    response.delete_cookie(_COOKIE, path="/")
    return {"status": "logged_out"}


@router.post("/api/auth/password")
async def change_password(payload: dict, request: Request, response: Response) -> dict:
    """Change the authenticated user's password and revoke active sessions."""
    user = current_user(request)
    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    try:
        changed = request.app.state.tenant_store.change_password(
            user["id"], current_password, new_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    request.app.state.tenant_store.delete_user_sessions(user["id"])
    request.app.state.tenant_store.audit(user["tenant_id"], user["id"], "auth.password_changed")
    response.delete_cookie(_COOKIE, path="/")
    return {"status": "password_changed"}


@router.get("/api/auth/me")
async def me(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"user": user}
