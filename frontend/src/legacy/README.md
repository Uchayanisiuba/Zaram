# Legacy surfaces

Preserved, not deleted. **Nothing here is imported by the running app.**

These workspaces belong to the retired "AI operating system" direction. They are out of
scope for v1 per `CLAUDE.md`, so they were unlinked from the shell rather than removed —
the code may be worth something later, and deleting it is a decision that can be made
once, later, with more information.

| File | Was | Why it is here |
|---|---|---|
| `BuildWorkspace.tsx` | Code studio surface | Code studio / IDE integration is out of scope |
| `CanvasWorkspace.tsx` | Infinite canvas surface | Additional workspaces are out of scope |
| `PluginsWorkspace.tsx` | Extensions browser | The extensions marketplace is out of scope |

## Rules

- **Do not import from this directory.** If a v1 feature seems to need something here,
  that is a signal to check the scope list in `CLAUDE.md`, not a signal to re-link it.
- Finding code here is not permission to revive it.
- These files still typecheck as part of `src/`. If they start failing after a
  refactor, delete them rather than repairing them — they are not part of the product.

## Provenance

Moved out of `src/workspaces/` on 3 August 2026, along with the deletion of
`RuntimePanel.tsx` (which displayed fabricated telemetry under a "LIVE" badge) and the
seven zero-byte files in `src/accessibility/`.
