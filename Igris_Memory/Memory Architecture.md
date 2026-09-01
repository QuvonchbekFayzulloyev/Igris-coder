# Memory Architecture

Igris Memory tizimi ikki qatlamdan iborat:

## L1 Runtime Memory

Sessiya davomida ishlatiladigan vaqtinchalik ma'lumotlar. Tez ishlaydi, lekin vaqtinchalik.

- [[L1 Runtime Memory Overview]]
- 18 ta tur
- TTL (Time To Live) mavjud

## L2 Persistent Memory

Doimiy saqlanadigan uzoq muddatli xotira. Sekinroq, lekin doimiy.

- [[L2 Persistent Memory Overview]]
- 24 ta tur
- JSONL formatida saqlanadi

## Bog'lanishlar

Har bir memory type boshqalariga bog'langan. Bu bog'lanishlar:
- [[01-short-turn]] → [[02-session]] → [[14-decision-log]]
- [[05-task]] → [[06-execution]] → [[07-observation]]
- [[03-knowledge]] → [[06-pattern]] → [[17-codemap]]

## Ma'lumot oqimi

1. Foydalanuvchi xabar beradi
2. [[01-short-turn]] ga saqlanadi
3. [[03-active-context]] yangilanadi
4. [[04-working]] reasoning qiladi
5. [[06-execution]] bajaradi
6. [[07-observation]] kuzatadi
7. [[14-decision-log]] qaror qayd etadi
8. [[15-reflection]] tahlil qiladi
9. Kerakli ma'lumotlar [[L2 Persistent Memory]] ga o'tkaziladi

#memory #architecture
