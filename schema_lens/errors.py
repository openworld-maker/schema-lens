"""Custom exceptions for SolrGuard."""


class SchemaLensError(Exception):
    """Base exception."""


class ValidationError(SchemaLensError):
    """Raised when configuration or inputs are invalid."""


class SolrRequestError(SchemaLensError):
    """Raised when Solr HTTP interactions fail."""


class StageError(SchemaLensError):
    """Raised when pipeline stage fails."""
