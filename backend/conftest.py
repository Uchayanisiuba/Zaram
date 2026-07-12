# backend/conftest.py
"""Pytest configuration: ensure the backend package root is importable.

The application packages (``core``, ``runtimes``, ``implementations``,
``services``) use absolute imports that resolve against the ``backend/``
directory. Adding it to ``sys.path`` lets the test suite run from any cwd.
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
