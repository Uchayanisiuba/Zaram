"""The code pack — reading a repository.

Parsers live in `ingest/parsers/code.py` because ingestion owns resolution by
suffix; the tools live here, and `active.py` holds the one piece of
request-scoped state they need. `docs/CODE-PACK.md` records the decisions,
including why this is a pack rather than a seventh node.
"""

from .active import active_root, set_active_root
from .tools import SERVER_ID, CodeTools, OutsideTheProject

__all__ = [
    "SERVER_ID",
    "CodeTools",
    "OutsideTheProject",
    "active_root",
    "set_active_root",
]
