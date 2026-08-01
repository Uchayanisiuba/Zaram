# ADR-005: Knowledge Runtime Provider Agnosticism
**Status:** Accepted
**Context:** Knowledge must come from local files, web, RSS, and memory without hardcoding providers.
**Decision:** The Knowledge Runtime uses a Provider Manager. The Executive Runtime requests `knowledge.search` and never knows the underlying provider.
**Consequences:** Allows seamless addition of new data sources (e.g., Notion, Obsidian) without altering core logic.