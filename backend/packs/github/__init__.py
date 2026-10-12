"""The GitHub pack: connect an account, and push, open pull requests and file issues.

A pack is data and adapters, never navigation: this adds a section to Settings, a
built-in tool server, and nothing to the six places. See `tools.py` for what the
model may do and `vault.py` for what it costs (a credential on this machine, which
`DataClass.REPO` originally promised Zaram would never hold).
"""

from .app import configured
from .tools import SERVER_ID, GitHubTools

__all__ = ["SERVER_ID", "GitHubTools", "configured"]
