# Frontend Plan — `apps/web`

Source of truth for visuals: `design/reference.html` (OpenDesign export, project
`dff69c9b-181c-40b9-8ee5-499cab192cd5`). It is a single-file vanilla
HTML/CSS/JS prototype. The port preserves look, layout, and interactions; markup
is restructured into React components, not copied verbatim.

Design read: developer portfolio for hiring managers, terminal / dark-tech
language, Next.js + Tailwind v4 + customized shadcn/ui.

Dials: `DESIGN_VARIANCE 6`, `MOTION_INTENSITY 5`, `VISUAL_DENSITY 4`.

## 1. Design tokens

Defined once in `src/styles/globals.css` as CSS variables, consumed through
Tailwind theme tokens (`@theme` / `--color-*`). Components never hardcode hex.

### Color

| Token | Value | Use |
|---|---|---|
| `--background` | `#0b0d10` | page background |
| `--panel` | `#0e1216` | panel fill |
| `--panel-2` | `#121820` | raised fill, status tiles |
| `--inset` | `#0a0c0f` | inset wells (composer, screenshots) |
| `--border` | `#232a33` | hairlines |
| `--border-hi` | `#333d49` | emphasized hairlines |
| `--text` | `#e8e8e8` | primary text |
| `--dim` | `#9aa4af` | secondary text |
| `--faint` | `#66717d` | tertiary text |
| `--accent` | `#ffb000` | single accent (amber) |
| `--accent-soft` | `rgba(255,176,0,.14)` | accent washes |
| `--ok` | `#3fb950` | success / completed |
| `--err` | `#ff6b6b` | error |

One accent, one palette. Light mode is out of scope: the reference is a
dark-terminal brand; `prefers-color-scheme` flipping would break it.

### Type

- Family: JetBrains Mono via `next/font` (`next/font/google`, weights 400/500/700),
  replacing the prototype's Google Fonts `<link>`.
- Base size: `clamp(14px, .35vw + 13px, 15.5px)`, line-height `1.65`.

### Space / shape / motion

- Spacing unit `8px`, radius `4px` (single radius scale), container `1000px`.
- `--dur: 200ms`, `--ease: cubic-bezier(.2,.7,.3,1)`.
- Elevation: no drop shadows; borders + `accent-soft` glows only.

## 2. Component inventory

### Primitives — `src/components/ui` (props in, JSX out)

| Component | Notes |
|---|---|
| `panel-cap` | `┌─ label ─── ┐` box-drawing caption, top/bottom variants |
| `suggestion-chip` | `[ ./projects ]` shortcut, a real `Link` to a path |
| `composer` | `> input + send` bar; disabled / hot (agent busy) states |
| `task-card` | project card: name, meta, status, desc, stack |
| `status-mark` | `✔ / ◐ / ◌` + label, `ok / accent / dim` color |
| `contact-row` | `key  value` row |
| `cursor` | blinking block caret |
| `reveal` | IntersectionObserver fade-up wrapper (client leaf) |
| `section-head` | `01  title ————` index + title + hairline rule |
| `typewriter` | sequential character reveal, fires `onComplete` once |

`section-head` and `reveal` exist because two sections needed the same markup;
`typewriter` exists because the landing intro types line by line and each line
must wait for the previous one.

### Features — `src/features/<name>` (components + hooks)

| Feature | Contents |
|---|---|
| `agent` | `AgentPanel` (console: full height on `/`, compact elsewhere so the path just opened is visible), `Landing` (typewriter intro + path shortcuts), `Message`, `useScriptedAgent` (busy, stream, greeting, scripted replies) |
| `background` | `CodeRain` (canvas client leaf, rAF with cleanup, static fallback under reduced motion), `Slideshow` (4 fake project shots) |
| `shell` | `Topbar` (route links), `Statusbar` (clock + current path), `BootOverlay` (skippable), `CrtOverlay` |
| `projects` | `ProjectsSection` from fixtures |
| `contact` | `ContactSection` from fixtures |
| `fs` | `FsView` (directory listing / file body / not-found message), `ListingRow` (one listing line, a real link) |

### Hooks — `src/hooks`

`use-reduced-motion` subscribes to the `prefers-reduced-motion` media query via
`useSyncExternalStore`. Components that only read it once on mount (the boot
overlay, the agent's stream) call `matchMedia` directly and import
`REDUCED_MOTION_QUERY` for the string, so they do not re-render on a setting
change they would ignore anyway.

### Content — `src/lib/api/fs.ts`

One typed tree, `FsNode = FsDir | FsFile`, with three exports and no React:

- `FS` — the tree, built from the project and contact fixtures plus the `about`,
  `skills` and `resume` prose, so none of that text exists twice.
- `allPaths()` — every path below the root, feeding `generateStaticParams`.
- `getNode(path)` — walks the tree one segment at a time, `null` when absent.
  Ignores empty segments, so a trailing slash in a shared link still resolves.

It mirrors the shape a backend `GET /fs` would return, so the swap touches only
this file. `getNode` is the one piece of logic worth testing, so `fs.test.ts`
covers it.

`chat.ts` imports the `RESUME` body from here for its scripted answer, which is
why the `# resume` heading lives in the file rather than in the shared string: a
chat reply should not open with a markdown heading.

### Data — `src/lib/api`

Typed fixtures only for now (`chat.ts`, `projects.ts`, `contact.ts`, `fs.ts`),
shapes match the future FastAPI responses so the swap touches only this folder:

- `chat.ts`: `ask(text) -> Promise<{ reply: string }>` (scripted matcher,
  mirrors prototype `REPLIES` + `FALLBACK`).
- `projects.ts`: `listProjects() -> Promise<Project[]>`.
- `contact.ts`: `getContact() -> Promise<Contact>`.

Every data-driven component handles loading / empty / error.

## 3. Routes

| Route | Content |
|---|---|
| `/` | console + `#projects` task cards + `#contact` panel |
| `/[...path]` | catch-all: one fs node per URL. `generateStaticParams` prerenders all 10 valid paths |
| `/health` | static ok payload, **no DB touch** (Neon scale-to-zero) |

Navigation is by link, never by typed command. The visitor moves through the
listing rows, the topbar and the landing shortcuts, all real `Link`s, so
middle-click, keyboard and the Back button behave. `.md` stays in the URL so the
URL, the listing and the file are one vocabulary with nothing to translate.

An unknown path renders `error: no file at <path>` rather than a 404, which
means it answers HTTP 200; `dynamicParams` is left at its default on purpose.

`AgentPanel` and the chrome live in the root layout, not in the pages. The
layout does not unmount on navigation, so moving between paths keeps the
conversation. The panel is full height on `/` and compact elsewhere, so the
folder or file that was just opened is visible without scrolling.

## 4. Build slices

1. Init: Next.js (App Router, TS, Tailwind v4) in `apps/web`, shadcn init,
   `next/font`, tokens in `globals.css`. Verify `bun dev`.
2. Shell: layout, `Topbar`, `Statusbar`, `BootOverlay`, `CrtOverlay`.
3. Primitives: `panel-cap`, `suggestion-chip`, `composer`, `task-card`,
   `status-mark`, `contact-row`, `cursor`, `reveal`.
4. Agent feature: panel + landing typewriter + scripted stream + `?bg=`
   background switcher.
5. Projects + contact features from fixtures.
6. `/health`, cleanup (no `console.log`, no unused imports, files < 150 lines).
7. URL-synced browsing: `lib/api/fs.ts` + `getNode` tests, then the catch-all
   route, then moving the console into the layout. Navigation is by link only —
   an earlier pass added a shell command registry (`ls`/`cd`/`cat`) and was
   removed as a digression from the assistant-TUI concept.

Each slice: `playwright-cli` screenshots at 1440x900 and 390x844 compared
against `design/reference.html`, gaps fixed, then commit.

## 5. Known tensions (recorded, not silently "fixed")

- `design-taste-frontend` bans em-dashes, `·` separators, and `01 / 02`
  section eyebrows; the reference uses all three. Fidelity wins for v1
  (match the approved design); copy cleanup goes through `docs/decisions/`
  before it changes what you already signed off.
- `high-end-visual-design` prescribes double-bezel cards and pill CTAs; the
  reference uses hairline borders and 4px radius. Reference wins.
- No new libraries beyond Next.js + Tailwind + shadcn/ui without an ADR in
  `docs/decisions/`.
- The shadcn **CLI** and `tw-animate-css` were removed from `dependencies` on
  2026-10-05. `@import "shadcn/tailwind.css"` supplied only `scroll-fade-*`,
  `shimmer*`, `no-scrollbar`, `accordion-*`, and `data-*` variants, none of
  which the app uses; the app's only animation utility, `animate-pulse`, is
  Tailwind v4 core. The CLI pulled 166 packages (babel, ts-morph, execa,
  express, the MCP SDK) into a static portfolio. `shadcn` is still reachable
  through `bunx shadcn@latest`, and `components.json` still configures it.
