---
name: genjutsu
description: "Use when creating visual illusions, perception-based effects, psychological animations, and sleight-of-hand UI tricks. Genjutsu is the art of visual misdirection — making the UI feel faster, smoother, more responsive than it actually is. All effects scale via Executive Strategy tier system."
triggers: [genjutsu, illusion, perception, skeleton, optimistic ui, fake progress, shimmer, placeholder, visual trick, misdirection, psychological animation, attention, cognitive load, perceived performance, instant loading, sleight-of-hand]
pipeline_stage: Implementation
license: MIT
executive_tier: true
---

# Genjutsu — Executive Strategy Tier Integration

Making UIs feel faster than they actually are through psychological techniques.
ALL illusion complexity goes through `executive.getQualityLevel()`.

## Quality Tiers (Executive Strategy Compliant)

| Setting | Tier 0 (Battery) | Tier 1 (Low) | Tier 2 (Balanced) | Tier 3 (High) | Tier 4 (Ultra) |
|---------|:---:|:---:|:---:|:---:|:---:|
| Skeleton type | flat color | static gray | shimmer | shimmer + color | shimmer + gradient |
| Shimmer animation | none | none | 1.5s | 1.2s | 0.8s |
| Optimistic UI | off | off | on (1s rollback) | on (3s rollback) | on (5s rollback) |
| Fake progress | none | simple bar | bar + label | bar + ETA | animated bar + ETA |
| Perceptual easing | linear | ease-out | ease-out | fast-out | fast-out + spring |
| Staggered reveal | none | 5 items | 15 items | 30 items | all items |
| Attention effects | none | color flash | pulse + color | pulse + glow | pulse + glow + spring |
| Skeleton items visible | 1 | 3 | 6 | 12 | full page |

## Implementation

```javascript
import { executive } from '../executive-strategy/controller.js';

function getIllusionProfile() {
  const q = executive.getQualityLevel();
  return {
    // Skeleton — more sophisticated at higher tiers
    skeletonStyle: ['flat', 'static', 'shimmer', 'shimmer', 'shimmer-gradient'][q],
    shimmerCycle: [0, 0, 1500, 1200, 800][q],
    skeletonMaxVisible: [1, 3, 6, 12, 50][q],

    // Optimistic UI — only at Tier 2+
    optimisticActions: q >= 2,
    rollbackTimeout: [0, 0, 1000, 3000, 5000][q],

    // Attention effects — more dramatic at higher tiers
    attentionStyle: ['none', 'flash', 'pulse', 'pulse-glow', 'pulse-glow-spring'][q],

    // Perceptual motion
    easing: ['linear', 'ease-out', 'cubic-bezier(0,0,0.2,1)',
             'cubic-bezier(0,0,0.2,1)', 'cubic-bezier(0,0,0.2,1)'][q],
  };
}
```

## Core Techniques (Tier-Aware)

### Skeleton Screens

```css
/* Tier 0: flat color blocks, no animation */
.skeleton { background: var(--skeleton-base); border-radius: 4px; }

/* Tier 2+: shimmer animation */
.skeleton-shimmer {
  background: linear-gradient(90deg, var(--base) 25%, var(--shine) 50%, var(--base) 75%);
  background-size: 200% 100%;
  animation: shimmer var(--shimmer-cycle) ease-in-out infinite;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
/* Performance: GPU-composited background-position, no layout */
```

### Optimistic UI (Tier 2+ Only)

```javascript
// Assume success, show instantly, roll back on failure (with timeout)
function optimisticUpdate(prevState, newItem, apiCall) {
  setState([...prevState, newItem]);      // Instant
  apiCall().catch(() => {
    setState(prevState);                   // Rollback
    notify('Failed. Reverted.');
  });
}
```

### Perceptual Motion (All Tiers)

```css
/* Fast-out easing — feels instant even at same duration */
.perceptual-fast {
  transition: transform 250ms cubic-bezier(0, 0, 0.2, 1);
}
```

### Fake Progress Bar (Tier 1+)

```css
.progress-fake {
  width: 0%;
  transition: width 300ms ease-out;
  /* Jump to 70% immediately, crawl to 90%, pause at 95% */
}
```

## Laptop Performance Rules

- Tier 0: no animation, no shimmer, no GPU cost — pure flat UI
- Skeleton shimmer: `background-position` only — GPU composited
- Fake progress: zero cost — CSS width transition only
- Max shimmer elements = tier-dependent, capped at viewport only
- All techniques combined: ≤5% CPU overhead at Tier 2
- Optimistic UI: zero animation cost — just state management

## Validation

- ✅ Uses `executive.getQualityLevel()` for all illusion effects
- ✅ Tier 0: flat skeleton, no animation, no shimmer — zero GPU cost
- ✅ Skeleton matches final layout (no CLS)
- ✅ Shimmer uses `background-position` only (GPU composited)
- ✅ Optimistic UI enabled only at Tier 2+
- ✅ Fake progress never reaches 100% before completion
- ✅ `prefers-reduced-motion` disables all shimmer and attention effects
- ✅ ≤5% CPU overhead at Tier 2 on integrated GPU
