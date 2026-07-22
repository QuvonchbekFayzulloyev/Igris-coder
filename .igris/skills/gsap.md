---
name: gsap
description: "Use when building high-performance animations with GSAP (GreenSock Animation Platform). Creates smooth timeline animations, scroll-triggered effects, and morph transitions — all optimized for laptop battery and integrated GPUs via Executive Strategy tier system."
pipeline_stage: Implementation
triggers: [gsap, greensock, animation, timeline, scrolltrigger, tween, motion, transition, animate, stagger, keyframes, morphsvg, flip, drawsvg, motionpath]
used_by: [all]
---

# GSAP — Executive Strategy Tier Integration

GSAP for laptop-friendly UI animations (~15KB gzipped core).
ALL animation complexity MUST go through `executive.getQualityLevel()`.

## Quality Tiers (Executive Strategy Compliant)

| Setting | Tier 0 (Battery) | Tier 1 (Low) | Tier 2 (Balanced) | Tier 3 (High) | Tier 4 (Ultra) |
|---------|:---:|:---:|:---:|:---:|:---:|
| Max simultaneous | 5 | 10 | 20 | 40 | 80 |
| Stagger max items | 10 | 20 | 40 | 80 | 160 |
| ScrollTrigger throttle | 200ms | 100ms | 50ms | 25ms | 16ms |
| Duration min/max | 100-200ms | 100-300ms | 150-400ms | 200-500ms | 200-600ms |
| MotionPath | off | off | off | on | on |
| MorphSVG | off | off | off | on | on |
| Draggable | off | off | on | on | on |
| Flip layouts | off | off | on | on | on |

## Implementation

```javascript
import { executive } from '../executive-strategy/controller.js';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

function getAnimationConfig() {
  const quality = executive.getQualityLevel();
  return {
    durationRange: [100, 200, 300, 400, 500][quality] / 1000,
    staggerEach: [0.05, 0.04, 0.03, 0.02, 0.015][quality],
    scrollThrottle: [200, 100, 50, 25, 16][quality],
    usePlugins: quality >= 3,
  };
}

// Usage
const cfg = getAnimationConfig();
gsap.to('.items', {
  x: 100,
  duration: cfg.durationRange,
  stagger: cfg.staggerEach,
  scrollTrigger: {
    trigger: '.container',
    fastScrollEnd: true,
    throttle: cfg.scrollThrottle,
  },
});
```

## Laptop Performance Rules

1. **Animate only `transform` and `opacity`** — GPU-composited, never trigger layout
2. **`will-change` opt-in** — set then clear with `ClearProps`
3. **Kill on unmount** — always `gsap.killTweensOf(element)` or `scrollTrigger.kill()`
4. **Batch DOM reads/writes** — avoid mixing framework state updates in same microtask
5. **`immediateRender: false`** for paused timelines — prevents flash on mount

## Validation

- ✅ Uses `executive.getQualityLevel()` for animation complexity
- ✅ Only `transform`/`opacity` animated — no layout triggers
- ✅ `killTweensOf` called on unmount
- ✅ No ScrollTrigger memory leaks
- ✅ Frame rate stable on integrated GPU at Tier 2
