# Session

Butun sessiya tarixi — boshidan oxirigacha

## Tur: L1 Runtime Memory

## ID: `02-session`

## Asosiy maydonlar

- `status`
- `started_at`
- `updated_at`
- `total_turns`
- `total_tool_calls`
- `total_tokens_used`
- `files_read`
- `files_modified`
- `errors_encountered`

## Bog'langan memory turlari

- [[Short Turn]]
- [[Active Context]]
- [[Decision Log]]

## Ishlatish

```python
from memory.schemas import make_02_session
entry = make_02_session(...)
```

#memory #runtime #l1 #02-session
