"""Pluggable API auth, RBAC, and audit helpers."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, Request

from schema_lens.util.io import ensure_dir
from schema_lens.util.time import utc_now_iso


@dataclass(frozen=True)
class ApiIdentity:
    principal: str
    roles: tuple[str, ...] = ()
    authenticated: bool = False
    attributes: dict[str, str] = field(default_factory=dict)


class ApiAuthProvider(Protocol):
    def authenticate(self, request: Request) -> ApiIdentity:
        """Return identity for this request or raise HTTPException."""


class NoAuthProvider:
    def authenticate(self, request: Request) -> ApiIdentity:
        return ApiIdentity(principal="anonymous", authenticated=False)


class HeaderTokenAuthProvider:
    """Simple bearer-like auth provider for local enterprise gateways."""

    def __init__(
        self,
        *,
        token_map: dict[str, ApiIdentity],
        header_name: str = "x-solrguard-token",
        legacy_header_name: str = "x-schema-lens-token",
    ) -> None:
        self.token_map = token_map
        self.header_name = header_name.lower()
        self.legacy_header_name = legacy_header_name.lower()

    def authenticate(self, request: Request) -> ApiIdentity:
        token = request.headers.get(self.header_name) or request.headers.get(self.legacy_header_name)
        if not token:
            raise HTTPException(status_code=401, detail=f"missing auth header: {self.header_name}")
        identity = self.token_map.get(token)
        if identity is None:
            raise HTTPException(status_code=403, detail="invalid credentials")
        return identity


class ApiRbacPolicy(Protocol):
    def authorize(self, request: Request, identity: ApiIdentity) -> bool:
        """Return True if identity can access request."""


class AllowAllRbacPolicy:
    def authorize(self, request: Request, identity: ApiIdentity) -> bool:
        return True


class RoleBasedRbacPolicy:
    """
    Route-prefix role policy.

    rules format:
      {
        "GET /runs": ["viewer", "operator"],
        "POST /runs": ["operator"],
      }
    """

    def __init__(self, rules: dict[str, list[str]]) -> None:
        self.rules: dict[tuple[str, str], set[str]] = {}
        for rule_key, roles in rules.items():
            if " " not in rule_key:
                continue
            method, prefix = rule_key.split(" ", 1)
            self.rules[(method.strip().upper(), prefix.strip())] = set(roles)

    def authorize(self, request: Request, identity: ApiIdentity) -> bool:
        method = request.method.upper()
        path = request.url.path
        for (rule_method, prefix), required_roles in self.rules.items():
            if rule_method != method:
                continue
            if not path.startswith(prefix):
                continue
            if not required_roles:
                return True
            return bool(set(identity.roles).intersection(required_roles))
        return True


class ApiAuditLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path.resolve()
        ensure_dir(self.log_path.parent)
        self._lock = threading.Lock()

    def log(
        self,
        *,
        request: Request,
        status_code: int,
        identity: ApiIdentity,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        entry = {
            "timestamp": utc_now_iso(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "outcome": outcome,
            "principal": identity.principal,
            "authenticated": identity.authenticated,
            "roles": list(identity.roles),
            "client": request.client.host if request.client else "",
        }
        if detail:
            entry["detail"] = detail
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
