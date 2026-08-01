# Design System Audit

This document evaluates the current state of the Zaram design system.

## Current State

A complete, formal design system **does not exist**.

However, the foundations of a design system are present, scattered across the `src/theme` and `src/components/design-system` directories. The system is based on a set of design tokens consumed via CSS variables.

### Core Elements in Place:

- **Color System**: A robust color system is defined in `src/styles/default_theme.css` and consumed in `tailwind.config.js`. It correctly uses CSS variables and supports light/dark modes.
- **Glassmorphism**: A `glass` theme object (`src/theme/glass.ts`) defines the properties for the glass effect (background, border, blur, shadow), which is a core part of the visual identity.
- **Spacing & Radius**: Theme objects for spacing and border-radius exist, promoting consistency.
- **Typography**: A `typography.ts` file exists, but it is not fully implemented or enforced.
- **Components**: The `src/components/design-system` folder contains several pre-built components like `GlassPanel`, `SpatialButton`, and various cards. This is a good starting point.

### Major Gaps and Inconsistencies:

- **Incomplete & Unenforced**: The system is not comprehensive. Many components use one-off styles or hardcoded values (e.g., `SpatialBackground` hardcoding `oklch` values).
- **No Documentation**: There is no documentation or style guide, making it difficult for developers to use the system correctly.
- **No Formal Component Library**: The components in `src/components/design-system` are a good start, but they do not form a cohesive, well-documented library with standardized props and variants.

## Recommendation

**Formalize and enforce the existing system.**

Instead of adopting a new, external library, the best path forward is to build upon the strong foundation that already exists. The current system is bespoke to Zaram's unique aesthetic and is already integrated with the codebase.

### Action Plan:

1.  **Create a Style Guide**: Create a `DESIGN_SYSTEM.md` file that documents all the design tokens: colors, typography, spacing, radii, shadows, and motion presets.
2.  **Build a Component Library**:
    -   Move all reusable components into `src/components/design-system`.
    -   Standardize the props and variants for each component (e.g., `Button` should have `variant`, `size`, `state` props).
    -   Create stories for each component using a tool like Storybook or Ladle. This will provide interactive documentation and a sandbox for development.
3.  **Enforce Usage**:
    -   Establish a strict rule that all UI development must use the components and tokens from the design system.
    -   Refactor existing components (`RuntimeHUD`, `CommandPalette`, etc.) to exclusively use the design system.
    -   Add linting rules to detect hardcoded style values.
4.  **Expand the System**: Systematically create the missing components identified in the audit (e.g., a standardized `Input` field, `Tooltip`, etc.).

By formalizing the existing system, Zaram can maintain its unique visual identity while gaining the benefits of a true design system: consistency, reusability, and faster development.