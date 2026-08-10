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
| `surfaces/*.tsx` (16) | The retired six-workspace shell | Agent, Browser, Build, Calendar, Code, Context, Create, Document, ImageGeneration, Project, Research, RuntimeMonitor, and duplicate Knowledge/Memory/Settings surfaces |
| `panels/ChatInterface.tsx` | Chat panel | Only importer was `WorkspaceSurface`; the two referenced each other and nothing else |
| `shell/BottomCommandDock.tsx` | Floating dock | Duplicated the left rail exactly and floated over content |
| `shell/LeftContextRail.tsx` | Second rail | Superseded by `components/LeftRail.tsx` |

## Rules

- **Do not import from this directory.** If a v1 feature seems to need something here,
  that is a signal to check the scope list in `CLAUDE.md`, not a signal to re-link it.
- Finding code here is not permission to revive it.
- These files still typecheck as part of `src/`. If they start failing after a
  refactor, delete them rather than repairing them — they are not part of the product.

## Provenance

The 19 files under `surfaces/`, `panels/` and `shell/` were moved here on
5 August 2026, when Work joined the orbit. They were already unreachable: the
production bundle was byte-identical before and after the move — same size, same
content hash — which is the proof they were never linked rather than an argument
that they should not be.

Three files stayed behind in `components/surfaces/`: `SurfaceBody`,
`SurfaceHeader` and `SurfaceToolbar` are shared layout primitives that the live
workspaces still use. Files moved here import them by `@/` path rather than
relatively, because the move changed their depth.

Moved out of `src/workspaces/` on 3 August 2026, along with the deletion of
`RuntimePanel.tsx` (which displayed fabricated telemetry under a "LIVE" badge) and the
seven zero-byte files in `src/accessibility/`.
