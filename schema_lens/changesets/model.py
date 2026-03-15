"""Changeset model abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Changeset:
    raw: dict[str, Any]
    path: Path | None = None

    @property
    def version(self) -> int:
        return int(self.raw.get("schema_lens_version", 1))

    @property
    def baseline(self) -> dict[str, Any]:
        return self.raw.get("baseline", {})

    @property
    def shadow(self) -> dict[str, Any]:
        return self.raw.get("shadow", {})

    @property
    def data(self) -> dict[str, Any]:
        return self.raw.get("data", {})

    @property
    def queries(self) -> dict[str, Any]:
        return self.raw.get("queries", {})

    @property
    def changes(self) -> list[dict[str, Any]]:
        return self.raw.get("changes", [])

    @property
    def evaluation(self) -> dict[str, Any]:
        return self.raw.get("evaluation", {})

    @property
    def replay(self) -> dict[str, Any]:
        return self.raw.get("replay", {})

    @property
    def vector(self) -> dict[str, Any]:
        return self.raw.get("vector", {})
