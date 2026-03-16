"""API route modules."""

from schema_lens.api.routes.artifacts import router as artifacts_router
from schema_lens.api.routes.capabilities import router as capabilities_router
from schema_lens.api.routes.compare_env import router as compare_env_router
from schema_lens.api.routes.gates import router as gates_router
from schema_lens.api.routes.health import router as health_router
from schema_lens.api.routes.runs import router as runs_router

__all__ = [
    "artifacts_router",
    "capabilities_router",
    "compare_env_router",
    "gates_router",
    "health_router",
    "runs_router",
]
