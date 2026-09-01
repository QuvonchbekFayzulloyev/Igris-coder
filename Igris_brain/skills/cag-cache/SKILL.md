---
name: cag-cache
description: >-
  CAG (Cache-Augmented Generation) — takroriy savol/vazifalarga javoblarni
  KESHLASH orqali tezlik va barqarorlikni oshirish metodikasi. Bir xil
  so'rov qayta kelganda LLM'ni qayta ishga tushirmasdan, saqlangan javobni
  qaytarish. Igris'da bu uchun CagCache (Igris_brain/cag.py) mavjud — LLM
  javoblari (prompt-hash bo'yicha) keshlanadi, TTL va LRU bilan boshqariladi.
  Trigger: takrorlanuvchi so'rovlar, bir xil vazifa qayta berilishi mumkin
  bo'lgan holatlar, tezlik muhim bo'lgan joylar, test/CI ishlari. Deterministik
  natijalar uchun xavfsiz — kreativ/muhokama savollarida qo'llanilmaydi.
---

# CAG Cache — keshlash orqali tezlashtirish

## Nima bu

RAG — bilimni TASHQARIDAN chaqirish. CAG — ilgari hisoblangan javobni
QAYTA ISHLATISH. Takroriy so'rovlar uchun LLM qayta ishlamaydi, keshdan
javob qaytariladi: tezroq, arzonroq, barqarorroq.

## Qachon ishlatiladi

| Holat | CAG? |
|---|---|
| Deterministik so'rov (xuddi shu savol qayta) | ✅ keshdan qaytar |
| Takrorlanuvchi vazifa (build, test, format) | ✅ keshdan qaytar |
| Kreativ/muhokama (fikr, loyiha, "nima deb o'ylaysan") | ❌ keshlamaslik |
| Foydalanuvchi "yangilab ber" degan | ❌ keshni bekor qilish (invalidate) |
| Kontekst o'zgardi (fayl tahrirlandi) | ❌ keshni bekor qilish |

## Igris'da texnik qo'llanishi

```python
from cag import CagCache

cache = CagCache(max_entries=256, ttl_seconds=1800)

# yozish (javob olingach)
cache.put(system_prompt, user_prompt, response_text)

# o'qish (LLM'ga borishdan oldin)
hit = cache.get(system_prompt, user_prompt)
if hit is not None:
    return hit  # LLM chaqirilmaydi

# bekor qilish (fayl o'zgarganda / "yangilab ber")
cache.invalidate(prefix_or_key)
```

Kesh kaliti = (system_prompt hash, user_prompt hash). Agente `CagCache`
`igris_agent.chat()` da avtomatik ulanadi: agar keshda bo'lsa — LLM
chaqirilmaydi, natija keshdan qaytariladi; natija yangi bo'lsa — keshga
yoziladi. `/api/status` da `cag: {size, hits, misses}` ko'rinadi.

## Qoidalar

1. **Deterministik javoblargina** keshlanadi (kod generatsiyasi, qisqa
   yechimlar, qayta-qayta so'raladigan faktlar). Chat-muhokamani keshlamang.
2. **TTL** — eski javobni cheksiz qaytarmang; muddat o'tsa qayta hisoblang.
3. **Invalidate** — kontekst o'zgarganda (fayl yozilganda, session
   yangilanganda) mos kesh yozuvlarini o'chiring.
4. **HIT/MISS kuzatuvi** — `/api/status` dagi cag statistikasidan samarani
   ko'ring; hit rate past bo'lsa kesh foydasiz (yozishni to'xtating).
5. Keshda javob bo'lsa ham, user "qayta ko'rsat" deganida — invalidate + qayta.

## Anti-patterns

- Kreativ javoblarni keshga yozish (takroriy, qotib qolgan javoblar).
- Invalidate qilmasdan eski javobni qaytaraverish (fayl o'zgardi, javob eski).
- Keshni "tezkor qilish" uchun hamma narsaga qo'llash — xato javobni ham
  keshlash xatoni ko'paytiradi.
