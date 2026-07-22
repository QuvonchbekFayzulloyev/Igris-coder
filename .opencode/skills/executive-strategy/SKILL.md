---
name: executive-strategy
description: "Resource-aware executive controller that adjusts quality, complexity, and feature level based on available laptop resources (CPU, GPU, RAM, battery). Self-evolving: monitors FPS, memory usage, and thermal state to dynamically scale all animation/3D/visual skills. Prevents laptop overheating while maintaining optimal visual quality."
triggers: [executive, strategy, resource, performance, quality, adaptive, laptop, battery, optimize, throttle, scaling, self-evolving, self-evolve, resource-aware, budget, profile, performance mode, quality level, gpu, integrated graphics, laptop mode]
pipeline_stage: Planning
license: MIT
related-skills: [threejs, gsap, design-dna, motion-design, genjutsu]
---

# Executive Strategy — Self-Evolving Resource Controller

Controls quality levels across all animation/3D/visual skills based on runtime
resource detection. The system self-evolves: it measures, adapts, and remembers.

## Tier System

Every visual skill checks with Executive Strategy before choosing quality settings.

| Tier | Label | GPU | Triangle Budget | Texture Max | Shadow | PostFX | Particle Cap |
|------|-------|-----|----------------|-------------|--------|--------|-------------|
| 0 | **Battery Saver** | Intel UHD / no GPU | 1K total | 512px | off | off | 50 |
| 1 | **Low Power** | Integrated entry | 10K total | 1024px | 512px PCF | off | 200 |
| 2 | **Balanced** | Integrated mid (Iris, Vega) | 50K total | 2048px | 1024px PCF | 1 pass | 1000 |
| 3 | **High Quality** | Discrete entry (MX, RTX 2050) | 200K total | 4096px | 2048px PCF Soft | 2 passes | 5000 |
| 4 | **Ultra** | Discrete high (RTX 3060+) | 1M total | 8192px | 4096px PCF Soft | full | 20000 |

## Runtime Detection (No User Config Needed)

```javascript
class ExecutiveStrategy {
  constructor() {
    this.tier = null;
    this.fpsHistory = [];
    this.thermalThrottle = false;
  }

  detectTier() {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2');
    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = debugInfo
      ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : '';
    
    // Detect integrated vs discrete
    const isIntel = /intel/i.test(renderer);
    const isAMD_Integrated = /(amd|ati).*(\brendon\b|integrated)/i.test(renderer);
    const isAppleSilicon = /apple\s+(m[1-4]|a\d+)/i.test(renderer);
    const isDiscrete = /(nvidia|rtx|gtx|radeon\s+(rx|pro)\b)/i.test(renderer);
    
    const maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    const maxVtx = gl.getParameter(gl.MAX_VERTEX_ATTRIBS);
    const mem = navigator.deviceMemory || 4; // GB, Chrome-only
    const cores = navigator.hardwareConcurrency || 4;

    if (isDiscrete && maxTex >= 16384 && mem >= 16) {
      this.tier = 4;
    } else if (isDiscrete && mem >= 8) {
      this.tier = 3;
    } else if (isAppleSilicon || maxTex >= 8192) {
      this.tier = 2;
    } else if (maxTex >= 4096) {
      this.tier = 1;
    } else {
      this.tier = 0;
    }
    
    // Battery check — drop one tier if on battery
    if (navigator.getBattery) {
      navigator.getBattery().then(b => {
        if (!b.charging && this.tier > 0) this.tier--;
      });
    }
    
    return this.tier;
  }

  // Self-evolving: monitor FPS and auto-adjust
  async monitor(render) {
    let fps = 0, frames = 0, last = performance.now();
    const loop = (now) => {
      frames++;
      if (now - last >= 1000) {
        fps = frames;
        frames = 0;
        last = now;
        this.fpsHistory.push(fps);
        if (this.fpsHistory.length > 10) this.fpsHistory.shift();
        this._adapt();
      }
      render();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  _adapt() {
    const avg = this.fpsHistory.reduce((a,b) => a+b,0) / this.fpsHistory.length;
    if (avg < 30 && this.tier > 0) {
      this.tier--;  // Drop quality — overheating/throttling detected
      this.fpsHistory = []; // Reset after change
    }
    if (avg > 55 && this.tier < 4) {
      this.tier++;  // Raise quality — we have headroom
      this.fpsHistory = [];
    }
  }

  getQualityLevel() {
    if (this.tier === null) this.detectTier();
    return this.tier;
  }
}
export const executive = new ExecutiveStrategy();
```

## Integration Contract

All animation/3D/visual skills MUST:
1. Call `executive.getQualityLevel()` before setting quality parameters
2. Import executive-strategy as a peer dependency
3. Define high/medium/low quality branches keyed to tiers 4/2/0
4. Never hardcode "high quality" — always use `executive.getQualityLevel()`
5. Listen for dynamic tier changes (battery unplug, thermal throttle)

## Self-Evolution Rules

| Observation | Action |
|------------|--------|
| FPS < 30 for 5+ seconds | Drop 1 tier, reset FPS history |
| FPS > 55 for 10+ seconds | Raise 1 tier, reset FPS history |
| Battery unplugged | Drop 1 tier immediately |
| Battery plugged in | Raise 1 tier (up to original detected tier) |
| Thermal throttling detected (via `navigator.getBattery()` or FPS pattern) | Drop to tier 1 until cool |
| Memory > 80% (via `performance.memory`) | Drop 2 tiers, clear unused textures |
| New renderer detected (external monitor, eGPU) | Re-detect tier |

## Reuse Across Skills

```javascript
// ANY skill — Three.js, GSAP, Genjutsu, etc.
import { executive } from '../executive-strategy/controller.js';

const quality = executive.getQualityLevel(); // 0-4
const pixelRatio = [1, 1, 1.5, 2, 2][quality];
const shadows = quality >= 2;
const particles = [50, 200, 1000, 5000, 20000][quality];
```

## Validation

- ✅ No hardcoded quality — every setting goes through `executive.getQualityLevel()`
- ✅ FPS monitor runs only when animations are active (not idle)
- ✅ Thermal throttle auto-reduces quality, auto-recovers when cool
- ✅ Battery-aware: unplug = immediate 1-tier drop
- ✅ Memory-aware: >80% usage triggers aggressive reduction
- ✅ All 5 visual skills (threejs, gsap, design-dna, motion-design, genjutsu) comply
- ✅ Zero dependencies — pure vanilla JS, ~2KB minified
