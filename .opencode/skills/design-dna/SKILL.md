---
name: design-dna
description: "Use when designing or implementing visual design systems, brand identities, UI language, and component design tokens. Produces coherent design languages with color systems, typography scales, spacing grids, and motion principles — with Executive Strategy tier system for responsive visual complexity."
triggers: [design system, design language, brand identity, design tokens, visual identity, brand guide, style guide, UI language, component library, design pattern, theme]
pipeline_stage: Planning
license: MIT
executive_tier: true
---

# Design DNA — Executive Strategy Tier Integration

A design system framework that defines the visual, interactive, and behavioral DNA
of a product. ALL visual complexity decisions go through `executive.getQualityLevel()`.

## Quality Tiers (Executive Strategy Compliant)

| Setting | Tier 0 (Battery) | Tier 1 (Low) | Tier 2 (Balanced) | Tier 3 (High) | Tier 4 (Ultra) |
|---------|:---:|:---:|:---:|:---:|:---:|
| Shadows | flat | 1 level | 3 levels | 5 levels | 5 levels + blur |
| Blur backdrop | none | none | 8px | 16px | 24px |
| Gradient complexity | solid | 2-stop | 3-stop | 4-stop | 5-stop |
| Border radius | 4px uniform | 4px uniform | 4-8px varied | 4-12px varied | 4-16px varied |
| Icon style | outline 1px | outline 1.5px | outline 2px | filled | filled + duotone |
| Animation duration | 100ms | 150ms | 250ms | 300ms | 400ms |
| Micro-interactions | none | opacity only | transform+opacity | full | full + spring |
| Skeleton shimmer | off | simple | animated | animated | animated + color |
| Typography features | none | none | tabular-nums | + ligatures | + stylistic sets |

## Token Architecture

```
tokens/
  global/
    color.json        — hue, saturation, lightness primitives
    typography.json   — typeface, weight, line-height families
    spacing.json      — 4px base grid
    motion.json       — duration, easing curves (tiered)
    elevation.json    — shadow levels (tier-dependent count)
  alias/
    semantic.json     — color.primary, color.error, etc.
    component.json    — button.bg, button.text, card.shadow (tiered)
  component/
    button.json       — size/color/padding variants
```

## Motion DNA (Tier-Aware)

```css
/* All tokens compile to CSS variables — zero runtime cost */
:root {
  --duration-fast: 100ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.1);
}

/* Tier 0-1: flat shadows, no blur, solid colors */
/* Tier 2+: layered shadows, backdrop blur, gradients */
```

## Color System

```json
{
  "hue_wheel": { "primary": 210, "secondary": 340, "accent": 160 },
  "scale": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900],
  "lightness": { "50": 0.97, "100": 0.92, "200": 0.82, ... },
  "saturation": { "50": 0.05, "100": 0.10, "200": 0.20, ... }
}
```

## Laptop Performance Rules

- All tokens compile to static CSS variables — zero runtime cost
- Motion tokens use `transform`/`opacity` only (GPU composited)
- Shadows/blur disabled at Tier 0-1 — pure flat design
- Dark mode via `color-scheme` + CSS variables — no class toggle overhead
- Responsive: mobile-first breakpoints (640, 768, 1024, 1280)

## Validation

- ✅ Uses `executive.getQualityLevel()` for shadow/blur/gradient complexity
- ✅ WCAG AA contrast (4.5:1 normal, 3:1 large text)
- ✅ All colors from hue wheel — no arbitrary values
- ✅ Spacing follows 4px grid
- ✅ Motion tokens use GPU-composited properties only
- ✅ Design tokens as static CSS vars — zero JS runtime cost
- ✅ Tier 0 = pure flat design, no GPU overhead
