"""The code pack — reading a repository, and since 12 September changing one.

Parsers live in `ingest/parsers/code.py` because ingestion owns resolution by
suffix; the tools live here, and `active.py` holds the one piece of
request-scoped state they need. `docs/CODE-PACK.md` records the decisions,
including why this is a pack rather than a seventh node.
"""

from .active import active_root, runs_granted, set_active_root, writes_granted
from .libraries import LibraryTools
from .runners import CodeRunner
from .tools import SERVER_ID, CodeTools, OutsideTheProject
from .writes import CodeWriter

__all__ = [
    "SERVER_ID",
    "CodeTools",
    "CodeRunner",
    "CodeWriter",
    "LibraryTools",
    "OutsideTheProject",
    "active_root",
    "runs_granted",
    "set_active_root",
    "writes_granted",
]
