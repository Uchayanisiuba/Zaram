# ADR-016: Knowledge Runtime Provider Interface
**Status:** Accepted (RC2)

## Context
Knowledge must be aggregated from dozens of disparate sources without hardcoding them into the Intelligence Layer. The Knowledge Runtime must support local memory, vector databases, graph databases, projects, web sources, documents, APIs, and plugins.

## Decision
Define a **Universal Provider Interface** for the Knowledge Runtime. All data sources must implement this interface:

### Provider Categories

| Category | Examples |
|---|---|
| **Memory Providers** | Local Memory Runtime, Episodic Memory, Semantic Memory |
| **Vector Database Providers** | ChromaDB, FAISS, Qdrant, Milvus |
| **Graph Database Providers** | Neo4j, ArangoDB, Local Graph DB |
| **Project Providers** | Workspace files, IDE context, VS Code workspace |
| **Code Repository Providers** | GitHub, GitLab, Bitbucket, local Git repos |
| **Document Providers** | PDF, Office Documents (Word, Excel, PowerPoint), Markdown, TXT, HTML |
| **Web Providers** | Web Search (DuckDuckGo, SearXNG), RSS feeds, News APIs |
| **Database Providers** | SQLite, PostgreSQL, MySQL, MongoDB |
| **API Providers** | REST APIs, GraphQL endpoints, Webhooks |
| **Plugin Providers** | Third-party data streams, custom integrations |
| **Bookmark Providers** | Browser bookmarks, saved links, reading lists |
| **Future Providers** | Email, Calendar, Notion, Obsidian, Slack, Discord, IoT sensors |

### Key Principles
1. **Provider Agnosticism:** The Intelligence Layer only requests `knowledge.search`. It never knows if the data came from a local PDF, a GitHub repository, a vector database, or an RSS feed.
2. **Unified Interface:** All providers implement the same `search()`, `store()`, `update()`, and `delete()` methods.
3. **Pluggable Architecture:** New providers can be added simply by implementing the interface. No changes to core logic required.
4. **Local-First:** All providers default to local execution. Cloud providers are optional and require explicit user consent.

## Consequences
The Knowledge Runtime becomes the universal gateway to all information. The Intelligence Layer can query any source without knowing its implementation. This allows Zaram to integrate with any future data source simply by adding a new Provider.