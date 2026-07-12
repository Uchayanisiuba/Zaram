# Runtime Contract

Every Runtime MUST expose

initialize()

shutdown()

status()

health()

metrics()

All Runtime modules must

- publish events
- structured logging
- graceful shutdown
- dependency injection
- configuration support
