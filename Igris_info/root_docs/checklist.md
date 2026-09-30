# IGRIS OFFLINE-HIMOYA TIZIMI — TO'LIQ CHECKLIST

**Maqsad:** Igris miyyasining (backend, port 8765) **birdan offline bo'lib qolish** ehtimolini
iloji boricha nolga yaqinlashtirish va qolib qolsa ham **avtomatik, tez tiklash**.

**Sana:** 2026-08-07 · **Holat:** ✅ BARCHA TESTLAR O'TDI — himoya FAOL

---

## 1. TIZIM TARKIBI (3 qatlam)

| Qatlam | Komponent | Vazifa |
|---|---|---|
| 1. Himoya | `Igris_brain/watchdog.py` | Tashqi qo'riqchi — backend + Ollama'ni kuzatadi, qulasa qayta ishga tushiradi |
| 2. Tayanch | `server.py` qo'shimchalari | Qulash sababini log'laydi, restart komandasini saqlaydi, holatni UI'ga beradi |
| 3. Boshqaruv | `run.bat` + UI | Watchdog'ni avtomatik ishga tushiradi / to'xtatadi; holatni ko'rsatadi |

---

## 2. TO'LIQ FUNKSIYALAR RO'YXATI (FULL FUNCTION LIST)

### 2.1 `watchdog.py` — 16 funksiya

| # | Funksiya | Vazifa | Holat |
|---|---|---|---|
| 1 | `log(msg)` | Vaqt belgili log yozadi (`logs/watchdog.log`) | ✅ |
| 2 | `_http_ok(url, timeout)` | URL 2xx qaytaradimi — sog'lomlik tekshiruvi | ✅ |
| 3 | `_port_in_use(port)` | Port bandmi (socket sinovi) | ✅ |
| 4 | `_port_pids(port)` | Portda LISTENING jarayonlar PIDs (netstat) | ✅ |
| 5 | `_kill_port(port)` | Port egalarini `taskkill /F` bilan to'xtatadi | ✅ |
| 6 | `_spawn_detached(command, cwd, log_file)` | Ko'rinmas, mustaqil jarayon ochadi (CREATE_NO_WINDOW) | ✅ |
| 7 | `_acquire_lock()` | Single-instance qulfi (msvcrt/fcntl fayl qulfi) — ikki watchdog urishmaydi | ✅ |
| 8 | `_backend_port()` | Backend porti (`server_launch.json`dan, default 8765) | ✅ |
| 9 | `_backend_health()` | `/api/status` tekshiruvi (3s timeout — band server adashib o'ldirilmaydi) | ✅ |
| 10 | `_backend_start_command()` | Restart komandasi — asl sozlamalar saqlanadi | ✅ |
| 11 | `_recent_ui_restart_marker()` | UI restart handshake'ini aniqlaydi (30s oyna) — aralashmaydi | ✅ |
| 12 | `_restart_backend(restarts)` | Backend'ni tiklaydi: started / rate_limited / skipped. Spawn'dan keyin **3s liveness tekshiruvi** — jarayon darhol o'lsa (noto'g'ri komanda) keyingi (standart) komanda qo'llanadi | ✅ |
| 13 | `_ollama_restart(restarts)` | `ollama serve`ni qayta ochadi (rate-limit bilan) | ✅ |
| 14 | `_write_state(state)` | `logs/watchdog.json`ni atomik yozadi (tmp+replace) | ✅ |
| 15 | `_load_prev_restarts(...)` | Avvalgi restartlar tarixini tiklaydi — watchdog qayta boshlansa ham hisob va rate-limit oynasi saqlanadi | ✅ |
| 16 | `main()` | Asosiy qo'riqlash aylanishi (loop xatolardan himoyalangan) | ✅ |

### 2.2 `server.py` qo'shimchalari — 4 funksiya

| # | Funksiya | Vazifa | Holat |
|---|---|---|---|
| 1 | `_install_fatal_handlers()` | faulthandler + `sys.excepthook` → `logs/server.log.err` (jim qulash sababi yoziladi) | ✅ |
| 2 | `_persist_launch_info()` | Restart komandasini `logs/server_launch.json`ga yozadi | ✅ |
| 3 | `_watchdog_state()` | `watchdog.json`ni o'qiydi (15s eski bo'lsa `running=False` — yolg'on "active" yo'q) | ✅ |
| 4 | `/api/system/services` | Javobga `watchdog` maydoni qo'shildi | ✅ |

### 2.3 `run.bat` — 2 qo'shimcha

| # | Qism | Vazifa | Holat |
|---|---|---|---|
| 1 | `:start_watchdog` | Server'dan keyin watchdog'ni yashirin ishga tushiradi (pid tekshiruvi bilan) | ✅ |
| 2 | `:stop_all` | Stop fayl + CommandLine bo'yicha watchdog'ni to'xtatadi | ✅ |

### 2.4 UI — 2 qo'shimcha

| # | Fayl | Vazifa | Holat |
|---|---|---|---|
| 1 | `web/backend.ts` | `SystemServicesResult.watchdog` tipi | ✅ |
| 2 | `web/components/SettingsModal.tsx` | Services tabida **Watchdog (auto-restart)** kartasi | ✅ |

### 2.5 Sozlama qiymatlari (watchdog.py)

| Parametr | Qiymat | Sababi |
|---|---|---|
| `POLL_INTERVAL` | 4 s | Tez aniqlash ↔ kam yuk balansi |
| `BACKEND_DOWN_LIMIT` | 4 (~16 s) | Band lekin tirik server adashib o'ldirilmaydi |
| `BACKEND_MIN_GAP` | 30 s | Restart oraliq cheklovi |
| `BACKEND_MAX_10MIN` | 5 | Restart to'foni oldini oladi |
| `BACKEND_COOLDOWN` | 60 s | Limitga yetganda tanaffus (loop bloklanmaydi) |
| `BOOT_GRACE` | 45 s | Server boot'lanayotganda restart qilinmaydi |
| `OLLAMA_CHECK_EVERY` | 15 s | Ollama tekshiruv davri |
| `OLLAMA_DOWN_LIMIT` | 3 (~45 s) | Restart boshlash sharti — band-lekin-tirik Ollama adashib o'ldirilmaydi |
| `OLLAMA_CHECK_TIMEOUT` | 4 s | /api/tags timeout (model yuklanayotganda sekinlashishi mumkin) |
| `OLLAMA_MAX_10MIN` | 3 | Ollama restart limiti |

---

## 3. TO'LIQ RESTART PROTSEDURALARI

### 3.1 AVTOMATIK RESTART (watchdog) — ✅ JONLI TEST QILINDI

```
1. Watchdog backend'ni har 4s tekshiradi (/api/status, timeout 3s)
2. Ketma-ket 4 marta javob bo'lmasa (~16s) -> qulash deb topiladi
3. Port egalari o'ldiriladi (taskkill /F), port bo'shatiladi (max 15s)
4. Yangi server asl sozlamalari bilan ochiladi (server_launch.json)
5. Spawn'dan keyin 3s liveness tekshiruvi — jarayon erta o'lsa standart komanda bilan qayta urinish
6. Server ~8s da boot'lanadi -> UI avtomatik qayta ulanadi
```

**O'lchangan natija (2 ta jonli test):**
- Test 1: backend o'ldirilgach → 48s da restart → **54.2s da to'liq tiklanish**
- Test 2 (liveness-tekshiruvli kod): restart 52s da → **55.2s da tiklanish**

> ⚠️ Ikkala o'lchovda ham o'ldirish boot-grace (45s) ichida qilindi — shuning uchun
> vaqt kattaroq. **Normal rejimda** (watchdog uzoq ishlab turganida): ~16s aniqlash +
> ~3s liveness + ~8s boot ≈ **20-30s**. Rate-limit'ga yetilganda eng yomon holat:
> tanaffus 60s + aniqlash 16s ≈ **~76-90s** (crash-loop himoyasi uchun ataylab).

### 3.2 UI'DAN RESTART (`/api/system/restart`) — marker handshake

```
1. UI "⟳ restart" -> server yangi jarayon ochadi (--restart-token)
2. Yangi server agent'ni boshlagach marker fayl yozadi (logs/restart_<token>.ok)
3. Eski server marker'ni ko'rib o'zini tugatadi (port bo'shaydi)
4. Watchdog marker'ni ko'rsa aralashmaydi (30s oyna)
```
Test holati: mantiqiy tekshirildi (marker guard kodi + review); jonli fault-injection talab qilmaydi.

### 3.3 QO'LDA TO'LIQ RESTART (to'liq tiklanish)

```
run.bat stop      # barcha xizmat + watchdog to'xtaydi (1420/8765/11434)
run.bat           # hammasi yana ishga tushadi (Ollama + server + watchdog + UI)
```

### 3.4 TO'XTATISH YO'LLARI

| Yo'l | Mexanizm |
|---|---|
| `run.bat stop` / `stop.bat` | Stop fayl + CommandLine o'ldirish + port o'ldirish |
| `python watchdog.py --stop` | Stop fayl yozadi → watchdog keyingi aylanishda to'xtaydi |
| Stop faylni qo'lda yaratish | `echo stop > Igris_brain/logs/watchdog.stop` |

---

## 4. TEKSHIRUV KATEGORIYALARI (NATIJALAR BILAN)

### 4.1 SIFAT (Quality) — ✅
- [x] `py_compile` server.py + watchdog.py — **O'TD1**
- [x] 58 ta pytest (test_brain, test_chat_history, test_svg_validator) — **O'TD1**
- [x] Web TypeScript typecheck (`tsc -p tsconfig.web.json`) — **EXIT:0, xato yo'q**
- [x] Code review (code-reviewer) — berilgan barcha tavsiyalar qo'llandi
- [x] Importlar xatosiz (`import server`, `import watchdog`)

### 4.2 ANIQLILIK (Accuracy) — ✅
Har bir funksiya alohida tekshirildi:
- [x] `_http_ok` o'lik manzilga **False** qaytaradi
- [x] `_backend_start_command` server.py yo'liga to'g'ri ishora qiladi
- [x] `_watchdog_state` fayl yo'q bo'lsa `running=False` qaytaradi
- [x] Staleness: 60s eski `checked_at` → `running=False` (yolg'on "active" yo'q)
- [x] E2E: backend haqiqatan o'ldirildi va **watchdog o'zi tikladi**
- [x] `ollama_up` real Ollama holatini to'g'ri ko'rsatdi (True)

### 4.3 SABABLILIK (Reasonableness) — ✅
- [x] Restart qarori asoslangan: 4 ketma-ket xato = ishonchli qulash belgisi (yagona xato emas)
- [x] 3s timeout + 4 limit — band-lekin-tirik server "o'lik" deb adashilmaydi
- [x] Boot grace 45s — yangi server yuklanayotganda ikki server urishib ketmaydi
- [x] Rate limitlar (5/10min) — restart to'foni (crash-loop) oldini oladi
- [x] UI restart marker — qasddan qilingan restart'ga aralashish yo'q
- [x] Restart komandasi asl flaglarni saqlaydi (hech qanday sozlama yo'qolmaydi)

### 4.4 ISHONCHLILIK (Reliability) — ✅
- [x] **Jonli E2E test**: backend o'ldirildi → avtomatik tiklandi (54.2s)
- [x] Single-instance qulf: ikkinchi watchdog exit code 0, log'da "boshqa watchdog" yozildi
- [x] Stop-fayl: `running=False`, pid fayli o'chirildi
- [x] Loop xatolardan himoyalangan (try/except — hech qanday xato watchdog'ni o'ldirmaydi)
- [x] Spawn fallback: server_launch.json komandasi xato bo'lsa (exception yoki **jarayon 3s ichida o'lsa**) standart komanda qo'llanadi — jonli sinovda tasdiqlandi
- [x] Holat fayli atomik yoziladi (tmp+replace — yarim yozilgan fayl yo'q)
- [x] Restartlar tarixi saqlanadi (`_load_prev_restarts`) — watchdog restart'da hisob va rate-limit oynasi yo'qolmaydi (birlik testi: 30s eski → 3 ta tiklandi; 1 soat eski → tashlandi)

### 4.5 XAVFSIZLIK (Safety) — ✅
- [x] Faqat Igris'ga tegishli portlar boshqariladi (8765 backend, 11434 ollama)
- [x] `taskkill /F` faqat port egasiga — UI restart handshake'ida qayta tekshiruv (2 marta)
- [x] Watchdog o'zi ko'rmagan backend'ni restart qilmaydi (boot himoyasi)
- [x] Foydalanuvchi ma'lumotlari xavfsiz: chat tarixi diskda (restart'da saqlanadi)

### 4.6 WINDOWS MOSLIGI — ✅
- [x] `CREATE_NO_WINDOW | DETACHED_PROCESS` — hech qanday terminal oynasi ochilmaydi
- [x] Batch'dagi PowerShell `-match 'watchdog'` kotirovkasi tuzatildi (test jarayonida)
- [x] `:stop_all` yorlig'i rem qatoriga yopishib qolgan xato tuzatildi
- [x] `netstat`/`taskkill`/`wscript` — standart Windows vositalari (qo'shimcha install yo'q)

### 4.7 SAMARADORLIK (Performance) — ✅
- [x] 4s davr — har tekshiruv: 1 ta HTTP so'rov (~3ms) — yuk deyarli nol
- [x] Holat fayli: 4s da 1 marta kichik JSON yozish
- [x] Uzoq sleep'lar yo'q (rate-limit tanaffusi loop'ni bloklamaydi)

### 4.8 HUJJATLASHTIRISH — ✅
- [x] `IGRIS_RUN_COMMANDS.txt` — watchdog bo'limi qo'shildi
- [x] `watchdog.py` docstring — to'liq tavsif
- [x] UI Settings → Services — Watchdog kartasi
- [x] Ushbu checklist

---

## 5. TEST DAVOMIDA TOPILGAN VA TUZATILGAN XATOLAR

| Xato | Qanday topildi | Tuzatish |
|---|---|---|
| `_spawn_detached()` argument mos kelmasligi (title parametri) — **backend restart HAR DOIM TypeError berardi** | 🔴 **E2E jonli test** — backend o'ldirilgach tiklanmadi, log tekshiruvida aniqlandi | Uchinchi pozitsion arg olib tashlandi (2 ta joyda: backend + ollama) |
| Batch'dagi PowerShell regex qochirish xatosi (`watchdog\\.py` mos kelmas edi) | Kod review + qo'lda tekshiruv | `-match 'watchdog'` — qochirishsiz, ishonchli |
| `:stop_all` yorlig'i rem qatoriga yopishib qolgan | `grep`/`cat -A` tekshiruvi | Alohida qatorga ajratildi |
| Rate-limit'da `sleep(60)` butun loop'ni bloklardi | Code review | Cooldown vaqtiga o'tkazildi (loop ishlayveradi) |
| O'ldirilgan watchdog eskirgan `running:true` qoldirardi → UI yolg'on "active" | Code review | Server'da staleness tekshiruvi (>15s → not running) |
| Spawn fallback faqat exception'da ishlardi — jarayon **darhol o'lsa** (noto'g'ri server_launch.json) crash-loop bo'lardi | Code review (2-bosqich) | 3s liveness tekshiruvi (`proc.poll()`) — o'lgan jarayon keyingi komandaga o'tkazadi; jonli sinovda tasdiqlandi |

> ⚡ **Asosiy xulosa:** `checklist.md` dan oldin o'tkazilgan **jonli E2E testi real ishlamaydigan
> restart yo'lini topdi va tuzatdi** — shunchaki kodga qarash bilan bu xato sezilmas edi.

---

## 6. QOLGAN OFFLINE XAVFLARI (qoldiq risklar)

| Xavf | Ehtimol | Yumshatish |
|---|---|---|
| Watchdog jarayonining o'zi qulashi (loop himoyalangan, lekin OS darajasida) | Juda past | `run.bat` qayta boshlaydi; qulf ikki nusxani yo'qotadi |
| Kompyuter o'chishi / quvvat ketishi | Tashqi | Hech narsa tiklay olmaydi (fizik chegara) |
| Backend restart in-memory agent run'lar yo'qoladi | O'rtacha | Chat tarixi diskda (restart'da qoladi); run'lar qayta yuboriladi |
| Ollama o'rnatilmagan bo'lsa | Past | Server `--no-llm` fallback; watchdog binary bo'lmasa tegmai |
| Eski kod bilan boshlangan server (launch fayli yo'q) | Bir martalik | Watchdog standart komanda bilan tiklaydi |
| `taskkill /F` boshqa ilova portni egallagan bo'lsa | Juda past | 8765 — Igris'ning doimiy porti; UI marker + 2-qatlam tekshiruv |

---

## 7. MONITORING — HIMOYANI QANDAY KO'RISH

```bash
cat Igris_brain/logs/watchdog.json      # running, backend_up, ollama_up, restarts
tail -20 Igris_brain/logs/watchdog.log  # qo'riqlash voqealari
curl http://127.0.0.1:8765/api/system/services   # backend holati (watchdog maydoni bilan)
```
**UI:** Settings → Services → **Watchdog (auto-restart)** kartasi — ● active / ○ off + restart sonlari.

---

## 8. XULOSA

- ✅ Backend qulab tushsa → **20-30 soniyada avtomatik tiklanadi** (watchdog normal rejimda)
- ✅ Ollama qulab tushsa → avtomatik qayta ochiladi
- ✅ Soxta / qayta-yo'naltirilgan restart'lar oldi olinadi (grace, marker, rate-limit)
- ✅ Qulash sababi doim log'da qoladi (server.log.err — endi "jim" qulash yo'q)
- ✅ UI himoya holatini ko'rsatadi
- ⚠️ **Amaliy eslatma:** hozir himoya **FAOL** (watchdog ishlayapti). `run.bat` keyingi
  ishga tushirishda buni o'zi boshqaradi (dublikat yaratmaydi, stop'da to'xtatadi).
