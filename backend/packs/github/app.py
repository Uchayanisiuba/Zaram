"""The Zaram GitHub App's public identifiers.

**Nothing in this file is a secret.** A client ID is how GitHub knows which app is
asking; it appears in the address of every sign-in page and is meant to be shipped
inside the program. The two things that would be secret -- the app's client secret
and its private key -- are never used by Zaram and were discarded when the app was
registered: sign-in is GitHub's *device flow*, which needs the ID and nothing else.

Why an app rather than a token somebody pastes in, or a broad OAuth scope: a GitHub
App is granted **repository by repository**. A person chooses, on GitHub, which of
their repositories Zaram may touch, and can change that at any time at
github.com/settings/installations. That is the same arrangement the Claude and
ChatGPT connectors use, with one difference that matters here: the token lives on
this machine, never on a server of ours (there is none).

Overridable by environment (`ZARAM_GITHUB_CLIENT_ID`, `ZARAM_GITHUB_APP_SLUG`) so a
test, or a fork with its own app, needs no edit.
"""

from __future__ import annotations

import os

#: Filled in from the registered app. Empty means the app has not been registered,
#: and every surface says so rather than offering a button that cannot work.
CLIENT_ID = "Iv23lixef3FW76R7W7Vf"

#: The app's address on GitHub: github.com/apps/<slug>.
APP_SLUG = "zaram-app"

#: GitHub's own addresses. Separate constants so a test points them at a local
#: server and nothing else in the pack knows about the difference.
WEB_BASE = "https://github.com"
API_BASE = "https://api.github.com"

#: The two hosts connecting GitHub allows, by name. Pressing Connect is the
#: deliberate decision about these destinations (rule 7j); pushing a repository
#: is a different data class and asks again, once, by name.
HOSTS = ("github.com", "api.github.com")


def client_id() -> str:
    return (os.getenv("ZARAM_GITHUB_CLIENT_ID") or CLIENT_ID).strip()


def slug() -> str:
    return (os.getenv("ZARAM_GITHUB_APP_SLUG") or APP_SLUG).strip()


def configured() -> bool:
    return bool(client_id())


def install_url() -> str:
    """Where a person chooses which repositories Zaram may reach."""
    return f"https://github.com/apps/{slug()}/installations/new"


def manage_url() -> str:
    """Where a person withdraws Zaram's access, on GitHub's side."""
    return "https://github.com/settings/applications"
