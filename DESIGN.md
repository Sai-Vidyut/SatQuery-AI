# SatQuery Design Specification

**Product:** SatQuery AI  
**Surface:** Working geospatial intelligence workstation (not a landing page, not a marketing site)  
**Audience:** Smart India Hackathon 2026 judges, analysts, and demo operators  
**Status:** Design specification only. No application code in this document.

---

## Design Read

Reading this as: a professional geospatial intelligence workstation for technical evaluators, with an aerospace-precision dark language, leaning toward a custom map-first overlay system (Tailwind tokens + MapLibre + Phosphor). Not Carbon, not Fluent, not a SaaS dashboard kit, not a marketing aesthetic.

**Dials (product overrides Taste Skill defaults of 8 / 6 / 4):**

| Dial | Value | Why |
|---|---|---|
| `DESIGN_VARIANCE` | 3 | Workstation predictability beats artsy asymmetry. Operators must find the same control in the same place every time. |
| `MOTION_INTENSITY` | 3 | Motion is feedback, not spectacle. Analysis already takes time; the UI must feel stable. |
| `VISUAL_DENSITY` | 8 | Cockpit density. The map is the canvas. Chrome is compact. Metrics are tabular, not gallery-airy. |

---

## Skill Reconciliation

SatQuery product requirements outrank generic skill examples. Skills were used as filters, not as templates.

| Skill | Keep | Reject / override |
|---|---|---|
| **Taste Skill** (`design-taste-frontend`) | Anti-slop bans, one accent, no Inter-by-default, no em-dashes in UI copy, Phosphor icons, WCAG contrast, empty/loading/error completeness, compositor-only motion, `prefers-reduced-motion` | Landing-page dials, hero typography, bento grids, GSAP scroll hijacks, AIDA structure, `max-w-7xl` page containment, “glass is inappropriate for dashboards” (user explicitly wants selective glass overlays) |
| **Web Design Guidelines** (Vercel) | All of it: labels, focus-visible, skip link, `tabular-nums`, `Intl.*`, URL-reflected state, `prefers-reduced-motion`, `transform`/`opacity` only, no `transition: all`, no `outline-none` without replacement, 44px touch, `color-scheme: dark` | None. These are product rules. |
| **Glassmorphism** (`bergside` / TypeUI) | Technique: `backdrop-filter`, luminous 1px edge, inset highlight, solid fallback for `prefers-reduced-transparency` | Light consumer palette (`#1856FF`, white surfaces), Plus Jakarta Sans, comfortable-density spacing, bento cards, full-UI translucency |
| **Image-to-Code** | Anti-nested-cards, anti-pill spam, anti-fake-dashboard, keep hero/chrome clean | Image-first marketing workflow, section-per-image landing comps, Codex section boards. This spec is the source of truth, not generated marketing frames. |
| **Playwright CLI** | Flagship flow is a testable script: AOI → dates → query → trace → detections → evidence. Keyboard and pointer paths required. | Playwright does not dictate visual style. |
| **gpt-taste / high-end-visual-design** | Phosphor, GPU-safe motion, blur only on fixed overlays | AIDA, giant display type, double-bezel 2rem squircles, purple mesh orbs, perpetual micro-loops, island-pill nav |
| **Industrial brutalist** | High density, mono for telemetry, cool dark substrate, single accent discipline | Scanlines, CRT phosphor, ASCII frames, zero-radius everywhere, giant viewport type, hazard-red as default accent |

**Foundation (honest):** custom aesthetic, not an official design-system package. Build with native CSS custom properties + Tailwind v4 utilities. Use Radix primitives only if a dialog, popover, or tooltip needs accessible behavior. Do not install Carbon, Fluent, shadcn kit-wide, GSAP, or decorative animation libraries.

---

## A. SatQuery Visual Design System

### 1. Visual identity

SatQuery is a **map workstation**. The brand is the imagery and the evidence, not a logo lockup.

- **Character:** ISRO / Airbus / Palantir-Gotham adjacent in *discipline*, not in decoration. Quiet, technical, evidence-first.
- **Primary surface:** full-viewport satellite imagery. UI floats over it. UI never replaces it.
- **Secondary surface:** compact instrument chrome (rail, composer, inspector). These are tools, not content.
- **Tone of voice:** short, operational, second person. “Run analysis.” “Open evidence.” Never “Unleash insights.”
- **Mark:** wordmark `SATQUERY` in IBM Plex Sans Medium, 13px, letter-spacing 0.08em, uppercase. Optional thin amber tick (4×12px) to the left of the word. No orbit icons, no 3D globes, no neural-net glyphs.

Theme is **dark only**. No light-mode section, no theme toggle for the hackathon build. `color-scheme: dark` on `:root`.

### 2. Color system

One substrate family: **cool ink**. One accent: **detection amber**. Semantic colors exist only for state, never as a second brand.

Saturation of the accent stays under 80%. No purple. No electric cyan glow. No mesh gradients.

| Token | Hex / value | Role |
|---|---|---|
| `void` | `#0B0D10` | Page root behind the map (seen only at edges / load) |
| `ink` | `#12151A` | Solid chrome fallback, collapsed rail, inspector body |
| `panel` | `#1A1F27` | Elevated solid surfaces (menus, dropdowns) |
| `line` | `rgba(232, 236, 242, 0.10)` | Hairline borders |
| `line-strong` | `rgba(232, 236, 242, 0.18)` | Active / focused chrome edges |
| `text` | `#E8ECF2` | Primary labels, query text |
| `text-muted` | `#9AA3B2` | Secondary labels, timestamps, helper |
| `text-faint` | `#6B7380` | Disabled, placeholders (must still pass 4.5:1 on `ink`) |
| `amber` | `#C9A227` | Single accent: primary CTA, AOI stroke, selected detection, focus ring |
| `amber-dim` | `rgba(201, 162, 39, 0.16)` | Accent wash, selected row, confidence fill track |
| `success` | `#3D9A6A` | Completed pipeline step, confirmed change |
| `warning` | `#C47A2C` | Partial evidence, stale imagery, date mismatch |
| `danger` | `#C44C4C` | Failed step, blocking error |
| `map-aoi` | `#C9A227` | AOI polygon stroke (2px). Fill `rgba(201, 162, 39, 0.14)` |
| `map-detection` | `#C9A227` | Detection polygon stroke. Fill opacity encodes confidence (see §15) |

**Rules**

- Accent appears on: Run Analysis, selected AOI, selected detection, focus ring, confidence fill.
- Success / warning / danger never appear as large fills. They are 8px status marks + text.
- Do not tint the map. Imagery stays true-color (or true grayscale if the source is SAR). Overlay color is chrome and vectors only.
- Hover / active states increase contrast, they do not add glow.

### 3. Typography

Self-host via `next/font` or `@font-face` + `font-display: swap`. Never a Google Fonts `<link>`.

| Role | Family | Weight | Size | Line | Tracking | Use |
|---|---|---|---|---|---|---|
| UI | IBM Plex Sans | 400 / 500 | 13px | 1.35 | 0 | Labels, buttons, inspector body |
| UI small | IBM Plex Sans | 500 | 11px | 1.3 | 0.04em | Section labels, layer names |
| Query | IBM Plex Sans | 400 | 14px | 1.4 | 0 | Query composer input |
| Telemetry | IBM Plex Mono | 400 / 500 | 11–12px | 1.3 | 0 | Coordinates, dates, IDs, confidence %, timestamps |
| Wordmark | IBM Plex Sans | 500 | 13px | 1 | 0.08em | `SATQUERY` |

**Scale (compact workstation, not marketing display)**

- There is no display / hero size. Largest UI type is 16px (inspector title).
- Numbers that compare use `font-variant-numeric: tabular-nums`.
- Headings use `text-wrap: pretty`.
- UI copy uses typographic quotes `“ ”` and ellipsis `…`. Never em-dashes in visible strings. Use a hyphen or a new sentence.
- Serif is banned. Inter is banned. Plus Jakarta Sans is banned (Glassmorphism default, wrong character).

### 4. Spacing scale

Base unit: **4px**. Density 8 means tight chrome, not cramped map.

```
space-1  4px
space-2  8px
space-3  12px
space-4  16px
space-5  24px
space-6  32px
```

| Context | Rule |
|---|---|
| Rail item | 8px vertical pad, 10px horizontal, 8px icon gap |
| Panel pad | 12px |
| Composer pad | 10px 12px |
| Inspector section | 12px pad, 8px between rows |
| Map control cluster | 8px gap between buttons |
| Overlay inset from viewport | 12px (plus `env(safe-area-inset-*)`) |

Do not use marketing section padding (`py-24`, `py-32`). This is a single viewport, not a scrolling brochure.

### 5. Border radius system

Shape lock (documented exception to “all one radius”):

| Token | Value | Applies to |
|---|---|---|
| `radius-sm` | 4px | Buttons, inputs, icon controls, chips |
| `radius-md` | 8px | Panels, menus, inspector, trace |
| `radius-lg` | 12px | Query composer shell only |

No pills (`rounded-full`) except the circular map zoom buttons (20×20 hit target is too small; use 36×36 squares with `radius-sm` instead). No 24px squircles. No mixed “soft card + pill button” without this table.

### 6. Glass / material system

Glass is an **overlay material**, not a theme.

**Use glass for:** floating map controls, query composer, compact inspector when it floats over the map, AOI tooltip, layer popover.

**Never glass:** the map itself, the collapsed icon rail background if it sits off-map, modal scrims, error toasts (solid `panel`), evidence image frames.

**Glass recipe (approximation, not Apple Liquid Glass):**

```css
.glass {
  background: rgba(18, 21, 26, 0.72);
  backdrop-filter: blur(16px) saturate(1.2);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  border: 1px solid rgba(232, 236, 242, 0.12);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 8px 24px rgba(0, 0, 0, 0.35);
}
```

**Fallbacks**

```css
@media (prefers-reduced-transparency: reduce) {
  .glass { background: #12151A; backdrop-filter: none; }
}
```

Blur only on `position: fixed` / `sticky` overlays. Never on scrolling containers or the map canvas (GPU cost).

### 7. Shadows and depth

Depth comes from the map (real imagery) plus 2 overlay levels.

| Level | Treatment |
|---|---|
| L0 Map | No shadow. Full bleed. |
| L1 Chrome | Glass recipe above. Shadow tinted to void, never pure-black bloom. |
| L2 Popover / menu | Solid `panel` + same inset highlight + `0 12px 32px rgba(0,0,0,0.45)` |

No neon outer glow. No stacked card shadows. No double-bezel trays.

### 8. Iconography

- Family: **Phosphor** (`@phosphor-icons/react`), regular weight, stroke 1.5, 16px in chrome, 20px in map controls.
- One family only. No Lucide, no Material, no mixed sets, no hand-rolled decorative SVGs.
- Icon-only controls require `aria-label`. Decorative icons `aria-hidden="true"`.
- No emoji in UI, code, or copy.

Suggested glyphs (do not invent new metaphors):

| Action | Icon |
|---|---|
| Pan | `Hand` |
| Draw AOI | `Polygon` / `BoundingBox` |
| Layers | `Stack` |
| Query | `MagnifyingGlass` |
| Run | `Play` |
| Trace | `TreeStructure` |
| Evidence | `Image` |
| Confidence | none (use the meter, not an icon) |
| Zoom in/out | `Plus` / `Minus` |
| Collapse rail | `CaretLeft` |

### 9. Motion / animation principles

Motion answers one of: **feedback**, **state change**, **hierarchy**. If it cannot be named in those terms, drop it.

| Event | Motion |
|---|---|
| Overlay mount | opacity 0→1, 140ms, `cubic-bezier(0.2, 0.8, 0.2, 1)` |
| Inspector open | panel translates from the right 12px + fade, 180ms |
| Detection appear | polygon opacity 0→fill, 200ms stagger ≤ 40ms per feature, cap 8 features then appear together |
| Trace step complete | label color change, no bounce |
| Button active | `scale(0.98)`, 80ms |
| Analysis running | composer Run button shows “Running…”; trace rows fill in. No map pulse. |

**Hard rules (Web Guidelines + Taste)**

- Animate `transform` and `opacity` only.
- Never `transition: all`.
- Honor `prefers-reduced-motion: reduce`: instant opacity, no stagger, no scale.
- Interruptible: user input cancels in-flight UI animation.
- No infinite loops, no shimmer on the map, no orbiting loaders, no GSAP scroll, no magnetic hover.

### 10. Map styling

The map is not a “widget in a card.” It is the application background.

- Engine: **MapLibre GL JS** (raster satellite basemap + GeoJSON overlays). Do not wrap it in a rounded card or max-width container.
- Basemap: true-color optical when available. Labels: none, or a sparse reference overlay the user can toggle off (default **off** so detections read against imagery).
- Attribution: required, bottom-left, 10px mono, 60% opacity, never covered by controls (offset controls 12px above attribution).
- Cursor: grab / grabbing for pan. Crosshair while drawing AOI. Pointer on detections.
- AOI: amber stroke 2px, fill 14% opacity, vertex handles 8px squares (`radius-sm`), not circles.
- Detections: amber stroke 1.5px. Fill opacity = `0.08 + 0.32 * confidence` (so 0.4 confidence ≈ 0.21 fill). Selected: stroke 2.5px, fill +0.10.
- No 3D buildings, no atmosphere glow, no globe projection for the hackathon MVP (2D mercator).
- Compare dates with a **swipe or side-by-side toggle** inside the inspector evidence pane, not as a gimmicky map split unless the user asks. Default: detections on the later date.

### 11. Button / input styles

**Buttons**

| Variant | Fill | Text | Border | Use |
|---|---|---|---|---|
| Primary | `amber` | `#12151A` | none | Run Analysis (one primary per view) |
| Secondary | transparent | `text` | `line` | Cancel, Close, Reset AOI |
| Ghost | transparent | `text-muted` | none | Rail items, map tools |
| Danger | transparent | `danger` | `danger` 1px | Discard run |

Height 32px in chrome, 36px for map tools. Horizontal pad 10px. Label one line, Title Case, specific: “Run Analysis” not “Continue”. Active: scale 0.98. Hover: increase border to `line-strong` or darken amber 8%. Disabled: 40% opacity, not clickable, no pointer.

Primary text on amber must pass 4.5:1 (`#12151A` on `#C9A227` does). Never white text on amber.

**Inputs**

- Label above, 11px, `text-muted`. Error below, 11px, `danger`.
- Height 32px. Background `rgba(0,0,0,0.28)` on glass, `panel` on solid. Border `line`. Focus: 2px `amber` ring via `:focus-visible` only. Never `outline: none` without that ring.
- No placeholder-as-label. Placeholders end with `…` and show a pattern: `Show significant new construction…`
- `spellCheck={false}` on IDs, coordinates, query field.
- Dates: native `type="date"` or a compact dual date field labeled “Earlier” and “Later”, `Intl.DateTimeFormat` for display.
- `autocomplete="off"` on non-auth fields.

### 12. Chat / query composer

This is **not a chatbot**. No avatar, no bubble thread, no “Ask anything”, no suggested-prompt chips wall.

It is a **structured command bar** docked bottom-center (desktop) over the map.

**Anatomy (single row, wrapping to two rows only below 1024px):**

1. AOI status: `AOI · 2.4 km²` or `Draw AOI` (ghost)
2. Earlier date
3. Later date
4. Query field (flex grow)
5. Primary: `Run Analysis`

Collapsed height: 52px including padding. Max width: 920px. `radius-lg` glass shell.

Empty query + missing AOI: Run stays enabled until click, then inline errors on the missing pieces (Web Guidelines: do not disable before the request starts; validate on submit).

After a run, the composer stays. Results do not turn into a chat transcript. A one-line status sits above the composer: `12 regions · 18.4s · 2024-01-12 → 2025-03-03`.

Keyboard: `⌘K` / `Ctrl+K` focuses the query field. `Esc` clears selection, not the AOI.

### 13. Analysis execution trace

A compact vertical log, not a spinner, not a marketing “AI thinking” animation.

**Placement:** left edge of the inspector, or a slim 240px column above evidence when the inspector is open. Not a modal.

**Row anatomy:**

```
[mark]  Acquire imagery          1.2s
[mark]  Align & difference       4.8s
[mark]  Detect change            9.1s
[mark]  Score regions            3.3s
```

- Mark: 6px square. `text-faint` pending, `amber` running (static, not pulsing), `success` done, `danger` failed.
- Label: 12px Sans. Duration: 11px Mono, `tabular-nums`, right-aligned.
- Running row: `aria-live="polite"` on the trace region. Text: `Detecting change…`
- Failed row: label + one-line fix: `Acquire imagery failed. Check AOI coverage.`
- No fake precise substeps. Only real pipeline stages.
- User can collapse the trace to a single summary line after success.

### 14. Evidence inspector

Right-side sheet, 380px desktop (420px if evidence imagery needs it), glass when overlapping the map, solid `ink` if it docks.

**Does not cover the selected detection.** Map recenters / pads so the polygon stays visible left of the sheet.

**Sections, top to bottom (no cards inside cards):**

1. Header: `Region 07` (16px) + close. Subline: coordinates in Mono.
2. Confidence meter (see §15)
3. Pair viewer: Earlier | Later imagery, same crop, swipe or two-up. Explicit `width`/`height` on images. Captions: dates, not “before/after” poetry.
4. Metrics list (not a card grid): area, change magnitude, persistence, cloud cover. Label left, value right, Mono values, hairline between rows. Max 6 rows.
5. Supporting text: 2–3 sentences max, evidence-based. If the model is uncertain, say so.
6. Actions: `Focus on map` (secondary), `Export region` (secondary). One primary is already Run Analysis in the composer.

Empty inspector: “Select a region on the map.” plus a 1-line hint. No illustration.

### 15. Confidence indicators

Confidence is a **number plus a meter**, never a colored dot, never a traffic-light pill, never a circular gauge.

- Display: `74%` in IBM Plex Mono 13px tabular, labeled `Confidence` 11px muted.
- Meter: 3px track `amber-dim`, fill `amber`, width = percentage. Height 3px, `radius-sm`.
- Bands (text, not extra color): `High` ≥ 75, `Medium` 45–74, `Low` < 45. Band is text beside the number, same `text-muted`.
- Map fill opacity is the spatial encoding of the same number (see §10). Do not add a second color scale.
- Never invent `99.9%`. Show the model’s value, one decimal max, or integer percent.

### 16. Layer controls

Floating cluster, **top-right**, vertical stack, 36×36 ghost-glass buttons.

Order (top to bottom): Layers, Basemap, Labels, Zoom in, Zoom out, Recenter AOI.

Layers popover (solid `panel`, 220px):

- Checkboxes with a single hit target (label + control).
- Items: Detections, AOI, Reference labels, Earlier imagery (if compare).
- No nested folders for MVP.

Do not put a mini-map. Do not put a compass unless north-up can be rotated (it cannot in MVP).

### 17. Empty / loading / error states

| State | Treatment |
|---|---|
| No AOI | Map idle. Composer shows `Draw AOI`. Ghost hint on map, bottom-left, 12px: `Draw an area to analyze`. Dismisses after first draw. |
| AOI, no run | AOI visible. Run is the only accent. |
| Running | Trace visible. Map interaction still allowed (pan/zoom). Detections hidden until stage “Score regions” completes. Composer button label `Running…` with spinner **inside the button**, not a page overlay. |
| Success, 0 regions | Inspector: `No significant change in this AOI for the selected dates.` Next step: `Widen the date range or AOI.` |
| Success, N regions | Polygons appear. Inspector lists count. First region not auto-opened (user chooses). |
| Partial failure | Trace shows failed stage. Completed stages remain. Error includes the fix. |
| Imagery missing | Warning text in composer: `Later date has no clear scene. Pick another date.` |
| Network error | Solid toast, `aria-live="assertive"`, `Retry` action. Does not cover the map center. |

Skeletons: only in inspector metric rows and trace rows. Shape-matched. No circular page spinner. No skeleton over the map (the map is already the visual).

### 18. Responsive behavior

This product is **desktop-first** (demo + analyst). Mobile is a constrained operator mode, not a second product.

| Breakpoint | Layout |
|---|---|
| ≥ 1280px | Rail 48px icons + 200px expanded optional. Composer bottom-center. Inspector 380px right. Trace in inspector. |
| 1024–1279px | Rail icons only (48px). Composer two rows. Inspector 340px. |
| 768–1023px | Rail becomes bottom toolstrip (56px). Inspector is a bottom sheet (50vh) over the map. Composer sits above the sheet. |
| < 768px | Same as tablet, full-width sheets. Map remains 50%+ of `100dvh`. Touch targets ≥ 44px. `env(safe-area-inset-*)`. |

Never `h-screen`; use `100dvh`. No horizontal page scroll. Map canvas handles its own pan.

AOI drawing: mouse on desktop; equivalent tap-to-place vertices on touch, with a `Complete AOI` button (gesture-only is banned).

### 19. Accessibility requirements

Must be testable. See also Section I.

- WCAG 2.2 AA contrast on all chrome text, including muted labels on glass (if glass fails, increase opacity or use the solid fallback).
- Skip link: “Skip to map”.
- Heading order: `h1` SatQuery (visually the wordmark), `h2` Query, `h2` Results, `h3` region titles.
- Keyboard: Tab through rail → map tools → composer → inspector. Map drawing has a non-pointer path: “Enter bounding box as minLon, minLat, maxLon, maxLat”.
- `:focus-visible` amber ring, 2px offset. Sticky overlays must not cover focused elements (`scroll-margin` / pad map).
- `aria-label` on every icon button. Trace is `aria-live="polite"`. Errors `assertive`.
- Images in evidence: meaningful `alt` (`Later scene, 3 Mar 2025, region 07`).
- Do not disable zoom (`user-scalable=no` banned).
- `touch-action: manipulation` on buttons.
- Reduced motion and reduced transparency as specified.

### 20. Explicit design anti-patterns

Banned in SatQuery:

- Purple / blue mesh gradients, aurora blobs, glowing borders
- Entire UI made of glass
- Giant hero text, centered marketing layout, AIDA, bento, 3 equal cards
- Chatbot column, message bubbles, avatar, “suggested prompts” chip clouds
- Status dots, pill tags, fake badges (`BETA`, `LIVE`, `v1.0`)
- Decorative 3D globes, orbit rings, neural graphs, stock photos of analysts
- Nested cards, dashboard KPI tiles above the map, sparkline wallpaper
- Inter, Plus Jakarta Sans, Fraunces, Instrument Serif
- Em-dashes in UI copy
- Emoji
- `transition: all`, layout animations, infinite pulse on detections
- Fake metrics (`99.9%` accuracy, `4.1×` faster)
- Copy: Unleash, Seamless, Next-gen, Insights at your fingertips, Empower
- Covering the selected region with the inspector
- Disabling map pan while a panel is open

---

## B. Workspace Layout Specification

Full viewport. No site header. No marketing nav.

```
┌──────────────────────────────────────────────────────────────────┐
│ [rail]  MAP (full bleed satellite imagery)          [layers]     │
│  48px                                                    36px    │
│                                                                  │
│         AOI polygon                                              │
│         detection polygons                                       │
│                                                                  │
│                    [inspector 380px, when open]                  │
│                    trace + evidence                              │
│                                                                  │
│              ┌──────── query composer 920px ────────┐            │
│              │ AOI │ date │ date │ query │ Run      │            │
│              └──────────────────────────────────────┘            │
│  attribution                                                     │
└──────────────────────────────────────────────────────────────────┘
```

**Rail (left)**  
Fixed, 48px collapsed. Items, top to bottom: Wordmark tick, Draw AOI, Pan, Projects (optional later), Settings (optional). Bottom: docs/about as a text button, not a second product. Default collapsed. Hover/click expands to 200px with 11px labels. Does not push the map; it overlays.

**Map**  
`position: absolute; inset: 0`. z-index 0.

**Floating controls**  
z-index 20. Top-right layer cluster. Bottom-left attribution. Bottom-center composer (z-index 30).

**Inspector**  
z-index 25. Right overlay. Opens only after a run or when a detection is selected.

**z-index lock**

| Layer | z |
|---|---|
| Map | 0 |
| AOI draw handles | 5 |
| Rail | 20 |
| Map controls | 20 |
| Inspector | 25 |
| Composer | 30 |
| Popovers / menus | 40 |
| Toast | 50 |
| Focus ring | native |

**Flagship layout sequence**

1. Idle: map + rail + composer + layers. Empty hint.
2. User draws AOI: amber polygon, composer AOI chip updates area.
3. User sets dates and query, runs.
4. Trace appears in a slim inspector (trace-only, 280px).
5. On complete: detections draw; inspector expands to 380px with region list (simple list, not cards). Count in composer status line.
6. User clicks a polygon or a list row: evidence section fills; map pads left.

URL state (Web Guidelines): `?bbox=&from=&to=&q=&run=&region=`. Deep-link a completed demo run.

---

## C. Component Inventory

Build only these. No placeholder component library dump.

**Shell**

- `AppWorkspace`
- `IconRail`
- `MapViewport`
- `MapAttribution`

**Map chrome**

- `MapToolCluster`
- `LayerPopover`
- `AoiDrawController`
- `DetectionLayer`
- `AoiLayer`

**Query**

- `QueryComposer`
- `AoiStatus`
- `DatePairFields`
- `RunButton`

**Analysis**

- `ExecutionTrace`
- `TraceRow`
- `ResultsStatusLine`
- `RegionList`

**Evidence**

- `EvidenceInspector`
- `ConfidenceMeter`
- `ScenePairViewer`
- `MetricsList`

**Feedback**

- `InlineError`
- `Toast`
- `EmptyHint`
- `SkeletonRows`

**Do not build in MVP:** dashboard home, landing, pricing, team avatars, notification bell, theme switch, KPI row, chat history sidebar, 3D globe, settings forest.

---

## D. Component States

Every interactive component implements the relevant subset of: default, hover, focus-visible, active, disabled, loading, error, empty.

| Component | default | hover | focus-visible | active | disabled | loading | error | empty |
|---|---|---|---|---|---|---|---|---|
| `RunButton` | amber | darker amber | ring | scale 0.98 | 40% after submit starts | “Running…” | n/a | n/a |
| `QueryComposer` input | glass field | line-strong | ring | n/a | n/a | n/a | inline below | placeholder |
| `AoiStatus` | “Draw AOI” | underline | ring | n/a | n/a | n/a | “AOI required” | same as default |
| `DatePairFields` | dates or empty | line-strong | ring | n/a | n/a | n/a | “Later must be after earlier” | empty |
| `IconRail` item | ghost | text brightens | ring | ink wash | n/a | n/a | n/a | n/a |
| `MapToolCluster` | glass 36 | line-strong | ring | scale 0.98 | n/a | n/a | n/a | n/a |
| `LayerPopover` checkbox | unchecked | n/a | ring on group | n/a | n/a | n/a | n/a | n/a |
| `ExecutionTrace` | hidden | n/a | n/a | n/a | n/a | rows pending→running | failed row | n/a |
| `TraceRow` | pending faint | n/a | n/a | n/a | n/a | amber mark | danger + fix | n/a |
| `RegionList` row | hairline row | amber-dim wash | ring | selected wash | n/a | skeleton | n/a | “No regions” |
| `DetectionLayer` feature | opacity by confidence | stroke +0.5px | keyboard equivalent via list | selected 2.5px | n/a | hidden | n/a | none |
| `EvidenceInspector` | closed | n/a | trap focus when open | n/a | n/a | skeletons | inline | “Select a region” |
| `ConfidenceMeter` | % + bar | n/a | n/a | n/a | n/a | skeleton bar | hide if null | “—” with explanation |
| `ScenePairViewer` | two-up | n/a | ring on swipe handle | dragging | n/a | image skeleton | “Scene unavailable” | n/a |
| `Toast` | hidden | n/a | action focus | n/a | n/a | n/a | assertive | n/a |

Unsaved AOI / query: warn before leaving (`beforeunload` or router guard) if a run is in progress.

---

## E. Interaction / Motion Specification

### Flagship flow

```text
Idle
  → Draw AOI (click-drag box or click vertices + Complete)
  → Set Earlier date, Later date
  → Type: Show me significant new construction.
  → Submit Run Analysis
  → Trace stages complete in order
  → Polygons appear on later imagery
  → Click region 07
  → Inspector shows pair, confidence, metrics
  → Esc or Close returns to region list, AOI preserved
```

### Timing

| Interaction | Duration |
|---|---|
| Overlay fade | 140ms |
| Inspector enter | 180ms |
| Button press | 80ms |
| Detection stagger | 200ms, max 8 |
| Toast | 4s, pause on hover |

Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)` for enter. `cubic-bezier(0.4, 0, 1, 1)` for exit. No linear. No spring libraries required.

### Keyboard

| Key | Action |
|---|---|
| `⌘K` / `Ctrl+K` | Focus query |
| `Enter` | Run (when composer focused and valid) |
| `Esc` | Close popover / inspector / cancel draw |
| `A` | Draw AOI tool |
| `L` | Layers |
| `+` / `-` | Zoom |
| Arrow keys in region list | Move selection, map follows |

### Pointer

- Draw AOI: click-drag rectangle for MVP (fastest demo). Polygon tool can follow if time.
- Click detection: select. Click empty map: clear selection, keep AOI.
- Drag map never starts a draw unless Draw tool is active.

### Playwright-facing contracts

Stable `data-testid`s (do not style with them):

`rail`, `map`, `composer`, `composer-query`, `composer-date-from`, `composer-date-to`, `composer-run`, `aoi-status`, `trace`, `inspector`, `region-list`, `region-row`, `confidence`, `scene-earlier`, `scene-later`, `layer-toggle`

Flagship spec (to implement with `playwright-cli`, not now): draw AOI → fill dates → fill query → run → wait for `trace` success → assert ≥1 `region-row` → click row → assert `confidence` visible and map still present.

---

## F. Map / UI Relationship

**Law:** If a control does not help the operator see or judge change on the map, it does not belong on the map.

| UI | Relationship to map |
|---|---|
| Rail | Overlays left. Map stays full bleed underneath. |
| Composer | Overlays bottom. Map padding-bottom ~72px so the AOI is not hidden under the bar. |
| Inspector | Overlays right. Map `fitBounds` with padding `{ left: 56, right: 400, top: 48, bottom: 88 }`. |
| Layers | Overlays top-right. Does not move the camera. |
| Detections | Live on the map. List in inspector is an index into the same features, not a duplicate dashboard. |
| Evidence imagery | Crops of the same scenes, not a different dataset, unless the trace says so. |

Selecting in either map or list updates the other. There is one selected region ID in state and in the URL.

The map never lives inside a card, iframe-looking frame, or rounded rectangle. Viewport = map.

---

## G. Design Tokens

Implement later as CSS custom properties on `:root`. Values are normative.

```css
:root {
  color-scheme: dark;

  --sq-void: #0B0D10;
  --sq-ink: #12151A;
  --sq-panel: #1A1F27;
  --sq-line: rgba(232, 236, 242, 0.10);
  --sq-line-strong: rgba(232, 236, 242, 0.18);
  --sq-text: #E8ECF2;
  --sq-text-muted: #9AA3B2;
  --sq-text-faint: #6B7380;
  --sq-amber: #C9A227;
  --sq-amber-dim: rgba(201, 162, 39, 0.16);
  --sq-success: #3D9A6A;
  --sq-warning: #C47A2C;
  --sq-danger: #C44C4C;

  --sq-glass-bg: rgba(18, 21, 26, 0.72);
  --sq-glass-blur: 16px;

  --sq-space-1: 4px;
  --sq-space-2: 8px;
  --sq-space-3: 12px;
  --sq-space-4: 16px;
  --sq-space-5: 24px;
  --sq-space-6: 32px;

  --sq-radius-sm: 4px;
  --sq-radius-md: 8px;
  --sq-radius-lg: 12px;

  --sq-font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --sq-font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --sq-text-ui: 13px;
  --sq-text-small: 11px;
  --sq-text-query: 14px;
  --sq-text-title: 16px;

  --sq-z-map: 0;
  --sq-z-chrome: 20;
  --sq-z-inspector: 25;
  --sq-z-composer: 30;
  --sq-z-popover: 40;
  --sq-z-toast: 50;

  --sq-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  --sq-duration: 140ms;

  --sq-focus: 0 0 0 2px var(--sq-void), 0 0 0 4px var(--sq-amber);
}
```

**Tailwind mapping (when coding):** extend theme with these names (`ink`, `amber`, …). Do not use default `slate-900` + `violet-500` utilities for brand color.

**Icon token:** Phosphor Regular, 16 / 20, weight 1.5.

**Breakpoints:** `md 768`, `lg 1024`, `xl 1280`. No `2xl` layout change required.

---

## H. Anti-AI-Slop Rules

Apply on every visual pass before coding and before demo.

1. Map is ≥ 70% of the pixels at idle desktop. If chrome eats the map, remove chrome.
2. One accent: amber. If a second bright color appears, it is a bug unless it is success/warning/danger at 6–8px.
3. No chatbot layout. Query is a command bar.
4. No KPI cards, no “12 analyses today”, no fake activity feed.
5. No pills. Dates are fields. Status is text + meter.
6. No decorative 3D. No globe hero. No particle fields.
7. No Inter. No purple. No mesh gradient. No glass-on-glass-on-glass.
8. No em-dashes, no emoji, no “Unlock the power of satellite AI”.
9. Cards only if a floating overlay needs a single shell. Never card-in-card.
10. Confidence is a percent and a bar, not a rainbow choropleth.
11. Empty, loading, and error are designed; success-only mockups are incomplete.
12. If a control looks like Linear / ChatGPT / Gemini / generic “AI SaaS”, restyle it until it looks like an instrument over imagery.

---

## I. Accessibility Rules

Normative, testable, inherited from Vercel Web Interface Guidelines plus workstation specifics.

- Contrast: 4.5:1 body, 3:1 for 18px+ (we have almost no large text, so assume 4.5:1 everywhere).
- Glass text: if muted text fails on imagery showing through, raise glass opacity to 0.88 or switch to solid `ink`.
- Keyboard path for AOI, run, region selection, evidence close.
- Icon-only `aria-label`. Form labels via `htmlFor`. Query has a visible or `aria-label` “Query”.
- `:focus-visible` ring; never `:focus` on click. No `outline-none` without replacement.
- Live regions for trace and errors.
- `Intl.DateTimeFormat` / `Intl.NumberFormat` for dates, area (`km²`), percents. `translate="no"` on IDs and the wordmark.
- Evidence images have width, height, and alt. Below-fold lazy; pair viewer is above-fold in the inspector (`fetchpriority` on the later image).
- Reduced motion: no stagger, no scale. Reduced transparency: solid panels.
- Hit targets ≥ 24px desktop, ≥ 44px touch.
- Destructive discard of a run asks for confirmation.
- Do not trap the map in an inaccessible canvas-only widget; expose a coordinate entry fallback.

Playwright checks (later): keyboard run of flagship flow; focus ring visible; no `aria-label` missing on toolbar.

---

## J. Concise Implementation Plan

Do not start visuals before the map canvas exists. Order is product-critical.

**0. Constraints**  
No extra design kits. Dependencies only when a surface needs them: MapLibre, Phosphor, IBM Plex (self-hosted), Tailwind v4. Optional: Radix Dialog/Popover. Motion: CSS. Tests: Playwright CLI when the flagship path works.

**1. Shell + map**  
Full-viewport MapLibre, dark void behind tiles, attribution, pan/zoom. Prove satellite imagery is the first thing on screen.

**2. Tokens**  
`:root` variables from Section G. Global `color-scheme: dark`. Focus ring utility. Reduced-motion / reduced-transparency media queries.

**3. Overlay chrome**  
Icon rail, layer cluster, query composer (non-functional fields OK). Glass recipe + solid fallback. No inspector yet.

**4. AOI**  
Rectangle draw, amber polygon, area in composer, URL `bbox`, keyboard bbox fallback.

**5. Run + trace**  
Wire dates + query. Dummy or real pipeline. `ExecutionTrace` with real stage names. `aria-live`. Run button loading state.

**6. Detections**  
GeoJSON layer, confidence-encoded fill, list in inspector, selection sync, map padding.

**7. Evidence**  
Pair viewer, confidence meter, metrics list. Empty/error for missing scenes.

**8. Polish last**  
Toasts, unsaved-run guard, deep links, Playwright flagship spec. Audit against Section H and Web Guidelines. Do not add landing, chat history, or extra pages.

**Done when:** a judge can draw an AOI, pick two dates, ask “Show me significant new construction.”, watch the trace, see regions on imagery, open one, and read confidence plus supporting metrics, entirely in this workspace.

---

## Pre-flight (spec, not code)

- [x] Design read declared
- [x] Dials overridden for workstation density
- [x] Taste / Glass / Image-to-Code / gpt-taste marketing rules explicitly rejected where they conflict
- [x] One accent, one theme, one radius table, one icon family
- [x] Map is the primary surface
- [x] Glass is overlay-only with transparency fallback
- [x] Flagship flow specified end to end
- [x] Empty / loading / error specified
- [x] Accessibility testable
- [x] No landing page, no application code, no placeholder components

Next step (when requested): implement Section J starting at **1. Shell + map**.
