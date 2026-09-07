---
name: ui-design-guidelines
description: Enforces hackathon frontend UI standards for Next.js, Tailwind CSS, and shadcn/ui using the Arc Browser glass design system (DESIGN.md). Use when building or editing UI components, pages, layouts, styles, or design-system tokens. Covers frosted surfaces, pastel gradients, spacing, typography hierarchy, data states, responsive layout, component reuse, accessibility, and anti-slop patterns.
---

# UI Design Guidelines

Hackathon frontend UI rules for Next.js + Tailwind + shadcn/ui. Apply on every UI build or edit pass.

## When to apply

- Creating or modifying components, pages, layouts, or global styles
- Adding data-driven UI (lists, forms, dashboards, inspectors, composers)
- Reviewing a screen before calling it done

## Stack defaults

- **Framework:** Next.js App Router, React, TypeScript
- **Styling:** Tailwind CSS default scale only
- **Components:** shadcn/ui in `components/ui/` — check there first
- **Icons:** Lucide React (or project-standard icon set if already established)

## Rules (enforce verbatim)

- Consistent spacing using only Tailwind's default scale (4/8/16/24/32px), no arbitrary values
- Pastel radial gradient background allowed; one purple accent (`#8b5cf6`); frosted translucent surfaces via `backdrop-filter` are the default treatment for cards, nav, and modals
- Max 2-3 font sizes per screen, clear visual hierarchy
- Always include loading, empty, error, and success states for any data-driven component
- Mobile-first responsive layout (test at sm/md/lg breakpoints)
- Reuse existing components from /components/ui before creating new ones
- Accessible by default: proper contrast, semantic HTML, alt text, focus states
- Avoid generic "AI-generated" look: no centered-everything layouts, no saturated neon, no excessive shadows/animations

## Implementation notes

### Spacing

Use Tailwind spacing utilities that map to 4/8/16/24/32px:

| px | Tailwind |
|----|----------|
| 4  | `1` |
| 8  | `2` |
| 16 | `4` |
| 24 | `6` |
| 32 | `8` |

- Prefer `gap-*`, `p-*`, `m-*`, `space-*` from this set
- Do **not** use arbitrary values (`p-[13px]`, `gap-[18px]`, `mt-[22px]`)
- Align related controls to a shared grid; avoid one-off pixel nudging

### Color & surfaces (Arc glass — see DESIGN.md)

- **Background:** fixed pastel radial gradients on the body (`#fafaff` base)
- **Accent:** `#8b5cf6` only — primary buttons, focus rings, selected states. Soft variant: `#c4b5fd`
- **Surfaces:** frosted white translucency by default
  - `--surface`: `rgba(255, 255, 255, 0.6)` + `backdrop-filter: blur(20px) saturate(160%)`
  - `--surface-strong`: `rgba(255, 255, 255, 0.85)` for nav, modals
- **Text:** `#0f0f14` primary, `#5a5a68` muted
- **Borders:** `rgba(255, 255, 255, 0.5)` or `rgba(15, 15, 20, 0.08)`
- Inner highlight on glass: `inset 0 1px 0 rgba(255, 255, 255, 0.6)`
- Semantic colors (success, warning, error) are small marks + text — not large fills
- Provide opaque fallbacks when `backdrop-filter` is unavailable or `prefers-reduced-transparency` is set

### Typography

- **2–3 sizes per screen**, e.g. body (13–14px), label (11–12px), title (16px max for workstation UI)
- One sans for UI; mono for metrics, IDs, timestamps, coordinates
- Establish hierarchy with weight and muted color — not extra font sizes
- Use `tabular-nums` for comparable numbers

### Data-driven components

Every component that fetches or displays async data must handle:

| State | Requirement |
|-------|-------------|
| **Loading** | Skeleton or inline spinner matched to layout shape — not a full-page blocker unless unavoidable |
| **Empty** | Clear message + one next action ("Draw an area", "Upload a file") |
| **Error** | Inline, readable message; retry or fix path when possible |
| **Success** | Confirm outcome without blocking further work |

Do not ship a component that only renders the happy path.

### Responsive

- **Mobile-first:** base styles for small screens; enhance at `sm`, `md`, `lg`
- Verify layout at **640px (sm), 768px (md), 1024px (lg)**
- Touch targets ≥ 44px on mobile
- No horizontal page scroll; use `min-h-[100dvh]` not `h-screen`

### Component reuse

Before creating a new component:

1. Search `components/ui/` for shadcn primitives (Button, Input, Dialog, etc.)
2. Search `components/` for existing domain components
3. Extend or compose — do not duplicate

New shadcn components: add only when a primitive is genuinely missing.

### Accessibility

- Semantic HTML: `button` for actions, `nav` for navigation, heading order without skips
- WCAG AA contrast on text and interactive controls
- `alt` on meaningful images; decorative images `alt=""`
- Visible `:focus-visible` ring on all interactive elements
- Icon-only buttons need `aria-label`
- Live regions (`aria-live`) for async status updates
- Respect `prefers-reduced-motion` and `prefers-reduced-transparency`

### Anti-slop

Reject on sight:

- Centered-everything marketing layouts in product/workstation UI
- Hard-edged opaque surfaces where frosted glass is expected
- Saturated neon accents or a second brand color
- Three equal feature cards as the only layout pattern
- Heavy drop shadows, infinite pulse animations
- Chatbot bubbles, avatars, "suggested prompts" walls in non-chat products
- `transition-all`; animate `transform` and `opacity` only

## Workflow

1. Read existing components and design tokens before editing
2. Implement the smallest diff that satisfies the UI task
3. Add all four data states if the component is data-driven
4. Check responsive behavior at sm/md/lg
5. Run the done checklist below

## Done checklist

Before considering a screen **done**, verify:

- [ ] Spacing uses only 4/8/16/24/32px (Tailwind 1/2/4/6/8) — no arbitrary values
- [ ] Pastel radial gradient background; accent is purple (`#8b5cf6`), not a system color
- [ ] Does every surface use `backdrop-filter` or an opaque fallback?
- [ ] 2–3 font sizes on screen with clear hierarchy
- [ ] Loading, empty, error, and success states exist for every data-driven piece
- [ ] Layout works at sm, md, and lg breakpoints (mobile-first)
- [ ] Existing `components/ui` primitives reused before new components
- [ ] Contrast, semantics, alt text, and focus states are in place
- [ ] No centered-everything layout, saturated neon, or excessive shadow/animation
- [ ] Screen reads as a product surface, not a generic AI dashboard
