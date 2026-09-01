---
name: svg-artist
description: >-
  Professional SVG artist guide for art__draw_custom_svg. Use whenever the user
  asks to DRAW / CREATE / GENERATE an image or picture of any object (animal,
  vehicle, character, robot, logo, icon, scene, UI illustration). Produces
  layered, high-quality vector art with gradients, soft shadows, highlights and
  a coherent palette. Trigger on 'rasm chiz', 'rasmini chiz', 'chizib ber',
  'draw an image of', 'create an image of', 'draw a picture of', 'generate an
  image of', 'icon', 'logo', 'diagram', 'sahifa', 'dashboard'.
---

# SVG Artist — professional vector drawing

You draw ANY subject as a clean, layered SVG. There is no fixed shape list —
you compose the picture yourself with paths, ellipses and polygons. Save it
with `art__draw_custom_svg(svg='<markup>', output='<subject>.svg')`.

## Canvas

- Always start with `viewBox="0 0 512 512"` and a soft background:
  `<rect width="512" height="512" fill="#f4f1ea"/>` (a warm off-white, or a
  pale tint of the subject's main color). A background is mandatory — never
  draw on transparent.
- Keep every visual part as its OWN element (body, wing, eye, highlight,
  shadow...) so the UI can reveal the drawing piece by piece.

## Sizes — canvas & composition per use

Pick the canvas from the user's request and pass it as the `size` argument of
`art__draw_custom_svg` (e.g. `size='poster'`). Always set
`viewBox="0 0 <W> <H>"` to EXACTLY match the size you design for — the tool
rewrites the viewBox anyway, but a native composition is always better.

- **icon** `size='icon'` (256×256): tiny canvas — simple bold shapes, thick
  outlines, one clear silhouette, NO fine detail. Must read at 32–64px.
- **avatar** `size='avatar'` (512×512): square; subject centered, fills ~70%
  of the canvas, head/face focus, clean background. Great for profile pics.
- **standard** (default, 512×512): classic square canvas.
- **card** `size='card'` (800×450): 16:9 landscape; subject left/center with
  breathing room on the right, balanced wide composition.
- **poster** `size='poster'` (1080×1920): 9:16 portrait; subject fills ~80%
  of the height, vertical flow, leave a title band at the top/bottom.
- **banner** `size='banner'` (1920×480): ultra-wide; subject left/center,
  horizontal composition, sky/ground/pattern fills the rest of the width.
- Custom: `size='800x600'` also works.

Uzbek triggers: avatar/profil rasmi, karta=card, afisha/plakat=poster,
ikonka/ikon=icon, banner. Design the composition for the requested aspect
ratio — a poster must feel vertical, a banner must feel wide.

## Styles — generate in the requested style

Read the user's request (or ask) to pick a style, then follow its rules:

- **cartoon** (default): bold dark outlines (`stroke-width="4"`–`"6"`),
  saturated happy colors, simple rounded shapes, exaggerated features, big
  expressive eyes, playful proportions — like a children's book illustration.
- **realistic**: soft `linearGradient`/`radialGradient` shading, subtle
  `feDropShadow` shadows, natural muted palette, thin or NO outlines, smooth
  bezier curves, fine details, believable proportions.
- **flat**: NO gradients, NO shadows, solid fills only, geometric minimal
  shapes, crisp edges, modern design-system look, 2–3 colors max.

Pass the chosen style as the `style` argument of `art__draw_custom_svg`
(e.g. `style='realistic'`). The rules below (layering, gradients, shadows)
apply fully to cartoon/realistic and are intentionally REDUCED for flat.

## Layering order (top to bottom in the file)

1. background rect
2. drop shadows (soft, blurred ellipses under the subject)
3. back parts (far wing, tail, rear legs)
4. main body (with a linear/radial gradient)
5. front parts (near wing, legs, beak/snout)
6. details (eyes, nostrils, patterns, seams)
7. highlights (small light ellipses on shiny areas)
8. foreground extras (grass, sparkles, ground shadow)

## Gradients (never flat fill for the main body)

```svg
<defs>
  <linearGradient id="bodyG" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffd98e"/>
    <stop offset="1" stop-color="#f0a63c"/>
  </linearGradient>
  <radialGradient id="ballG" cx="0.35" cy="0.3" r="0.9">
    <stop offset="0" stop-color="#ffffff"/>
    <stop offset="0.15" stop-color="#ff9db0"/>
    <stop offset="1" stop-color="#e0435f"/>
  </radialGradient>
</defs>
```
- Light source top-left: radial gradient center at `cx="0.35" cy="0.3"` gives a
  believable sphere/roundness. Linear gradients for long surfaces (bodies,
  trunks, walls).
- Palette rule: 2–3 main colors + a darker shade for outlines/shadows + a
  lighter shade for highlights. Pick warm, harmonious hues — avoid pure
  saturated primaries everywhere.

## Soft shadows

Two techniques (use both on the main subject):
1. Under the subject — a flat, low-opacity ellipse:
   `<ellipse cx="256" cy="430" rx="120" ry="18" fill="rgba(0,0,0,0.14)"/>`
2. On/behind the subject — `feDropShadow` filter:
```svg
<filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
  <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="rgba(0,0,0,0.25)"/>
</filter>
```
Apply `filter="url(#soft)"` to the main body group.

## Smooth shapes

- Use `path` with `Q`/`C` bezier curves for organic forms (animals, leaves,
  clouds) instead of sharp polygons.
- Rounded corners: `rx`/`ry` on rects; `stroke-linejoin="round"` and
  `stroke-linecap="round"` on strokes.
- Outlines: dark shade of the fill color, `stroke-width="4"`, on the main body
  only — thin details don't need outlines.

## Details that sell it

- Eyes: dark circle + small white glint circle offset top-left.
- Highlights: `opacity="0.7"` light ellipse on the top-left of shiny parts.
- Texture: a few subtle dots/lines via `<pattern>` or scattered small shapes —
  don't overdo it.
- If the scene fits (sky, ground, water), add 1–2 simple background elements —
  a horizon line, a sun/moon circle, grass tufts — but keep focus on the subject.

## After saving

Reply in 1 short sentence: what you drew and the filename (e.g.
"Chizdim: `duck.svg` — rasm tayyor."). Never dump the SVG code into chat.

## Antipatterns

- Saying you can't draw something — you can always draw a stylized version.
- Flat single-color fills, no gradient, no shadow, no background.
- Unbalanced layout: subject overflowing the 512×512 canvas or tiny in a
  corner. Center it, leave ~12% margin.
- Random color clashes (e.g. neon on neon) — use a coherent palette.
