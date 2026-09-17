# A.R.P.I.A. Visual Foundation

**Version:** 0.1.0  
**Status:** Foundational / evolving  
**Scope:** Visual identity and framework-agnostic design rules

---

## 1. Purpose

This document defines the initial visual language of A.R.P.I.A.

It establishes visual decisions that can be made independently of the
application's final functional scope and frontend technology.

It does **not** define:

- application functionality
- information architecture
- navigation
- workflows
- specific UI components
- dashboard composition
- map/COP behavior
- frontend framework
- implementation details

Those decisions remain open until the application requirements are defined.

---

## 2. Core visual direction

A.R.P.I.A. should communicate:

- aerospace
- intelligence
- analytical depth
- operational technology
- precision
- controlled information density

The intended result is a professional analytical/operational interface,
not a consumer product and not a decorative science-fiction interface.

The visual language should support complex information without making the
interface visually noisy.

---

## 3. Foundation palette

The interface is based on a very dark navy/black foundation.

| Token | Hex | Role |
|---|---|---|
| `arpia-void` | `#05040D` | Deepest background |
| `arpia-bg` | `#040C1D` | Main application background |
| `arpia-surface` | `#0F1B30` | Primary panels/surfaces |
| `arpia-elevated` | `#16243A` | Elevated surfaces, menus, overlays |
| `arpia-border` | `#233E4D` | Default borders/dividers |
| `arpia-border-active` | `#2B4B5D` | Active/emphasized borders |

Use the foundation hierarchy to establish depth before adding accent colors.

---

## 4. Brand palette

| Token | Hex | Role |
|---|---|---|
| `brand-deep` | `#003F5E` | Deep brand tone |
| `brand-primary` | `#3566CC` | Primary A.R.P.I.A. blue |
| `brand-electric` | `#1B68BC` | Strong technical blue |
| `brand-space` | `#54B1DC` | Space/cyan accent |

These colors should not be treated as interchangeable decorative colors.
Their semantic role should determine usage.

---

## 5. Phenomenon colors

A.R.P.I.A. has three conceptual phenomena. Their color associations are
semantic and should remain stable across future views.

### F1 — IA y Capacidades Estratégicas

**Color:** `#3566CC`

Represents information associated with artificial intelligence,
capabilities, strategic intelligence, or related analytical concepts.

### F2 — Seguridad del Entorno Espacial

**Color:** `#54B1DC`

Represents information associated with the spatial/orbital domain,
space security, satellites, or related concepts.

### F3 — Dinámicas Territoriales

**Color:** `#10B981`

Represents information associated with territory, geographic dynamics,
coverage, or related concepts.

### Consistency rule

If the same phenomenon appears in different parts of the application,
its semantic color should remain consistent.

Do not use F1/F2/F3 colors merely because they look visually attractive.

---

## 6. Semantic states

| Semantic meaning | Token | Hex |
|---|---|---|
| Success / operational | `success` | `#10B981` |
| Information | `info` | `#54B1DC` |
| Warning / attention | `warning` | `#F59E0B` |
| Critical / error | `critical` | `#EF4444` |

### Important distinction

F1/F2/F3 colors identify phenomena.

Semantic state colors identify system or information states.

These two concepts should not be conflated.

For example, F2 being cyan does not mean that every cyan element is
necessarily an "information" state. Context and semantic tokens determine
meaning.

---

## 7. Evidence / RAG

Amber `#F59E0B` is reserved as the primary visual language for evidence,
retrieval, references, citations, or attention-worthy supporting material
when those concepts are eventually implemented.

This is a semantic convention, not a requirement that the current
application already contain a RAG interface.

---

## 8. Critical state

Red `#EF4444` represents critical conditions, errors, or situations that
require attention.

Do not use red as a generic decorative accent or as a neutral data color.

---

## 9. Typography

The typography system is intentionally not locked to a specific font yet.

Recommended characteristics:

- highly legible sans-serif for normal interface text
- clear hierarchy
- compact but readable technical metadata
- monospace may be used selectively for telemetry, identifiers, logs,
  coordinates, code-like information, or machine-generated output

Do not introduce a "sci-fi" display font merely to make the interface feel
aerospace-oriented.

The visual identity should come primarily from composition, color, hierarchy,
density, and information design.

---

## 10. Visual density

A.R.P.I.A. is expected to handle analytical information.

Therefore:

- favor clear grouping over excessive whitespace
- maintain strong hierarchy
- avoid unnecessary decorative elements
- make dense information scannable
- use borders and surface changes deliberately
- reserve accent colors for meaningful information

Density should be controlled, not maximized.

---

## 11. Shape language

The exact component geometry is not yet fixed.

Until the functional UI is defined:

- prefer restrained corner radii
- avoid excessive "pill" shapes
- avoid excessive rounded cards
- use borders sparingly
- use elevation/subtle contrast rather than heavy shadows
- preserve a technical, structured appearance

Specific component-level radius, spacing, shadow, and interaction rules should
be defined later as part of the UI system.

---

## 12. Accessibility and contrast

Color should not be the sole mechanism for communicating meaning.

Important states should also have appropriate text, icons, labels, position,
shape, or other visual cues.

Use the lighter text tokens for readable text and reserve muted/disabled
tokens for genuinely lower-priority information.

The primary blue `#3566CC` should not be assumed to work as small text on
the darkest background merely because it is a brand color. When contrast is
insufficient, use it for larger graphical elements, borders, indicators,
icons, or other suitable applications.

---

## 13. Visualization principles

When analytical visualizations are eventually designed:

- use semantic colors consistently
- use sequential scales for magnitude
- use diverging scales only when the variable has meaningful negative,
  neutral, and positive values
- avoid assigning arbitrary colors to quantitative values
- do not allow legends or interface overlays to obscure important data
- adapt information progressively as users move between levels of detail

The exact charts, maps, and COP layers remain undefined until the analytical
requirements are established.

---

## 14. What is deliberately not defined yet

The following should **not** be considered part of the current visual
foundation:

- button variants
- card variants
- sidebar structure
- header structure
- chat layout
- agent cards
- RAG citation components
- KPI cards
- map controls
- COP layers
- timeline components
- dashboard grids
- navigation model
- page hierarchy
- responsive breakpoints
- frontend framework
- component library

These should be designed only after the application's purpose and user
workflows are sufficiently defined.

---

## 15. Evolution rule

This document is version `0.1.0`.

The system should evolve incrementally.

New decisions should:

1. preserve existing semantic meanings where possible;
2. avoid unnecessary new tokens;
3. remain independent from framework implementation when possible;
4. be documented when they become stable project decisions.

The goal is to give future designers and coding agents a stable visual
foundation without prematurely freezing the product's interface.
