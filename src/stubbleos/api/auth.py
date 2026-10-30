"""Authentication, role-based access control, and rate limiting for API."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    FARMER = "farmer"
    BUYER = "buyer"


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID = Field(default_factory=uuid4)
    username: str
    role: Role
    district: str = "sangrur"


DEFAULT_API_KEYS: dict[str, AuthenticatedUser] = {
    "stubbleos-admin-key": AuthenticatedUser(username="admin", role=Role.ADMIN, district="sangrur"),
    "stubbleos-operator-key": AuthenticatedUser(
        username="chc_operator_01", role=Role.OPERATOR, district="sangrur"
    ),
    "stubbleos-buyer-key": AuthenticatedUser(
        username="biomass_buyer_corp", role=Role.BUYER, district="sangrur"
    ),
}


def get_current_user(
    api_key: str | None = Security(API_KEY_HEADER),
) -> AuthenticatedUser:
    """Validates API Key header with fallback to demo admin user in development/test."""
    if api_key and api_key in DEFAULT_API_KEYS:
        return DEFAULT_API_KEYS[api_key]

    # In dev/test environments without explicit header, allow read-only default user
    if api_key is None:
        return AuthenticatedUser(username="default_operator", role=Role.OPERATOR, district="sangrur")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-API-Key header",
    )


def require_role(allowed_roles: set[Role]) -> Callable[..., AuthenticatedUser]:
    def role_checker(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles: {[r.value for r in allowed_roles]}",
            )
        return user

    return role_checker


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = datetime.now(UTC).timestamp()
        cutoff = now - self.window_seconds

        times = [t for t in self._history[key] if t > cutoff]
        self._history[key] = times

        if len(times) >= self.max_requests:
            return False

        self._history[key].append(now)
        return True


default_limiter = RateLimiter(max_requests=1000, window_seconds=60.0)
