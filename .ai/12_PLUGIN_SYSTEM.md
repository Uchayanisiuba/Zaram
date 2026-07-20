# Zaram Plugin System Architecture

**Version:** 1.0.0  
**Status:** Authoritative Engineering Contract  
**Audience:** Core Engineering Team, Plugin Developers, Security Team  

---

## 1. Plugin System Overview

The Plugin System is the mechanism by which Layer 4 (Plugins) extends Layer 3 (Capability Runtimes) and Layer 2 (Core Runtimes). Plugins are strictly sandboxed, declarative, and lifecycle-managed. They cannot execute arbitrary code in the main Zaram process.

---

## 2. The Plugin Manifest

Every plugin must include a `zaram-plugin.json` manifest at its root. This file is the single source of truth for the Plugin Manager.

### Manifest Schema

```json
{
  "id": "com.acme.finance.broker-connector",
  "version": "1.2.0",
  "name": "Acme Broker Connector",
  "description": "Connects the Finance Runtime to Acme Brokerage APIs.",
  "author": "Acme Corp",
  "license": "MIT",
  
  "target_layer": "capability_runtime",
  "extends": "finance-runtime",
  
  "permissions": [
    "network:outbound:api.acme.com",
    "storage:read:credentials"
  ],
  
  "capabilities": {
    "provides_tools": ["acme.place_order", "acme.get_portfolio"],
    "ui_panels": ["acme-portfolio-widget"]
  },
  
  "runtime_requirements": {
    "zaram_platform": ">=1.0.0",
    "finance_runtime": ">=1.1.0"
  },
  
  "entrypoints": {
    "compute": "./dist/worker.js",
    "ui": "./dist/panel.js"
  }
}