"""Solr endpoint path helpers."""

from __future__ import annotations


def schema_path(collection: str) -> str:
    return f"{collection}/schema"


def query_path(collection: str) -> str:
    return f"{collection}/select"


def update_path(collection: str) -> str:
    return f"{collection}/update"


def collections_admin_path() -> str:
    return "admin/collections"


def configsets_admin_path() -> str:
    return "admin/configs"


def system_info_path() -> str:
    return "admin/info/system"
