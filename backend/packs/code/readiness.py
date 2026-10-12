"""Bounded HTTP availability, not an assertion of app identity or correctness."""
from __future__ import annotations

import http.client
import ipaddress
from urllib.parse import urlsplit


def probe_app(url: str, timeout: float = 0.5) -> dict:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        local = host == "localhost" or host.endswith(".localhost")
        try:
            local = local or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if parsed.scheme not in {"http", "https"} or not local or parsed.username or parsed.password:
            return {"ready": False, "readiness_error": "Only credential-free loopback URLs are probed."}
        cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = cls(host, parsed.port, timeout=timeout)
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request("GET", path, headers={"Connection": "close"})
            response = connection.getresponse()
            # Read the reply (bounded) before hanging up. Closing with the body
            # unread aborts the server mid-write, and a dev server logs that as
            # a traceback in the person's own app log -- seen on a plain Python
            # server, where it also pushed the app's real output out of view.
            try:
                response.read(64 * 1024)
            except (OSError, http.client.HTTPException):
                pass
            return {"ready": 200 <= response.status < 300, "http_status": response.status,
                    "readiness_error": "" if 200 <= response.status < 300 else
                    f"HTTP {response.status}; redirects are not followed."}
        finally:
            connection.close()
    except (OSError, ValueError, http.client.HTTPException) as error:
        return {"ready": False, "readiness_error": str(error)}
