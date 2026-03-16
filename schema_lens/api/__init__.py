"""API service mode for SolrGuard."""

from schema_lens.api.app import create_api_app
from schema_lens.api.config import ApiConfig

__all__ = ["create_api_app", "ApiConfig"]
