"""
IGRIS BRAIN WATCHDOG — external supervisor
==========================================
Igris miyyasining "birdan offline bo'lib qolishini" oldini oladi.

Backend (server.py, port 8765) yoki Ollama (port 11434) qulab tushsa yoki
javob bermay qolsa — bu mustaqil jarayon ularni AVTOMATIK qayta ishga
tushiradi. Server'dan mustaqil ishlaydi (alohida jarayon), shuning uchun
server o'lsa ham o'zi yashab qoladi.

Ishga tushirish:
    python monitor/watchdog.py    # run.bat buni avtomatik chaqiradi
    python monitor/watchdog.py --stop   # faqat stop faylini qoldirib chiqadi

Qo'riqlash:
  1. Backend — har ~4 soniyada /api/status tekshiradi; ketma-ket 4 marta
     javob bo'lmasa (≈16 soniya) backend'ni qayta ishga tushiradi.
  2. Ollama  — har ~15 soniyada /api/tags tekshiradi (timeout 4s); ketma-ket
     3 marta javob bo'lmasa (≈45 soniya) `ollama serve` ni qayta ochadi
     (agar o'rnatilgan bo'lsa). Band-lekin-tirik Ollama adashib o'ldirilmaydi.

Xavfsizlik (soxta/qayta-yo'naltirilgan restartlar yo'q):
  - UI'dan qilingan restart'ga xalaqit bermaydi (grace davri + marker tekshiruvi)
  - Restart'lar cheklangan: backend 10 daqiqada max 5 marta, ollama 3 marta
  - Backend hech qachon "ko'rilmagan" bo'lsa (hali boot'lanayotgan) — restart YO'Q
  - Bitta nusxa ishlaydi (fayl qulfi: logs/watchdog.lock)

Loglar:     Igris_brain/logs/watchdog.log
Holat:      Igris_brain/logs/watchdog.json  (UI /api/system/services shu yerdan o'qiydi)
To'xtatish: run.bat stop  (yoki logs/watchdog.stop faylini yaratib qo'ying)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

# MUHIM: bu fayl monitor/ papkasida — BRAIN_DIR esa Igris_brain bo'lishi kerak
# (loglar, pid/lock/stop fayllar va server_launch.json HAMMASI Igris_brain/logs
# da; run.bat ham shu yerni kutadi). Eskirgan yo'llar run.bat'dagi start_server
# bilan kelishmovchilik tug'dirib, watchdog hech qanday xatosiz ishlamay qolardi.
BRAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BRAIN_DIR, "logs")

WATCHDOG_LOG = os.path.join(LOGS_DIR, "watchdog.log")
WATCHDOG_STATE = os.path.join(LOGS_DIR, "watchdog.json")
WATCHDOG_PID = os.path.join(LOGS_DIR, "watchdog.pid")
WATCHDOG_LOCK = os.path.join(LOGS_DIR, "watchdog.lock")
WATCHDOG_STOP = os.path.join(LOGS_DIR, "watchdog.stop")
SERVER_LAUNCH = os.path.join(LOGS_DIR, "server_launch.json")

# Qo'riqlash sozlamalari
POLL_INTERVAL = 4.0          # backend tekshiruv davri (sekund)
BACKEND_DOWN_LIMIT = 4       # shuncha ketma-ket xatodan keyin restart (≈16s)
BACKEND_MIN_GAP = 30.0       # ikkita backend restart orasidagi eng kam vaqt
BACKEND_MAX_10MIN = 8        # 10 daqiqada eng ko'p backend restart (oldin 5 edi)
BOOT_GRACE = 45.0            # ishga tushgach shuncha vaqt backend'ni "ko'rish" kutamiz
# EXPONENTIAL BACKOFF: restart urinishlari orasida sekin o'suvchi tanaffus
# 1-restart: 30s, 2-restart: 60s, 3-restart: 120s, 4-restart: 240s, ...
BACKOFF_BASE = 30.0          # boshlang'ich backoff (sekund)
BACKOFF_MAX = 600.0          # maksimal backoff (10 daqiqa)
BACKOFF_FACTOR = 2.0         # har restart'da 2 baravar oshadi

OLLAMA_CHECK_EVERY = 15.0    # ollama tekshiruv davri (sekund)
OLLAMA_DOWN_LIMIT = 3        # shuncha ketma-ket xatodan keyin `ollama serve` (≈45s)
OLLAMA_CHECK_TIMEOUT = 4.0   # /api/tags timeout — model yuklanayotganda sekinlashishi mumkin
OLLAMA_MIN_GAP = 45.0        # ikkita ollama restart orasidagi eng kam vaqt
OLLAMA_MAX_10MIN = 5

OLLAMA_URL = "http://127.0.0.1:11434/api/tags"


def log(msg: str):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(WATCHDOG_LOG, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    """URL'ga so'rov — 2xx qaytsa True."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _port_pids(port: int) -> set[str]:
    """Portda LISTENING qilayotgan jarayon PIDs (Windows netstat)."""
    pids: set[str] = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout or ""
        for line in out.splitlines():
            if f":{port} " not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    except Exception:
        pass
    return pids


def _kill_port(port: int) -> bool:
    """Portni egallagan jarayon(lar)ni to'xtatadi. Qaytaradi: o'ldirildimi."""
    killed = False
    for pid in _port_pids(port):
        try:
            subprocess.run(["taskkill", "/PID", pid, "/F"],
                           capture_output=True, timeout=10)
            killed = True
        except Exception:
            pass
    return killed


def _spawn_detached(command: str, cwd: str, log_file: str):
    """Fon rejimida ko'rinmas jarayon ochadi (oyna yo'q, log'ga yozadi)."""
    out = err = subprocess.DEVNULL
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        out = open(log_file, "a", encoding="utf-8", errors="replace")
        err = open(log_file + ".err", "a", encoding="utf-8", errors="replace")
    except OSError:
        out = err = subprocess.DEVNULL
    try:
        if os.name == "nt":
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags |= subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            return subprocess.Popen(
                command, shell=True, cwd=cwd,
                stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                close_fds=True, creationflags=flags,
            )
        return subprocess.Popen(
            command, shell=True, cwd=cwd, start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=out, stderr=err, close_fds=True,
        )
    finally:
        for h in (out, err):
            if h is not subprocess.DEVNULL and not h.closed:
                try:
                    h.close()
                except OSError:
                    pass


# ---------------------------------------------------------------------- #
# Single-instance qulfi — ikkita watchdog bir-biri bilan urishmaydi.
# ---------------------------------------------------------------------- #

_lock_fh = None


def _acquire_lock() -> bool:
    """logs/watchdog.lock faylini egallaydi. Band bo'lsa False."""
    global _lock_fh
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        _lock_fh = open(WATCHDOG_LOCK, "a+", encoding="utf-8")
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                _lock_fh.close()
                _lock_fh = None
                return False
        import fcntl
        try:
            fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            _lock_fh.close()
            _lock_fh = None
            return False
    except Exception:
        # Qulf olinmasa ham ishlayveramiz (pid fayli zaxira)
        return True


# ---------------------------------------------------------------------- #
# Backend restart
# ---------------------------------------------------------------------- #

def _backend_port() -> int:
    """Backend porti — server_launch.json'dan (fayl yo'q bo'lsa 8765)."""
    try:
        with open(SERVER_LAUNCH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return int(data.get("port") or 8765)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return 8765


def _backend_health() -> tuple[bool, str]:
    """(up, url) — server_launch.json'dagi port bo'yicha tekshiradi.

    Yengil /api/health endpoint'ini afzal ko'radi (agent/LLM ga tegmagan
    uchun model yuklanayotganda ham TEZ javob beradi); eski serverlarda
    /api/health bo'lmasa /api/status ga tushadi. Timeout 3s + ketma-ket 4
    xato (≈16s) — band lekin tirik server'ni "o'lik" deb adashib
    o'ldirmaslik uchun (uzoq run paytida /api/status sekinlashishi mumkin).
    """
    port = _backend_port()
    for path in ("/api/health", "/api/status"):
        url = f"http://127.0.0.1:{port}{path}"
        if _http_ok(url, timeout=3.0):
            return True, url
    return False, f"http://127.0.0.1:{port}/api/status"


def _backend_start_command() -> str:
    """Backend'ni asl sozlamalari bilan qayta ishga tushirish komandasi.

    Avval server.py o'zi yozgan logs/server_launch.json o'qiladi (restart'da
    asl flaglar saqlanadi); fayl yo'q bo'lsa — standart komanda.
    """
    try:
        with open(SERVER_LAUNCH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        cmd = data.get("command") if isinstance(data, dict) else None
        if cmd and isinstance(cmd, str) and cmd.strip():
            # server_launch.json eski versiyadan qolgan bo'lishi mumkin.
            # Mavjud bo'lmagan server.py'ni qayta-qayta ishga tushirib,
            # watchdog crash-loop hosil qilmasin.
            script_tokens = re.findall(
                r'"([^"]+server\.py)"|(?<![\w/\\])([^\s"\']+server\.py)',
                cmd,
                flags=re.IGNORECASE,
            )
            scripts = [a or b for a, b in script_tokens]
            if scripts and any(os.path.isfile(os.path.expandvars(p)) for p in scripts):
                return cmd.strip()
            log(f"[backend] stale launch command rejected: {cmd}")
    except (OSError, json.JSONDecodeError):
        pass
    # server.py server/ paketi ICHIDA — ildizda emas (eskirgan yo'l watchdog
    # restart qilganda "can't open file ...Igris_brain\\server.py" berardi).
    script = os.path.abspath(os.path.join(BRAIN_DIR, "server", "server.py"))
    return f'"{sys.executable}" "{script}" --host 127.0.0.1 --port 8765'


def _recent_ui_restart_marker() -> bool:
    """UI restart handshake'ida marker fayl yoziladi — 30s ichida bo'lsa
    bu intentli restart (watchdog aralashmaydi)."""
    try:
        if not os.path.isdir(LOGS_DIR):
            return False
        cutoff = time.time() - 30.0
        for name in os.listdir(LOGS_DIR):
            if name.startswith("restart_") and name.endswith(".ok"):
                p = os.path.join(LOGS_DIR, name)
                if os.path.getmtime(p) > cutoff:
                    return True
    except OSError:
        pass
    return False


def _restart_backend(backend_restarts: list[float]) -> str:
    """Backend'ni qayta ishga tushiradi. EXPONENTIAL BACKOFF bilan.

    Qaytaradi:
      started      — yangi jarayon ochildi
      rate_limited — 10 daqiqada limitga yetildi (loop tanaffus oladi)
      skipped      — hali kutish kerak (backoff / UI restart / port band)

    Uzoq sleep'lar YO'Q — asosiy aylanish bu yerda bloklanmaydi (Ollama
    monitoring va stop-fayl tekshiruvi uzluksiz ishlayveradi).

    EXPONENTIAL BACKOFF: har restart'dan keyin keyingisi uzoqroq kutish
    kerak (1: 30s, 2: 60s, 3: 120s, 4: 240s, 5: 480s, 6+: 600s max).
    Bu "thrashing" oldini oladi — server qayt-qayta qulab tushsa ham
    watchdog sabr bilan kutadi, lekin hech qachon to'xtamaydi.
    """
    now = time.time()
    # Rate limit: 10 daqiqada max BACKEND_MAX_10MIN restart
    window = [t for t in backend_restarts if now - t < 600]
    if len(window) >= BACKEND_MAX_10MIN:
        log(f"[backend] rate-limit: 10 daqiqada {len(window)} restart — tanaffus")
        return "rate_limited"
    # EXPONENTIAL BACKOFF: qanchalik ko'p restart bo'lsa, shuncha uzoq kutish
    restart_count = len(backend_restarts)
    backoff = min(BACKOFF_BASE * (BACKOFF_FACTOR ** restart_count), BACKOFF_MAX)
    if backend_restarts:
        elapsed = now - backend_restarts[-1]
        if elapsed < backoff:
            remaining = backoff - elapsed
            if remaining > 10:  # faqat 10s dan ko'p qoldiqda log yozamiz
                log(f"[backend] backoff: {remaining:.0f}s qoldi (restart #{restart_count + 1})")
            return "skipped"
    # UI restart handshake'ida — aralashmaymiz
    if _recent_ui_restart_marker():
        log("[backend] UI restart handshake'da — kutamiz")
        return "skipped"

    # Port bo'shatamiz (eski server o'lik bo'lsa ham qoldiq jarayon bo'lishi mumkin)
    port = _backend_port()
    if _port_in_use(port):
        # O'ldirishdan OLDIN yana bir marta tekshiramiz — shu orada UI restart
        # boshlangan bo'lsa, yangi server'ni o'ldirib qo'ymaymiz.
        if _recent_ui_restart_marker():
            log("[backend] port band, lekin UI restart handshake'da — aralashmaymiz")
            return "skipped"
        log(f"[backend] port {port} band — eski jarayonni to'xtatamiz")
        _kill_port(port)
    # Port bo'shashini kutamiz (max ~15s)
    deadline = time.time() + 15.0
    while time.time() < deadline and _port_in_use(port):
        time.sleep(0.5)
    if _port_in_use(port):
        log(f"[backend] port {port} bo'shamadi — restart keyinga qoldirildi")
        return "skipped"

    # Avval server_launch.json'dagi komanda, muvaffaqiyatsiz bo'lsa — standart.
    commands = [_backend_start_command()]
    default_cmd = (
        f'"{sys.executable}" '
        f'"{os.path.join(BRAIN_DIR, "server", "server.py")}" --host 127.0.0.1 --port {port}'
    )
    if commands[0] != default_cmd:
        commands.append(default_cmd)
    for cmd in commands:
        log(f"[backend] qayta ishga tushirilmoqda: {cmd}")
        proc = None
        try:
            proc = _spawn_detached(
                cmd, BRAIN_DIR,
                log_file=os.path.join(LOGS_DIR, "server.log"),
            )
        except Exception as exc:
            log(f"[backend] restart xatosi: {exc}")
            continue  # keyingi komanda bilan urinamiz
        # Yangi jarayon erta chiqib ketdimi? (server_launch.json eskirgan /
        # noto'g'ri komanda -> argparse xatosi -> darhol o'lim). Shu holda
        # "started" deb hisoblanmaydi — keyingi komanda (standart) qo'llanadi.
        if proc is not None:
            try:
                time.sleep(3.0)
                if proc.poll() is not None:
                    log(f"[backend] yangi jarayon erta chiqib ketdi (exit={proc.poll()}) — keyingi komanda")
                    continue
            except Exception:
                pass
        backend_restarts.append(time.time())
        return "started"
    return "skipped"


# ---------------------------------------------------------------------- #
# Ollama restart
# ---------------------------------------------------------------------- #

def _ollama_restart(ollama_restarts: list[float]) -> bool:
    """Ollama'ni qayta ishga tushiradi. EXPONENTIAL BACKOFF bilan."""
    now = time.time()
    window = [t for t in ollama_restarts if now - t < 600]
    if len(window) >= OLLAMA_MAX_10MIN:
        return False
    # EXPONENTIAL BACKOFF: 45s, 90s, 180s, ...
    restart_count = len(ollama_restarts)
    backoff = min(OLLAMA_MIN_GAP * (BACKOFF_FACTOR ** restart_count), BACKOFF_MAX)
    if ollama_restarts and now - ollama_restarts[-1] < backoff:
        return False
    log("[ollama] qayta ishga tushirilmoqda: ollama serve")
    try:
        _spawn_detached(
            "ollama serve", os.path.expanduser("~"),
            log_file=os.path.join(LOGS_DIR, "ollama.log"),
        )
        ollama_restarts.append(time.time())
        return True
    except Exception as exc:
        log(f"[ollama] restart xatosi: {exc}")
        return False


# ---------------------------------------------------------------------- #
# Holat fayli
# ---------------------------------------------------------------------- #

def _load_prev_restarts(last_key: str, count_key: str) -> list:
    """Avvalgi watchdog.json'dan yaqin restartlar ro'yxatini tiklaydi.

    Watchdog qayta ishga tushsa ham: (1) UI "N x restart" hisobini yo'qotmaydi,
    (2) 10 daqiqalik rate-limit oynasi qayta boshlanmaydi (crash-loop'da tez
    tiklanadigan xato — restart limiti qayta to'ldirilmaydi). Faqat so'nggi
    10 daqiqadagi restartlar qo'shiladi (eskilari rate-limit uchun ahamiyatsiz).
    """
    try:
        with open(WATCHDOG_STATE, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            return []
        last = d.get(last_key)
        n = int(d.get(count_key) or 0)
        if isinstance(last, (int, float)) and time.time() - float(last) < 600:
            return [float(last)] * min(max(n, 1), 5)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return []


def _write_state(state: dict):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        tmp = WATCHDOG_STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        os.replace(tmp, WATCHDOG_STATE)
    except OSError:
        pass


# ---------------------------------------------------------------------- #
# Asosiy aylanish
# ---------------------------------------------------------------------- #

def main() -> int:
    os.makedirs(LOGS_DIR, exist_ok=True)
    # To'xtatish fayli — run.bat stop undan foydalanadi
    if os.path.isfile(WATCHDOG_STOP):
        try:
            os.unlink(WATCHDOG_STOP)
        except OSError:
            pass

    if not _acquire_lock():
        log("boshqa watchdog allaqachon ishlayapti — chiqamiz")
        return 0

    try:
        with open(WATCHDOG_PID, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass

    log("watchdog ishga tushdi (backend + Ollama qo'riqlanadi)")

    # Boot grace — run.bat server'ni endi ishga tushiryapti; bu vaqt ichida
    # server "ko'rinmasa" ham restart qilmaymiz (ikki server urishib ketmasin).
    boot_until = time.time() + BOOT_GRACE
    seen_backend_up = False

    # Avvalgi holatdan yaqin restartlar tarixini o'qiymiz — watchdog qayta
    # boshlansa ham UI hisoblagichi va rate-limit oynasi saqlanib qoladi.
    backend_restarts = _load_prev_restarts("last_restart", "backend_restarts")
    ollama_restarts = _load_prev_restarts("last_ollama_restart", "ollama_restarts")
    backend_down_streak = 0
    ollama_down_streak = 0
    last_ollama_check = 0.0
    # Ollama holati oxirgi tekshiruvdan beri saqlanadi — aks holda state faylda
    # har aylanishda "ollama_up: False" yozilib, tekshiruvlar orasida (≈15s)
    # UI Ollama'ni "o'chdi" deb ko'rsatardi (yolg'on signal).
    ollama_up_known = False
    # Rate-limit tanaffusi tugaydigan vaqt — loop bloklanmaydi, shunchaki
    # restart urinishlari shu vaqtgacha o'tkazib yuboriladi.
    backend_cooldown_until = 0.0

    while True:
        try:
            # To'xtatish buyrug'i
            if os.path.isfile(WATCHDOG_STOP):
                log("stop fayli topildi — watchdog to'xtaydi")
                try:
                    os.unlink(WATCHDOG_STOP)
                except OSError:
                    pass
                break

            now = time.time()
            state = {
                "running": True,
                "pid": os.getpid(),
                "checked_at": now,
                "backend_up": False,
                "ollama_up": ollama_up_known,
                "backend_restarts": len(backend_restarts),
                "ollama_restarts": len(ollama_restarts),
                "last_restart": backend_restarts[-1] if backend_restarts else None,
                "last_error": None,
            }
            if ollama_restarts:
                state["last_ollama_restart"] = ollama_restarts[-1]

            # ---- Backend ----
            try:
                up, _url = _backend_health()
                state["backend_up"] = up
                if up:
                    seen_backend_up = True
                    backend_down_streak = 0
                else:
                    backend_down_streak += 1
                    # Restart shartlari:
                    #  - ketma-ket DOWN_LIMIT ta xato
                    #  - boot grace o'tgan (run.bat server'ni endi yuklayotgan bo'lishi mumkin)
                    #  - server HECH QACHON ko'rilmagan bo'lsa ham — lekin server_launch.json
                    #    mavjud bo'lsa (server boshlangach yoziladi) — demak server kerak,
                    #    qulab tushgan bo'lsa qayta ishga tushiriladi
                    launch_info = os.path.isfile(SERVER_LAUNCH)
                    if (
                        backend_down_streak >= BACKEND_DOWN_LIMIT
                        and now > boot_until
                        and (seen_backend_up or launch_info)
                    ):
                        if now < backend_cooldown_until:
                            # Rate-limit tanaffusi — asosiy aylanish ishlayveradi
                            backend_down_streak = 0
                        else:
                            log(f"[backend] javob bermayapti ({backend_down_streak} tekshiruv) — restart")
                            result = _restart_backend(backend_restarts)
                            if result == "started":
                                state["backend_restarts"] = len(backend_restarts)
                                state["last_restart"] = backend_restarts[-1]
                            elif result == "rate_limited":
                                backend_cooldown_until = time.time() + BACKEND_COOLDOWN
                            backend_down_streak = 0
            except Exception as exc:
                state["last_error"] = f"backend check: {exc}"

            # ---- Ollama ----
            try:
                if now - last_ollama_check >= OLLAMA_CHECK_EVERY:
                    last_ollama_check = now
                    ollama_up = _http_ok(OLLAMA_URL, timeout=OLLAMA_CHECK_TIMEOUT)
                    ollama_up_known = ollama_up
                    state["ollama_up"] = ollama_up
                    if ollama_up:
                        ollama_down_streak = 0
                    else:
                        ollama_down_streak += 1
                        if ollama_down_streak >= OLLAMA_DOWN_LIMIT:
                            if shutil.which("ollama"):
                                log(f"[ollama] javob bermayapti ({ollama_down_streak} tekshiruv) — restart")
                                _ollama_restart(ollama_restarts)
                                state["ollama_restarts"] = len(ollama_restarts)
                                if ollama_restarts:
                                    state["last_ollama_restart"] = ollama_restarts[-1]
                            else:
                                state["last_error"] = "ollama executable not found"
                            ollama_down_streak = 0
            except Exception as exc:
                state["last_error"] = f"ollama check: {exc}"

            _write_state(state)
        except Exception as exc:
            # Hech qanday kutilmagan xato watchdog'ni o'ldirmaydi — keyingi
            # aylanishda davom etadi (offline himoya DOIMO tirik qoladi).
            log(f"[watchdog] aylanish xatosi (e'tiborsiz qilindi): {exc}")
        time.sleep(POLL_INTERVAL)

    # Tozalash — running=False, lekin restart HISOBLAGICHLARI saqlanadi
    # (keyingi watchdog `_load_prev_restarts` orqali ularni tiklaydi: UI hisobi
    # va rate-limit oynasi tez stop/start aylanishlarida ham yo'qolmaydi).
    final_state = dict(state) if isinstance(state, dict) else {}
    final_state.update({"running": False, "pid": os.getpid(), "checked_at": time.time()})
    _write_state(final_state)
    try:
        if os.path.isfile(WATCHDOG_PID):
            os.unlink(WATCHDOG_PID)
    except OSError:
        pass
    log("watchdog to'xtadi")
    return 0


if __name__ == "__main__":
    if "--stop" in sys.argv:
        try:
            with open(WATCHDOG_STOP, "w", encoding="utf-8") as fh:
                fh.write("stop")
            print("stop fayl yozildi — watchdog keyingi aylanishda to'xtaydi")
        except OSError as exc:
            print(f"xato: {exc}")
        raise SystemExit(0)
    raise SystemExit(main())
