# Runtime Cache

Tez kirish uchun saqlangan ma'lumotlar

## Tur: L1 Runtime Memory

## ID: `12-cache`

## Asosiy maydonlar

- `cache_entries`
- `cache_hits`
- `cache_misses`
- `eviction_count`

## Bog'langan memory turlari

- [[Execution]]
- [[Temp Knowledge]]
- [[Prompt Buffer]]

## Ishlatish

```python
from memory.schemas import make_12_cache
entry = make_12_cache(...)
```

#memory #runtime #l1 #12-cache
