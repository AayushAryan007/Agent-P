# AGENT-P — Design System and Screen Specification

Status: Phase 3 baseline. Last updated: 2026-10-27. Implemented in `frontend/src/styles/index.css` (tokens) and `frontend/src/components/` (components).

## 1. Direction (from `docs/design-references/`)

| Reference | What we take | What we leave |
|---|---|---|
| Control-AI policy platform (teal/black) | **Workspace layout**: graph canvas on the left, a dense inspector card on the right; glowing *selected* edge only; top toolbar of icon toggles | Large decorative orb |
| Toolnova agent workflows | **Dashboard grid**: KPI tiles row, agent list with status pills, logs and queue panels | Fake metrics, red glow everywhere |
| Data-flow architecture | Node cards with icon + label, solid edges for done, dashed for pending, color by kind | Code-panel decoration |
| Finova / Beaudia | Uppercase small-caps panel titles, thin 1 px borders, top navigation icons | Charts with no data source |
| Layered stack, InterLink, green fintech | Restraint: one accent glow per state | Neon saturation, globes, glassmorphism |

Principles: **status is the color system** (accents carry meaning, never decoration); every number shown is backed by data; the graph only moves when an event arrives.

## 2. Tokens

### Surfaces and text
| Token | Value | Use |
|---|---|---|
| `--bg` | `#06080F` | App background |
| `--surface-1` | `#0B1020` | Panels |
| `--surface-2` | `#10172A` | Raised: cards in panels, inputs, nodes |
| `--surface-3` | `#162038` | Hover, selected rows |
| `--border` | `#1C2740` | Default 1 px borders |
| `--border-strong` | `#2A3A5C` | Focused inputs, selected nodes |
| `--text` | `#E7ECF6` | Primary text (15.9:1 on bg) |
| `--text-2` | `#A3AFC6` | Secondary (8.4:1) |
| `--text-3` | `#6F7C96` | Muted labels, timestamps (4.6:1 — AA for ≥ 14 px) |

### Status and semantic accents
| Token | Value | Meaning |
|---|---|---|
| `--blue` | `#4C8DFF` | **Running**, primary action, links |
| `--violet` | `#9B87FF` | LLM / agent reasoning |
| `--cyan` | `#2BD4E3` | Tool invocations, sandbox |
| `--green` | `#34D399` | Completed, Verified |
| `--amber` | `#F5B544` | Waiting for approval, Partially verified, warnings |
| `--red` | `#F2617A` | Failed, Not verified, errors |
| `--slate` | `#6F7C96` | Pending, cancelled, skipped |

Each accent has a `-soft` variant (12% alpha) for badge backgrounds and a glow (`0 0 0 1px accent, 0 0 18px accent/35%`) used **only** on running and selected elements.

### Status mapping (single source: `src/domain/status.ts`)
| Status | Color | Icon | Motion |
|---|---|---|---|
| pending | slate | `Circle` (dashed) | none |
| running | blue | `Loader` | slow pulse on node ring (respects `prefers-reduced-motion`) |
| waiting_approval | amber | `Hand` | static ring |
| completed | green | `CheckCircle2` | 200 ms fill transition |
| failed | red | `XCircle` | single shake-free flash |
| cancelled / skipped | slate | `Ban` / `SkipForward` | none |

### Type, spacing, shape
- Fonts: **Inter Variable** (UI), **JetBrains Mono Variable** (ids, code, durations, numbers in tables).
- Scale: 11 (panel caps labels, +0.08em tracking), 12, 13 (default dense UI), 14, 16, 20, 28 (KPI values, tabular nums).
- Spacing: 4 px base; panel padding 16; gaps 12/16/24.
- Radius: 6 (controls), 10 (panels), 999 (pills). Borders 1 px; no drop shadows except overlays.
- Motion: 150–250 ms ease-out; nothing loops except the running indicator.

## 3. Information architecture

```
/                         Dashboard
/tasks/new                New Task
/runs                     Runs list (filter by status)
/runs/:runId              Run workspace — live if active, "Recorded" replay if terminal
/runs/:runId/report       Final results
/settings                 Providers, defaults (operator)
/dev/preview              Design preview with ILLUSTRATIVE fixture data (dev builds only)
```

Shell: left icon rail (64 px; labels on hover/tooltip) — Dashboard, Runs, New Task, Settings; top bar with breadcrumb, backend connection indicator, and role chip (Viewer / Operator · sign in).

## 4. Screens

### Dashboard
Row 1: KPI tiles — Runs (window), Success rate, Avg duration, Tokens used, Pending approvals. Each tile shows "—" with a hint when there is no data. Row 2: Recent runs table (status, task, duration, label, started) | Attention panel (failed runs, pending approvals). Row 3: Templates with "Start" action. Primary CTA **New task** in the top bar.

### New Task (two columns)
Left: goal textarea, template cards, repository source (segmented: Bundled demo | GitHub URL with validation), model select, limits (number inputs with server maximums). Right (sticky): **Authorization summary** — tools this run may call, where code runs (network-less sandbox), what needs your approval, budgets. Start button disabled until valid; operator-only.

### Run workspace (signature screen)
```
┌ top bar: task title · run status · elapsed · tokens · [2D|3D] · [Cancel] ──────────────────┐
├ Steps (260) ──┬ Agent graph (flex) ─────────────────────────────────┬ Inspector (380) ─────┤
│ status list   │ React Flow + ELK, left→right DAG                     │ tabs: Overview,      │
│ of run_steps  │ nodes: role icon, title, status ring, timer, tokens  │ Tool calls, LLM,     │
│ + approvals   │ edges: solid done / animated dash running / dim      │ Output               │
│               ├──────────────────────────────────────────────────────┤ approval card when   │
│               │ Timeline (240, resizable) — virtualized event list   │ waiting              │
└───────────────┴──────────────────────────────────────────────────────┴──────────────────────┘
```
Terminal runs show a replay bar (play/pause, 0.5×–8×, scrubber) and a **Recorded** badge. Narration (`agent.message`) is visually distinct (violet left rule, italic "Model narration") from recorded facts.

### Results
Header with the verification label and the rule that produced it. Sections: problem, root cause, patch with file-by-file diff, tests before/after, benchmark before/after, evidence (links to tool invocations/events), limitations, next steps.

## 5. Component inventory and states

| Component | States |
|---|---|
| `Panel` (title caps label, actions slot) | default, loading (skeleton), empty, error |
| `StatTile` | value, empty ("—" + hint), loading |
| `StatusBadge` | every status above + verification labels |
| `Button` | primary, secondary, ghost, danger; disabled, loading |
| `EmptyState` / `ErrorState` | icon, title, body, action; `ErrorState` shows problem+json `title`/`detail` and `request_id` |
| `AgentNode` | per status; selected; focus-visible ring; keyboard: Tab between nodes, Enter selects |
| `TimelineRow` | per event family color; selected; narration style |
| `ConnectionIndicator` | connected, reconnecting (amber), offline (red) |

Accessibility: all interactive elements reachable by keyboard with a visible `--blue` focus ring; status never conveyed by color alone (icon + text); motion disabled under `prefers-reduced-motion`.
