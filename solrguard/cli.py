"""SolrGuard CLI shim module.

This forwards to the canonical Typer app in `schema_lens.cli`.
"""

from schema_lens.cli import app, main

__all__ = ["app", "main"]
