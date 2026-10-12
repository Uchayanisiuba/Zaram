"""Port detection and conflict resolution for dev servers.

Zaram reserves certain ports for its own services. When starting a dev server
for a project, we detect what port it expects and find a free alternative if
there's a conflict.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from .runners import Runner

# Zaram's own reserved ports. These are the ones Zaram itself uses.
ZARAM_RESERVED_PORTS: Set[int] = {
    8420,   # Backend API
    5173,   # Vite renderer (dev)
    5174,   # Vite renderer (prod preview, sometimes)
    1234,   # TabbyAPI (if running)
}

# Framework default ports
FRAMEWORK_DEFAULTS = {
    "vite": 5173,
    "vite:preview": 4173,
    "next": 3000,
    "next:dev": 3000,
    "react-scripts": 3000,  # Create React App
    "react": 3000,
    "webpack": 8080,
    "webpack-dev-server": 8080,
    "django": 8000,
    "flask": 5000,
    "fastapi": 8000,
    "express": 3000,
    "nuxt": 3000,
    "svelte": 5173,
    "astro": 4321,
    "remix": 3000,
    "gatsby": 8000,
    "angular": 4200,
    "rails": 3000,
    "phoenix": 4000,
}

# Env var names that frameworks use for port override
PORT_ENV_VARS = {
    "vite": "VITE_PORT",
    "next": "PORT",
    "react-scripts": "PORT",
    "webpack": "PORT",
    "webpack-dev-server": "PORT",
    "django": "PORT",
    "flask": "PORT",
    "fastapi": "PORT",
    "express": "PORT",
    "nuxt": "PORT",
    "svelte": "PORT",
    "astro": "PORT",
    "remix": "PORT",
    "gatsby": "PORT",
    "angular": "PORT",
    "rails": "PORT",
    "phoenix": "PORT",
}


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is free by attempting to bind to it."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def find_free_port(start: int, reserved: Optional[Set[int]] = None, host: str = "127.0.0.1") -> int:
    """Find the next free port starting from `start`."""
    reserved = reserved or set()
    port = start
    while port in reserved or not is_port_free(port, host):
        port += 1
        if port > 65535:
            raise RuntimeError(f"Could not find free port starting from {start}")
    return port


def detect_framework_from_runner(runner: Runner) -> Optional[str]:
    """Guess the framework from the runner's command."""
    cmd = " ".join(runner.argv).lower()
    name = runner.name.lower()

    # Check argv for framework signatures
    if "vite" in cmd:
        return "vite"
    if "next" in cmd:
        return "next"
    if "react-scripts" in cmd or "react" in cmd:
        return "react-scripts"
    if "webpack" in cmd:
        return "webpack"
    if "django" in cmd or "manage.py" in cmd:
        return "django"
    if "flask" in cmd:
        return "flask"
    if "uvicorn" in cmd or "fastapi" in cmd:
        return "fastapi"
    if "nuxt" in cmd:
        return "nuxt"
    if "svelte" in cmd:
        return "svelte"
    if "astro" in cmd:
        return "astro"
    if "remix" in cmd:
        return "remix"
    if "gatsby" in cmd:
        return "gatsby"
    if "ng " in cmd or "angular" in cmd:
        return "angular"
    if "rails" in cmd:
        return "rails"
    if "mix phx" in cmd or "phoenix" in cmd:
        return "phoenix"

    # Check runner name for framework hints
    for framework in FRAMEWORK_DEFAULTS:
        if framework in name:
            return framework

    return None


def extract_port_from_argv(argv: tuple[str, ...]) -> Optional[int]:
    """Extract port from command line arguments."""
    args = list(argv)
    for i, arg in enumerate(args):
        # --port=3000 or --port 3000
        if arg.startswith("--port="):
            try:
                return int(arg.split("=")[1])
            except (ValueError, IndexError):
                pass
        elif arg == "--port" or arg == "-p":
            if i + 1 < len(args):
                try:
                    return int(args[i + 1])
                except ValueError:
                    pass
        # Vite: --port, Next: -p, etc.
        elif arg.startswith("-p") and len(arg) > 2:
            try:
                return int(arg[2:])
            except ValueError:
                pass
    return None


def extract_port_from_package_json(root: Path, script_name: str) -> Optional[int]:
    """Try to extract port from package.json script definition."""
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        import json
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        script = data.get("scripts", {}).get(script_name, "")
        # Look for port in script string
        match = re.search(r'(?:--port|-p)\s*=?\s*(\d+)', script)
        if match:
            return int(match.group(1))
        # Check for PORT= env var in script
        match = re.search(r'PORT\s*=\s*(\d+)', script)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def detect_expected_port(runner: Runner, root: Path) -> Optional[int]:
    """Detect what port the dev server will try to use."""
    # 1. Check explicit argv
    port = extract_port_from_argv(runner.argv)
    if port:
        return port

    # 2. Check package.json for npm scripts
    if runner.name.startswith("npm:") or runner.name.startswith("yarn:") or runner.name.startswith("pnpm:"):
        script_name = runner.name.split(":", 1)[1]
        port = extract_port_from_package_json(root, script_name)
        if port:
            return port

    # 3. Guess from framework
    framework = detect_framework_from_runner(runner)
    if framework and framework in FRAMEWORK_DEFAULTS:
        return FRAMEWORK_DEFAULTS[framework]

    return None


def get_port_env_var(framework: Optional[str]) -> Optional[str]:
    """Get the environment variable name for port override for a framework."""
    if framework:
        return PORT_ENV_VARS.get(framework)
    return "PORT"  # Generic fallback


def resolve_dev_server_port(
    runner: Runner,
    root: Path,
    reserved: Optional[Set[int]] = None,
) -> tuple[int, dict]:
    """
    Resolve the port for a dev server, handling conflicts.

    Returns:
        (resolved_port, info_dict) where info_dict contains:
        - "original_port": what the server wanted
        - "framework": detected framework
        - "conflict": True if there was a conflict
        - "note": human-readable note about what happened
    """
    reserved = reserved or set()
    all_reserved = ZARAM_RESERVED_PORTS | reserved

    expected_port = detect_expected_port(runner, root)
    framework = detect_framework_from_runner(runner)

    if expected_port is None:
        # No specific port detected - let the server choose its default
        # We'll just check if the default framework port is free
        if framework and framework in FRAMEWORK_DEFAULTS:
            expected_port = FRAMEWORK_DEFAULTS[framework]
        else:
            return (0, {
                "original_port": None,
                "framework": framework,
                "conflict": False,
                "note": "Could not detect expected port; server will choose its own",
            })

    # Check if expected port is free
    if expected_port in all_reserved or not is_port_free(expected_port):
        # Conflict! Find alternative
        alt_port = find_free_port(expected_port + 1, all_reserved)
        env_var = get_port_env_var(framework) or "PORT"
        return (alt_port, {
            "original_port": expected_port,
            "resolved_port": alt_port,
            "framework": framework,
            "conflict": True,
            "env_var": env_var,
            "note": f"Port {expected_port} is in use (by Zaram or another process). "
                    f"Using port {alt_port} instead (set {env_var}={alt_port}).",
        })

    return (expected_port, {
        "original_port": expected_port,
        "framework": framework,
        "conflict": False,
        "note": f"Using port {expected_port}.",
    })


def allocate_stack_ports(
    runners: List[Runner],
    root: Path,
    reserved: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Allocate ports for a stack of runners, ensuring no conflicts between them.
    
    Returns a list of port info dicts, one per runner, with process_name and resolved_port.
    """
    from .runners import Runner  # local import to avoid circular
    
    reserved = reserved or set()
    all_reserved = ZARAM_RESERVED_PORTS | reserved
    results = []
    
    for runner in runners:
        # Use process name from group if available
        process_name = runner.group or runner.name.replace("npm:", "").replace(":", "_")
        
        expected_port = detect_expected_port(runner, root)
        framework = detect_framework_from_runner(runner)
        
        if expected_port is None:
            if framework and framework in FRAMEWORK_DEFAULTS:
                expected_port = FRAMEWORK_DEFAULTS[framework]
            else:
                results.append({
                    "process_name": process_name,
                    "original_port": None,
                    "resolved_port": 0,
                    "framework": framework,
                    "conflict": False,
                    "note": "Could not detect expected port; server will choose its own",
                })
                continue
        
        # Check if expected port is free (considering other runners in this stack)
        if expected_port in all_reserved or not is_port_free(expected_port):
            alt_port = find_free_port(expected_port + 1, all_reserved)
            env_var = get_port_env_var(framework) or "PORT"
            all_reserved.add(alt_port)
            results.append({
                "process_name": process_name,
                "original_port": expected_port,
                "resolved_port": alt_port,
                "framework": framework,
                "conflict": True,
                "env_var": env_var,
                "note": f"Port {expected_port} is in use (by Zaram or another process). "
                        f"Using port {alt_port} instead (set {env_var}={alt_port}).",
            })
        else:
            all_reserved.add(expected_port)
            results.append({
                "process_name": process_name,
                "original_port": expected_port,
                "resolved_port": expected_port,
                "framework": framework,
                "conflict": False,
                "note": f"Using port {expected_port}.",
            })
    
    return results