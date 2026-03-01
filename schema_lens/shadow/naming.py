"""Shadow collection naming."""

from __future__ import annotations

from schema_lens.util.time import ts_slug


def render_shadow_name(template: str, collection: str) -> str:
    return template.format(collection=collection, ts=ts_slug())
