# Short Turn

Oxirgi 1-5 tur chat/tool call ma'lumotlari

## Tur: L1 Runtime Memory

## ID: `01-short-turn`

## Asosiy maydonlar

- `session_id`
- `turn_number`
- `user_message`
- `assistant_message`
- `tool_calls`
- `file_changes`
- `decisions`
- `thinking_summary`

## Bog'langan memory turlari

- [[Session]]
- [[Active Context]]
- [[Working Memory]]

## Ishlatish

```python
from memory.schemas import make_01_short_turn
entry = make_01_short_turn(...)
```

#memory #runtime #l1 #01-short-turn
