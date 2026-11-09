from typing import Literal
from fastapi import Header, HTTPException, status
from backend.config import settings

RoleType = Literal["viewer", "analyst", "admin"]


def resolve_role(x_api_key: str | None = Header(default=None), x_role: str | None = Header(default=None)) -> RoleType:
    if x_api_key:
        if x_api_key == settings.admin_api_key:
            return "admin"
        if x_api_key == settings.analyst_api_key:
            return "analyst"
        if x_api_key == settings.viewer_api_key:
            return "viewer"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    if x_role in ("viewer", "analyst", "admin"):
        return x_role  # type: ignore[return-value]
    return "viewer"


def require_analyst_or_admin(
    x_api_key: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> RoleType:
    role = resolve_role(x_api_key=x_api_key, x_role=x_role)
    if role not in ("analyst", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires 'analyst' or 'admin' privileges.",
        )
    return role


def require_admin(
    x_api_key: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
) -> RoleType:
    role = resolve_role(x_api_key=x_api_key, x_role=x_role)
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Metric registry mutations and approvals require 'admin' privileges.",
        )
    return role

