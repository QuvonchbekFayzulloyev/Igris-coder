---
name: threejs
description: "Use when building 3D graphics with Three.js in the browser. Creates optimized WebGL scenes, implements 3D models, renders animations, and configures lighting/materials — all with laptop-friendly performance via Executive Strategy tier system."
pipeline_stage: Implementation
triggers: [three.js, webgl, 3d, webgpu, 3d scene, 3d model, 3d animation, renderer, mesh, geometry, shader, glsl, camera, lighting]
used_by: [all]
---

# Three.js — Executive Strategy Tier Integration

Resource-efficient Three.js for laptops with integrated GPUs.
ALL quality settings MUST go through `executive.getQualityLevel()`.

## Quality Tiers (Executive Strategy Compliant)

| Setting | Tier 0 (Battery) | Tier 1 (Low) | Tier 2 (Balanced) | Tier 3 (High) | Tier 4 (Ultra) |
|---------|:---:|:---:|:---:|:---:|:---:|
| Pixel ratio | 1 | 1 | 1.5 | 2 | 2 |
| Max triangles | 1K | 10K | 50K | 200K | 1M |
| Max texture | 512px | 1024px | 2048px | 4096px | 8192px |
| Shadows | off | 512px PCF | 1024px PCF | 2048px soft | 4096px soft |
| PostFX passes | 0 | 0 | 1 | 2 | full |
| Draw calls cap | 20 | 50 | 100 | 200 | 500 |
| Particles | 50 | 200 | 1000 | 5000 | 20000 |
| LOD levels | 1 | 2 | 3 | 4 | 5 |
| Anti-aliasing | off | off | MSAA 2x | MSAA 4x | MSAA 8x |

## Implementation

```javascript
import { executive } from '../executive-strategy/controller.js';

function createRenderer(canvas) {
  const quality = executive.getQualityLevel();
  const pixelRatio = [1, 1, 1.5, 2, 2][quality];
  const shadows = quality >= 2;
  const aa = quality >= 2;
  
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: aa,
    powerPreference: quality <= 1 ? 'low-power' : 'high-performance',
  });
  renderer.setPixelRatio(Math.min(pixelRatio, devicePixelRatio));
  if (shadows) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = quality >= 3
      ? THREE.PCFSoftShadowMap
      : THREE.PCFShadowMap;
  }
  return renderer;
}
```

## Resource Detection (Fallback)

Only if `executive` module is unavailable — auto-detect as standalone:

```javascript
const gpu = renderer.capabilities;
const isLowEnd = gpu.maxVertexUniforms < 1024 || gpu.maxTextureSize < 4096;
const pixelRatio = isLowEnd ? 1 : Math.min(devicePixelRatio, 2);
renderer.setPixelRatio(pixelRatio);
```

## Bundle Size Control

```javascript
// Dynamic import — never bundle Three.js in main chunk
const THREE = await import('three');
const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
```

## Validation

- ✅ Uses `executive.getQualityLevel()` for all quality settings
- ✅ No hardcoded pixel ratio, shadow resolution, or poly count
- ✅ Tier table matches Executive Strategy tier boundaries
- ✅ Frame time ≤16ms (60 FPS) on integrated GPU at Tier 2
- ✅ No memory leak: `dispose()` all resources on unmount
- ✅ Three.js as dynamic import, not in main chunk
