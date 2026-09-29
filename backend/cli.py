"""The Spine from a terminal — recall, remember, correct, scriptable.

Why this exists, and why it is *not* a coding assistant
------------------------------------------------------
`CLAUDE.md`'s rule 7 claims the memory is exportable and outlives the
provider — *and Zaram itself*. A claim that strong is much stronger when the
memory can be piped. `zcode recall "the Northwind rate" | jq` is that claim
made operable, and no competitor can answer it: their memory is in their
client, in their format, and gone when the client is switched.

So this is the Spine as a command, and deliberately nothing else. It does not
write code, run commands or drive a repository — the `code` pack already does
that inside the product, where the write policy, the undo and the confirm live.

What it may do, and who decided
-------------------------------
**This is a paired client, and it reaches exactly what paired clients reach.**
`main.PAIRED_CLIENT_ROUTES` is the allow-list and its comment is the rule:
*"A paired client is a named client of the memory, not a second owner."* Five
routes — recall, remember, correct, read one fact, list projects.

Two things a person will ask for are therefore **absent on purpose**:

* ``ask`` — a full question needs ``POST /chat``, which paired clients cannot
  reach. Adding it would mean widening that allow-list, which is a security
  decision for the maintainer and not one a convenience command gets to make.
* ``export`` — same reason, and it is the one that stings, because export is
  rule 7's own promise. It stays in the owner's interface until somebody
  decides deliberately that a paired credential may take the whole Spine out.

Naming them here rather than leaving them missing is the point: a person who
wants them should find the reason, not a gap.

How it is run — `zcode`
-----------------------
``zcode`` from anywhere, via the launcher at the repository root (`zcode.cmd`
on Windows, `zcode` elsewhere). Both do the same three things: find the
bundled interpreter, change to ``backend/``, and run ``-m cli``.

**There is still no ``[project.scripts]`` entry, and that reasoning is
unchanged**: the root ``pyproject.toml`` has no ``build-system``, Zaram ships
as an Electron app with a bundled backend and is never ``pip install``-ed, so a
console script declared there would be metadata nothing reads — the same
dead-but-tested shape this repository has paid for fifteen times.

What *was* wrong was treating that as an argument against a name at all. It is
an argument about packaging. A launcher needs no packaging, and without one the
usage line read ``Usage: cli.py`` while the way to run it was
``cd backend && venv\Scripts\python.exe -m cli`` — which is a memory nobody
reaches. Named **ZCode** by the maintainer, 29 September 2026.

``prog_name`` is passed explicitly at the call. Typer's ``name=`` sets the
app's own name and Click still takes the usage line from ``sys.argv[0]``,
which under ``-m cli`` is the script path. Setting one without the other is
how it came to introduce itself as a filename.

The credential
--------------
**Never the API secret, and never invented here.** `zaram_mcp.py` established
the mechanism — pair once, hold a credential, send it as `X-Zaram-Auth` — and
this reuses that module rather than writing a second one. A second auth story
is how a product ends up with a weak one.

The token is stored under `core.paths.data_dir()`, readable by anything that
can read the directory. That is the same honest weakness `CLAUDE.md` records
about the development secret fallback, and it is stated rather than glossed:
on a shared machine, pair per user account.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from zaram_mcp import DEFAULT_API, Spine, pair as pair_with_zaram

app = typer.Typer(
    name="zaram",
    help="Your Spine, from the command line. Recall, remember, correct.",
    add_completion=False,
    no_args_is_help=True,
)

#: What the command calls itself in usage and errors. See the docstring:
#: Typer's `name=` above is not what Click prints.
PROGRAM = "zcode"

#: Written to stderr, always. Everything a person reads goes here so that
#: stdout stays a clean machine-readable stream — `zcode recall x --json | jq`
#: must not have a table in it.
err = Console(stderr=True)
out = Console()

_ENV_TOKEN = "ZARAM_CLI_TOKEN"
_ENV_API = "ZARAM_API"


def _token_path() -> Path:
    from core.paths import data_dir

    return Path(data_dir()) / "cli-credential.json"


def _credential() -> str:
    """The paired credential, from the environment or the stored file.

    The environment wins, so a script can run as a different named client
    without disturbing the one a person paired interactively.
    """
    from_env = os.environ.get(_ENV_TOKEN, "").strip()
    if from_env:
        return from_env

    path = _token_path()
    if not path.exists():
        err.print(
            "[bold]Not paired yet.[/bold] In Zaram, open Settings and issue a "
            "pairing code, then run:\n\n    zaram pair <code>\n"
        )
        raise typer.Exit(code=2)
    try:
        return str(json.loads(path.read_text(encoding="utf-8"))["credential"])
    except (ValueError, KeyError, OSError) as exc:
        err.print(f"[bold]The stored credential is unreadable[/bold] ({exc}). Re-run `zaram pair`.")
        raise typer.Exit(code=2) from exc


def _client() -> Spine:
    return Spine(_credential(), os.environ.get(_ENV_API) or DEFAULT_API)


#: Every command resolves its client *before* its try block, and that is not
#: style. `typer.Exit` is an ordinary `Exception`, so a credential failure
#: raised inside one of these handlers is caught by it and reported as a
#: generic error — which swallowed the one message a brand-new user needs,
#: "not paired yet, run `zaram pair`". Found by a test, not by reading.


def _fail(exc: Exception) -> "typer.Exit":
    """Report an error the way a terminal expects and exit non-zero.

    A stack trace is not a message. `SpineClient` already raises with a
    sentence naming the cause — "Zaram is not reachable at … Is it running?" —
    so the useful thing is to show that and nothing else.
    """
    err.print(f"[bold red]![/bold red] {exc}")
    return typer.Exit(code=1)


# --------------------------------------------------------------------------- #
# Pairing
# --------------------------------------------------------------------------- #


@app.command()
def pair(
    code: str = typer.Argument(..., help="The pairing code shown in Zaram's Settings."),
    name: str = typer.Option("zaram-cli", help="How this client appears in Zaram's device list."),
    api: str = typer.Option(DEFAULT_API, envvar=_ENV_API, help="The Zaram to pair with."),
) -> None:
    """Redeem a pairing code and store the credential for later commands.

    The code is single-use and expires in a minute, which is what makes a
    photographed QR worthless. The credential comes back exactly once —
    nothing can recover it afterwards, so it is written here and nowhere else.
    """
    try:
        result = pair_with_zaram(code.strip(), name, api)
    except Exception as exc:  # noqa: BLE001 — every failure is a message, not a trace
        raise _fail(exc) from exc

    credential = result.get("credential")
    if not credential:
        raise _fail(RuntimeError("Zaram accepted the code but returned no credential."))

    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "credential": credential}, indent=1), encoding="utf-8"
    )
    try:
        # Owner-only where the platform has the concept. Windows ignores it,
        # which is why the docstring says what it says about shared machines
        # rather than claiming a protection that is not there.
        os.chmod(path, 0o600)
    except OSError:
        pass

    err.print(f"Paired as [bold]{name}[/bold]. Revoke it any time in Zaram's Settings.")


# --------------------------------------------------------------------------- #
# The Spine
# --------------------------------------------------------------------------- #


@app.command()
def recall(
    query: str = typer.Argument(..., help="What to look for."),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Scope to one project."),
    limit: int = typer.Option(6, "--limit", "-n", min=1, max=50),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable, on stdout."),
) -> None:
    """Search the Spine and show what it found, with where each fact came from.

    **Provenance is printed, not optional.** Rule 2 says an answer that cites
    nothing is a bug, and a terminal is the easiest place in the product to
    quietly drop the citation because it costs a column.
    """
    spine = _client()
    try:
        payload = spine.recall(query, project, limit)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return

    facts = payload.get("facts") or payload.get("results") or []
    if not facts:
        err.print("Nothing recalled. Rule 9: it says so rather than filling the gap.")
        return

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("id", style="dim", no_wrap=True)
    table.add_column("fact")
    table.add_column("origin", style="dim", no_wrap=True)
    table.add_column("scope", style="dim", no_wrap=True)
    for fact in facts:
        table.add_row(
            str(fact.get("id", ""))[:12],
            str(fact.get("content") or fact.get("text") or ""),
            str(fact.get("origin") or ""),
            str(fact.get("scope") or fact.get("project_id") or "global"),
        )
    out.print(table)


@app.command()
def remember(
    text: str = typer.Argument(..., help="The fact to store."),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Scope it to one project."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Store one fact.

    Scope defaults to global when no project is named, which is rule 7i read
    honestly: a fact stated outside any project genuinely is not about one, and
    inventing a project for it would be a value nobody entered.
    """
    spine = _client()
    try:
        payload = spine.remember(text, project)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return
    err.print(f"Remembered [dim]{str(payload.get('id', ''))[:12]}[/dim].")


@app.command()
def correct(
    fact_id: str = typer.Argument(..., help="The fact's id, from `zaram recall`."),
    text: str = typer.Argument(..., help="What it should say instead."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Correct a stored fact, so the answers that used it change.

    Rule 4 is the whole product in one command. It is deliberately a
    *correction* and not a delete: what the fact used to say is part of the
    record, and an interface that silently replaces it is one nobody can audit.
    """
    spine = _client()
    try:
        payload = spine.correct(fact_id, text)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return
    err.print(f"Corrected [dim]{fact_id[:12]}[/dim].")


@app.command()
def show(
    fact_id: str = typer.Argument(..., help="The fact's id."),
) -> None:
    """Print one fact as JSON, for piping."""
    spine = _client()
    try:
        payload = spine._call("GET", f"/memory/{fact_id}")  # noqa: SLF001
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=1))


@app.command()
def projects(as_json: bool = typer.Option(False, "--json")) -> None:
    """List the projects a fact can be scoped to."""
    spine = _client()
    try:
        payload = spine.projects()
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return

    rows = payload.get("projects") or []
    if not rows:
        err.print("No projects. Facts land global, which is rule 7i's default.")
        return
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("id", style="dim", no_wrap=True)
    table.add_column("name")
    table.add_column("type", style="dim")
    for row in rows:
        table.add_row(str(row.get("id", "")), str(row.get("name", "")), str(row.get("type", "")))
    out.print(table)


def main() -> None:
    app(prog_name=PROGRAM)


if __name__ == "__main__":
    # **Through `main`, not around it.** This called `app()` directly, so
    # `main`'s `prog_name` never applied on the one path anybody uses —
    # `python -m cli`, which is what the `zcode` launcher runs. Two halves
    # each correct on their own, with nothing exercising the join, which is
    # this repository's most expensive recurring shape.
    sys.exit(main())
