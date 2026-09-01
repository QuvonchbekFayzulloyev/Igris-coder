---
name: preview-live-usage
description: >-
  Live Preview (LiveBuildView) oynasining ASL VAZIFASI — agent ishlab
  chiqargan vizual/UI natijalarni REAL vaqtda, BOSQICHMA-BOSQICH va
  HAQIQIY holatda ko'rsatish. Preview — shunchaki "rasm ko'rsatuvchi" emas:
  u agentning qurilish jarayonining jonli oynasi. Har qanday vizual vazifada
  (UI, rasm, diagramma, dashboard) natija preview'da ko'rinadigan fayl
  (SVG, PNG, .uibuild.json) sifatida yaratilishi KERAK — faqat matnli javob
  yetarli emas. Trigger: "preview", "ko'rsat", "jonli ko'rsat", "qanday
  ko'rinadi", "qurilishini kuzat", UI/dizayn/diagramma vazifalari. Preview
  ishlashi uchun natija Igris_brain/agent_workspace'da fayl bo'lishi kerak.
---

# Preview Live Usage — preview'ning asl vazifasi

## Asl vazifa

Igris_Interface'dagi **Preview** bo'limi va chat'dagi **LIVE BUILD**
kartalari agent natijalarini jonli ko'rsatish uchun:

- `.svg` fayl — LiveBuildView elementlarni birma-bir ochib ko'rsatadi
  (haqiqiy SVG elementlari, animatsiya emas).
- `.uibuild.json` — LiveBuildHTML haqiqiy HTML qilib BOSQICHMA-BOSQICH
  quradi (fon → section → nav → kontent → tugma → modal), har bosqichda
  interaktiv.
- `.png` — rastr rasm progressiv ko'rsatiladi.
- `.md`/`.txt`/kod — matnli fayl sifatida ochiladi.

## Qoida: har bir vizual natija preview fayli bo'lsin

1. **Vizual vazifa** (UI, rasm, diagramma, dashboard, sxema) — javobni
   faqat matnda qoldirmang. Natijani **workspace'da fayl** qiling:
   - UI ekran → `art__ui_build_spec(app, output="app.uibuild.json", theme)`
   - Rasm/ob'ekt → `art__draw_scene_svg(subject, output="scene.svg", ...)`
   - UI mockup → `art__draw_ui_svg(app, output="ui.svg", theme, texture)`
   - Oddiy bitmap → `art__draw_object_png(subject, output="obj.png")`
   - Boshqa → `write_file` (SVG/HTML) + `python_exec` (Pillow)
2. **Preview'da ko'rsatish** — javobda yaratilgan fayl yo'lini ayting
   (`image` maydoni chat'da LIVE BUILD kartasini ochadi; frontend
   `msg.path` orqali LiveBuildView'ni ishga tushiradi).
3. **Tugallanganlik** — qurilish tugagach, preview interaktiv bo'ladi
   (sidebar toggle, modal ochiladi) — buni user'ga eslatib o'ting.

## Vizual vazifada javob TARKIBI

```
[natija fayl yaratildi: app.uibuild.json / scene.svg]
[yakuniy holatning 1-2 jumlali tavsifi]
[preview qanday ko'rsatiladi: "chatdagi LIVE BUILD kartasida yoki
 Preview bo'limida elementma-element qurilishni kuzatasiz"]
```

## Igris'da texnik qo'llanishi

- Fayl yo'li workspace'ga nisbatan (masalan `app.uibuild.json`) — frontend
  `workspaceFileUrl(path)` orqali oladi.
- `art__*` tool'lari `Igris_brain/agent_workspace`'ga yozadi (default).
- Chat javobida `image` maydoni fayl yo'li bilan to'ldiriladi → frontend
  LIVE BUILD kartasi ko'rsatadi.
- Preview bo'limida faylni ochish: workspace daraxtidan tanlang yoki
  chat'dagi "⌕ preview" tugmasi.

## Anti-patterns

- Vizual vazifaga faqat matnli javob berish (preview ishlatilmaydi).
- Faylni workspace'dan tashqariga yozish (preview topa olmaydi).
- "Preview ko'rsata olmayman" deyish — `art__*` tool'lari va LiveBuildView bor.
- Natijani bir zarbada "tayyor holda" berib, qurilish jarayonini ko'rsatmaslik
  — user jonli qurilishni kuzatishi kerak (S1 progressive-visual-construction).
