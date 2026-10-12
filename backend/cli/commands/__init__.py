"""CLI Commands package."""

from .compare import app as compare_app
from .schema import app as schema_app
from .analytics import app as analytics_app

__all__ = [
    "compare_app",
    "schema_app",
    "analytics_app",
]