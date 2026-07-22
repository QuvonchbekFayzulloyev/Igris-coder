---
name: motion-design
description: "Use when designing or implementing motion/animation systems for web UI. Creates purposeful motion with correct timing, easing, choreography, and spatial logic — all dynamically scaled via Executive Strategy tier system for laptop performance."
pipeline_stage: Implementation
triggers: [motion design, animation, transition, micro-interaction, easing, timing, ui animation, page transition, loading, gesture, enter animation, exit animation, flip, layout animation, spring, choreography]
used_by: [all]
---

# Motion Design — Executive Strategy Tier Integration

Purposeful motion that communicates hierarchy, spatial relationships, and state
changes. ALL motion complexity goes through `executive.getQualityLevel()`.

## Quality Tiers (Executive Strategy Compliant)

| Setting | Tier 0 (Battery) | Tier 1 (Low) | Tier 2 (Balanced) | Tier 3 (High) | Tier 4 (Ultra) |
|---------|:---:|:---:|:---:|:---:|:---:|
| Max simultaneous | 2 | 5 | 10 | 20 | 40 |
| Micro-interactions | off | opacity | transform | full | + spring |
| Page transitions | cut | 100ms fade | 200ms slide | 300ms shared | 400ms shared+spring |
| Stagger max | none | 5 items | 15 items | 30 items | 60 items |
| Scroll-reveal | off | off | on | on | on + parallax |
| Loading shimmer | off | 1s cycle | 1.2s cycle | 1.5s cycle | 1.5s + color |
| Gesture feedback | none | opacity | scale | scale + rotate | spring physics |
| Duration range | 50-100ms | 100-200ms | 150-300ms | 200-400ms | 200-500ms |

## Implementation

```javascript
import { executive } from '../executive-strategy/controller.js';

function getMotionProfile() {
  const q = executive.getQualityLevel();
  return {
    duration: [100, 150, 250, 350, 400][q],
    easing: ['linear', 'ease-out', 'cubic-bezier(0,0,0.2,1)',
             'cubic-bezier(0.18,0.89,0.32,1.28)',
             'cubic-bezier(0.34,1.56,0.64,1)'][q],
    maxSimultaneous: [2, 5, 10, 20, 40][q],
    transformOnly: q <= 1,      // Tier 0-1: opacity only
    useSpring: q >= 3,
    useScrollReveal: q >= 2,
    useSharedElements: q >= 3,
  };
}
```

## Motion Principles (Tier-Aware)

1. **Tier 0-1:** opacity-only transitions, 100-200ms, no scroll reveal, no stagger
2. **Tier 2:** transform+opacity, 250ms, scroll reveal, mild stagger (15 items)
3. **Tier 3-4:** spring physics, shared elements, parallax, full choreography

## Reduced Motion (Always On)

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Validation

- ✅ Uses `executive.getQualityLevel()` for timing, easing, complexity
- ✅ Tier 0: opacity-only, no layout triggers, max 2 simultaneous
- ✅ `prefers-reduced-motion` respected with static fallback
- ✅ Only `transform`/`opacity` animated at Tier ≤2
- ✅ ≤10 simultaneous animated elements at Tier 2
- ✅ 60 FPS on integrated GPU at Tier 2
