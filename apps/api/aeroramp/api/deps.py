from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from aeroramp.core.permissions import has_permission
from aeroramp.core.security import decode_token
from aeroramp.db.models import OrganizationMembership, User
from aeroramp.db.session import get_db

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    user: User
    organization_id: str
    role: str


DbSession = Annotated[Session, Depends(get_db)]


def get_current_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbSession,
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    user = db.get(User, payload.get("sub"))
    organization_id = str(payload.get("org"))
    role = str(payload.get("role"))
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == role,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization membership not found")
    return AuthContext(user, organization_id, role)


CurrentContext = Annotated[AuthContext, Depends(get_current_context)]


def require_permission(permission: str):
    def dependency(context: CurrentContext) -> AuthContext:
        if not has_permission(context.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission}")
        return context

    return dependency


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
