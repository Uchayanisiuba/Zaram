"""GitHub, as tools the model can use when the person asks.

"Push this project to my GitHub", "open a pull request for this branch", "file an
issue about the crash": the person says it in the conversation and the model does
it, through the same gate as every other tool. It is an MCP server in process, like
`zaram-self` and `draw`, so it inherits the policy gate, the confirm card and the
egress log without new machinery.

**Every action that changes something on GitHub asks, every time, and no standing
yes can be kept for it** (`policy.always_asks`). A push puts a whole project in
front of whoever can read the repository; a pull request or an issue is public
words in the person's name. Those are the two things rule 6 and rule 7j say must
not become a dialog nobody reads *or* a permission nobody notices -- and asking each
time is what keeps the first from being worse than the second.

**What it can reach is what the person chose on GitHub.** The app is installed
repository by repository; `github_list_repositories` returns exactly those, and a
push or a pull request to anything else is refused here, before GitHub is asked.
The model never supplies a host: addresses are built from `owner/name` after it has
been checked against a strict pattern.

**A push is never forced.** There is no `force` argument and no way to spell one;
a rejected push is reported, and the person decides what to do about it in their
own terminal. And **the token never appears in a command line**: it travels in the
environment of the one `git` process that needs it, where other programs cannot
list it the way they can list arguments, and is scrubbed from anything git says
back.

The push is a `git` process, which `EgressGate` cannot see -- the same gap
`packs/code/publishing.py` closes for the terminal. So before it runs the gate is
asked, with `DataClass.REPO` named, and what is logged is how many commits and to
where, never what they said.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

from . import app, vault
from .client import GitHub, GitHubError, current, valid_full_name

logger = logging.getLogger(__name__)

SERVER_ID = "github"

GET_STATUS = "github_get_status"
LIST_REPOSITORIES = "github_list_repositories"
PUSH_BRANCH = "github_push_branch"
OPEN_PULL_REQUEST = "github_open_pull_request"
CREATE_ISSUE = "github_create_issue"
CREATE_REPOSITORY = "github_create_repository"

#: The tools that only look.
READ_TOOLS = frozenset({GET_STATUS, LIST_REPOSITORIES})

#: The tools that change something on GitHub. Each asks every time.
WRITE_TOOLS = frozenset({PUSH_BRANCH, OPEN_PULL_REQUEST, CREATE_ISSUE, CREATE_REPOSITORY})

HOW_TO_PERMIT = "Every GitHub action asks each time; there is no standing yes for it."

GIT_TIMEOUT_SECONDS = 180

#: Words in a git error that have a known remedy, in order of how often they are the
#: cause. Said back to the person in place of git's own wall of text.
_GIT_HINTS = (
    ("workflow", "GitHub refuses a push that changes .github/workflows unless the app has the 'workflows' permission, which Zaram does not ask for."),
    ("protected branch", "That branch is protected on GitHub. Push to a new branch and open a pull request instead."),
    ("non-fast-forward", "GitHub has commits this project does not. Zaram never forces a push; pull them in your terminal first."),
    ("fetch first", "GitHub has commits this project does not. Zaram never forces a push; pull them in your terminal first."),
    ("denied", "GitHub did not allow Zaram to write to that repository. Check that Zaram is installed on it with write access."),
    ("403", "GitHub did not allow Zaram to write to that repository. Check that Zaram is installed on it with write access."),
    ("not found", "GitHub could not find that repository under that name."),
)


def _schema(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


def _text(arguments: Dict[str, Any], key: str, limit: int) -> str:
    value = arguments.get(key)
    return value.strip()[:limit] if isinstance(value, str) else ""


def _git_out(root: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def scrub(text: str, token: str) -> str:
    """Remove the token (and its base64 form) from anything about to be shown."""
    cleaned = text or ""
    for secret in {token, base64.b64encode(f"x-access-token:{token}".encode()).decode()}:
        if secret:
            cleaned = cleaned.replace(secret, "***")
    return cleaned


class GitHubTools:
    """Zaram's built-in GitHub server."""

    def __init__(
        self,
        root: Callable[[], Optional[Path]],
        *,
        client: Optional[GitHub] = None,
        gate: Any = None,
        connection: Callable[[], Optional[vault.Connection]] = vault.load,
        remote_url: Optional[Callable[[str], str]] = None,
        git_timeout: float = GIT_TIMEOUT_SECONDS,
    ) -> None:
        self._root = root
        self._client = client or GitHub(gate=gate)
        self._gate = gate
        self._connection = connection
        self._remote_url = remote_url or (lambda repo: f"{app.WEB_BASE}/{repo}.git")
        self._git_timeout = git_timeout

    # -- the built-in server surface ------------------------------------------ #

    def connect(self) -> None:
        """Nothing to start."""

    def close(self) -> None:
        """Nothing to stop."""

    def granted_tools(self) -> set:
        """Only the reads are offered without asking; nothing here is ever granted for good."""
        return set(READ_TOOLS)

    def mutative_tools(self) -> set:
        return set(WRITE_TOOLS)

    def grant_scope(self, tool_name: str) -> str:
        return ""

    def how_to_permit(self, tool_name: str) -> str:
        return HOW_TO_PERMIT if tool_name in WRITE_TOOLS else ""

    def tools_for_request(self) -> List[ToolDescriptor]:
        """The tools worth putting in front of the model *right now*.

        Six tools are several hundred tokens on every turn of every conversation,
        and a local model's window is the scarce thing -- the code pack learned
        that on 4 October 2026 and offers nothing it cannot act on. So: until
        GitHub is connected, the model is offered the one tool that can say so,
        which is enough for it to tell the person where to connect rather than
        guess. Connected, it gets the set; and the push, which has nothing to act
        on without a project, only while one is open. `list_tools` is unchanged:
        Settings lists what the server *can* do.
        """
        everything = self.list_tools()
        if self._connected() is None:
            return [t for t in everything if t.name == GET_STATUS]
        if self._root() is None:
            return [t for t in everything if t.name != PUSH_BRANCH]
        return everything

    def list_tools(self) -> List[ToolDescriptor]:
        def tool(name: str, description: str, schema: Dict[str, Any]) -> ToolDescriptor:
            return ToolDescriptor(server_id=SERVER_ID, name=name, description=description, input_schema=schema)

        repo = {"type": "string", "description": "owner/name, exactly as github_list_repositories gave it."}
        return [
            tool(GET_STATUS, "Whether GitHub is connected, as whom, and how to connect or add repositories. Use it before any other GitHub tool.", _schema({}, [])),
            tool(
                LIST_REPOSITORIES,
                "The repositories on GitHub that the person has let Zaram reach, with whether each can be pushed to. "
                "Only these can be pushed to or opened pull requests in.",
                _schema({}, []),
            ),
            tool(
                PUSH_BRANCH,
                "Push the open project's current branch to one of the person's GitHub repositories. Never forced. "
                "It sends the whole branch history, so the person is asked every time, naming the repository.",
                _schema(
                    {
                        "repository": repo,
                        "branch": {"type": "string", "description": "The branch name to create or update on GitHub. Defaults to the project's current branch."},
                    },
                    ["repository"],
                ),
            ),
            tool(
                OPEN_PULL_REQUEST,
                "Open a pull request on GitHub from a branch that has already been pushed. The person is asked every time.",
                _schema(
                    {
                        "repository": repo,
                        "title": {"type": "string", "maxLength": 200},
                        "head": {"type": "string", "description": "The branch with the changes."},
                        "base": {"type": "string", "description": "The branch to merge into. Defaults to the repository's default branch."},
                        "body": {"type": "string", "maxLength": 6000},
                        "draft": {"type": "boolean"},
                    },
                    ["repository", "title", "head"],
                ),
            ),
            tool(
                CREATE_ISSUE,
                "File an issue on GitHub. The person is asked every time, and sees the title.",
                _schema(
                    {"repository": repo, "title": {"type": "string", "maxLength": 200}, "body": {"type": "string", "maxLength": 6000}},
                    ["repository", "title"],
                ),
            ),
            tool(
                CREATE_REPOSITORY,
                "Create a new, empty, private repository on the person's GitHub. GitHub may not allow this connection to "
                "do it; if so the answer says what to do instead. The person is asked every time.",
                _schema(
                    {"name": {"type": "string", "maxLength": 100}, "description": {"type": "string", "maxLength": 300}},
                    ["name"],
                ),
            ),
        ]

    # -- calling --------------------------------------------------------------- #

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        handler = {
            GET_STATUS: self._status,
            LIST_REPOSITORIES: self._list,
            PUSH_BRANCH: self._push,
            OPEN_PULL_REQUEST: self._pull_request,
            CREATE_ISSUE: self._issue,
            CREATE_REPOSITORY: self._create_repository,
        }.get(name)
        if handler is None:
            return {"success": False, "error": f"there is no GitHub tool called {name!r}"}
        try:
            return handler(arguments)
        except GitHubError as error:
            return {"success": False, "error": str(error)}

    # -- helpers --------------------------------------------------------------- #

    def _connected(self) -> Optional[vault.Connection]:
        return current(self._connection())

    def _not_connected(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "GitHub is not connected. The person connects it in Settings -> Tools -> GitHub.",
        }

    def _reachable(self, connection: vault.Connection, repository: str, *, need_push: bool) -> Optional[Dict[str, Any]]:
        """An error answer when ``repository`` is not one Zaram may use, else ``None``."""
        if not valid_full_name(repository):
            return {"success": False, "error": f"{repository!r} is not an owner/name repository."}
        listing = self._client.repositories(connection.token)
        match = next((r for r in listing if r["full_name"].lower() == repository.lower()), None)
        if match is None:
            return {
                "success": False,
                "error": f"Zaram has not been given access to {repository}. The person chooses repositories at {app.install_url()}.",
            }
        if need_push and not match["can_push"]:
            return {"success": False, "error": f"Zaram can read {repository} but not write to it."}
        return None

    # -- the tools -------------------------------------------------------------- #

    def _status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not app.configured():
            return {"success": True, "connected": False, "note": "The GitHub app is not registered on this build."}
        connection = self._connected()
        if connection is None:
            stored = self._connection()
            expired = stored is not None and stored.expired
            return {
                "success": True,
                "connected": False,
                "note": ("The GitHub sign-in expired. " if expired else "") + "The person connects GitHub in Settings -> Tools -> GitHub.",
            }
        return {
            "success": True,
            "connected": True,
            "login": connection.login,
            "choose_repositories_at": app.install_url(),
        }

    def _list(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._connected()
        if connection is None:
            return self._not_connected()
        repositories = self._client.repositories(connection.token)
        return {
            "success": True,
            "repositories": repositories,
            "note": "" if repositories else f"Zaram is not installed on any repository yet. The person chooses them at {app.install_url()}.",
        }

    def _push(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._connected()
        if connection is None:
            return self._not_connected()
        root = self._root()
        if root is None:
            return {"success": False, "error": "No project is open, so there is nothing to push. Open a coding project first."}
        repository = _text(arguments, "repository", 140)
        refused = self._reachable(connection, repository, need_push=True)
        if refused is not None:
            return refused

        if _git_out(root, "rev-parse", "--is-inside-work-tree") != "true":
            return {"success": False, "error": "The open project's folder is not a git repository."}
        current_branch = _git_out(root, "rev-parse", "--abbrev-ref", "HEAD") or ""
        branch = _text(arguments, "branch", 200) or current_branch
        if not branch or branch == "HEAD" or branch.startswith("-"):
            return {"success": False, "error": "The project is not on a branch (detached HEAD). Say which branch name to push to."}
        if _git_out(root, "check-ref-format", "--branch", branch) is None:
            return {"success": False, "error": f"{branch!r} is not a valid branch name."}
        if _git_out(root, "rev-parse", "--verify", "HEAD") is None:
            return {"success": False, "error": "The project has no commits yet, so there is nothing to push."}

        # The consent that governs a repository leaving: its own data class, asked
        # once by name for this destination and remembered (rule 7j). What it
        # carries is a count and a place, never content.
        count = _git_out(root, "rev-list", "--count", "HEAD") or "?"
        summary = f"git push of branch {branch} ({count} commits in its history) to {repository}"
        denied = self._ask_gate(summary)
        if denied is not None:
            return {"success": False, "error": denied}

        outcome = self._run_push(root, repository, branch, connection.token)
        if outcome["ok"]:
            dirty = bool(_git_out(root, "status", "--porcelain"))
            return {
                "success": True,
                "repository": repository,
                "branch": branch,
                "url": f"https://github.com/{repository}/tree/{branch}",
                "note": "Changes not yet committed were not pushed." if dirty else "",
            }
        return {"success": False, "error": outcome["message"]}

    def _ask_gate(self, summary: str) -> Optional[str]:
        from core.egress import DataClass, EgressDenied, get_gate

        gate = self._gate if self._gate is not None else get_gate()
        try:
            gate.check(
                f"{app.WEB_BASE}/",
                method="POST",
                body=summary,
                source="github.push",
                data_class=DataClass.REPO,
            )
        except EgressDenied as denied:
            return (
                f"Not pushed. {denied} Pushing a repository is its own decision, separate from connecting GitHub: "
                "allow repositories to github.com in Activity, then ask again. Nothing was sent."
            )
        return None

    def _run_push(self, root: Path, repository: str, branch: str, token: str) -> Dict[str, Any]:
        url = self._remote_url(repository)
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        environment = {
            **os.environ,
            # Never wait for a person at a prompt this process cannot show.
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": f"http.{app.WEB_BASE}/.extraheader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
            # And no stored sign-in from some other helper answering instead.
            "GIT_CONFIG_KEY_1": "credential.helper",
            "GIT_CONFIG_VALUE_1": "",
        }
        try:
            done = subprocess.run(
                ["git", "push", url, f"HEAD:refs/heads/{branch}"],
                cwd=str(root), capture_output=True, text=True, timeout=self._git_timeout,
                encoding="utf-8", errors="replace", env=environment,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": "The push took too long and was stopped. Nothing is half-sent: git either finishes or does not."}
        except OSError as error:
            return {"ok": False, "message": f"git could not be run: {error}"}
        if done.returncode == 0:
            return {"ok": True, "message": ""}
        said = scrub((done.stderr or done.stdout or "").strip(), token)
        lowered = said.lower()
        hint = next((h for needle, h in _GIT_HINTS if needle in lowered), "")
        short = " ".join(said.split())[:400]
        return {"ok": False, "message": f"The push failed. {hint} (git said: {short})".replace("  ", " ")}

    def _pull_request(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._connected()
        if connection is None:
            return self._not_connected()
        repository = _text(arguments, "repository", 140)
        refused = self._reachable(connection, repository, need_push=True)
        if refused is not None:
            return refused
        title, head = _text(arguments, "title", 200), _text(arguments, "head", 200)
        if not title or not head:
            return {"success": False, "error": "A pull request needs a title and the branch that has the changes."}
        base = _text(arguments, "base", 200) or self._client.default_branch(connection.token, repository)
        made = self._client.open_pull_request(
            connection.token, repository, title=title, head=head, base=base,
            body=_text(arguments, "body", 6000), draft=bool(arguments.get("draft")),
        )
        return {"success": True, "repository": repository, **made}

    def _issue(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._connected()
        if connection is None:
            return self._not_connected()
        repository = _text(arguments, "repository", 140)
        refused = self._reachable(connection, repository, need_push=False)
        if refused is not None:
            return refused
        title = _text(arguments, "title", 200)
        if not title:
            return {"success": False, "error": "An issue needs a title."}
        made = self._client.create_issue(connection.token, repository, title=title, body=_text(arguments, "body", 6000))
        return {"success": True, "repository": repository, **made}

    def _create_repository(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        connection = self._connected()
        if connection is None:
            return self._not_connected()
        name = _text(arguments, "name", 100)
        if not name or not valid_full_name(f"{connection.login}/{name}"):
            return {"success": False, "error": "A repository name may use letters, numbers, dots, dashes and underscores."}
        try:
            made = self._client.create_repository(
                connection.token, name, private=True, description=_text(arguments, "description", 300)
            )
        except GitHubError as error:
            if error.status in (403, 404):
                return {
                    "success": False,
                    "error": (
                        "GitHub does not let this connection create a repository. Create an empty one at "
                        f"https://github.com/new, then choose it at {app.install_url()} and it will appear here."
                    ),
                }
            raise
        return {
            "success": True,
            **made,
            "note": f"Zaram can use it once it is installed on it: choose it at {app.install_url()} unless the installation covers all repositories.",
        }
