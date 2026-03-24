"""Security auth models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuthMaterial:
    mode: str
    headers: dict[str, str] = field(default_factory=dict)
    cert: str | tuple[str, str] | None = None
    verify: bool | str = True
