"""
IGRIS BRAIN — ServerProcess — S5 modullashtirish
=================================================
problems_to_fix.md :: S5 (qism) — server.py god-file'dan ajratilgan.

Jarayon boshqaruvi yordamchilari (system restart / watchdog / ollama):
  _install_fatal_handlers   — faulthandler + sys.excepthook -> logs/server.log.err
  _watchdog_state           — logs/watchdog.json holati (UI ko'rsatadi)
  _ollama_running           — Ollama /api/tags ping
  _port_in_use/_wait_port_free — port bandligini tekshirish/bo'shashini kutish
  _spawn_detached           — fon jarayoni (CREATE_NO_WINDOW, log fayl bilan)
  _server_start_command     — backend'ni asl flaglar bilan qayta ochish komandasi
  _persist_launch_info      — logs/server_launch.json (watchdog o'qiydi)
  _restart_marker_path/_write_restart_marker — restart marker fayli

Holat (server.main() to'ldiradi):
  _RUN_HOST / _RUN_PORT / _RUN_EXTRA_ARGS — asl ishga tushirish manzili/flaglari
  configure(server_path=...) — qayta ishga tushirishda ishlatiladigan skript yo'li

MUHIM: _server_start_command qayta ochadigan fayl — SERVER.PY (shu modul emas).
Shu sababli __file__ o'rniga _SERVER_PATH ishlatiladi; main() uni configure()
orqali aniqlashtiradi (default: shu papkadagi server.py).

Bu modul FAQAT stdlib'dan foydalanadi — server.py import qilib qayta eksport
qiladi (eski ichki nomlar kontrakti saqlanadi).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Optional

__all__ = [
    "_install_fatal_handlers", "_watchdog_state", "_ollama_running",
    "_port_in_use", "_wait_port_free", "_spawn_detached",
    "_server_start_command", "_persist_launch_info",
    "_restart_marker_path", "_write_restart_marker",
    "configure",
]

# Qayta ishga tushiriladigan skript — server.py (shu papkada).
# server.main() configure(server_path=os.path.abspath(__file__)) bilan aniqlashtiradi.
_SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


def configure(server_path: Optional[str] = None,
              host: Optional[str] = None,
              port: Optional[int] = None,
              extra_args: Optional[list] = None) -> None:
    """Jarayon boshqaruvi holatini o'rnatadi (server.main() chaqiradi)."""
    global _SERVER_PATH, _RUN_HOST, _RUN_PORT, _RUN_EXTRA_ARGS
    if server_path:
        _SERVER_PATH = server_path
    if host:
        _RUN_HOST = host
    if port:
        _RUN_PORT = port
    if extra_args is not None:
        _RUN_EXTRA_ARGS = list(extra_args)

# Ishga tushirilgan host/port  -  restart'da xuddi shu manzilda qayta ochiladi.
_RUN_HOST = "127.0.0.1"
_RUN_PORT = 8765
# Asl ishga tushirish flaglari (--model, --no-llm, --base-url, ...)  -  restart'da saqlanadi.
_RUN_EXTRA_ARGS: list[str] = []

# MUHIM: kanonik logs papka — Igris_brain/logs (server/ logs EMAS).
# Watchdog (monitor/watchdog.py) server_launch.json / watchdog.json /
# restart_*.ok larni FAQAT Igris_brain/logs dan kutadi. Avval bu fayllar
# server/logs ga yozilgani uchun watchdog restart ma'lumotlarini umuman
# ko'rmasdi (stale launch.json crash-loop'ga sabab bo'lgandi).
_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)


def _install_fatal_handlers():
    """Kutilmagan xatolarni log'ga yozadi  --  server "jim" qulab tushsa ham
    sabab Igris_brain/logs/server.log.err faylida qoladi.

    faulthandler: C darajasidagi qulash (segfault) traceback'ini ushlaydi.
    sys.excepthook: main thread'da ushlanmagan Python exception'larini
    yozadi (uvicorn tutib olmagan xatolar). Watchdog sababni tez topishi
    uchun juda muhim  --  "birdan offline" holatining ildizi shu yerda qoladi.
    """
    try:
        import faulthandler
        os.makedirs(_LOGS_DIR, exist_ok=True)
        faulthandler.enable(
            open(os.path.join(_LOGS_DIR, "server.log.err"), "a", encoding="utf-8", errors="replace")
        )
    except Exception:
        pass

    def _hook(exc_type, exc, tb):
        import traceback
        try:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            with open(os.path.join(_LOGS_DIR, "server.log.err"), "a", encoding="utf-8") as fh:
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNHANDLED EXCEPTION  -  server yopilmoqda\n")
                traceback.print_exception(exc_type, exc, tb, file=fh)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def _watchdog_state() -> dict:
    """Watchdog holatini logs/watchdog.json'dan o'qiydi (UI ko'rsatishi uchun).

    Watchdog alohida jarayon  --  server u haqida faqat shu fayl orqali biladi.
    Fayl yo'q bo'lsa: watchdog ishlamayapti (eskirgan run.bat bilan ishga
    tushirilgan yoki to'xtatilgan).
    """
    try:
        p = os.path.join(_LOGS_DIR, "watchdog.json")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                running = bool(d.get("running"))
                checked = d.get("checked_at")
                # Watchdog har ~4s yangilaydi. Agar holat ESKI bo'lsa (>15s)  - 
                # jarayon o'ldirilgan bo'lishi mumkin (force-kill stop-faylni
                # yozmasdan tugatadi)  -  UI yolg'on "active" ko'rsatmasligi uchun.
                if running and isinstance(checked, (int, float)):
                    if time.time() - float(checked) > 15.0:
                        running = False
                return {
                    "running": running,
                    "backend_up": bool(d.get("backend_up")),
                    "ollama_up": bool(d.get("ollama_up")),
                    "backend_restarts": int(d.get("backend_restarts") or 0),
                    "ollama_restarts": int(d.get("ollama_restarts") or 0),
                    "last_restart": d.get("last_restart"),
                    "checked_at": checked,
                    "last_error": d.get("last_error"),
                }
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {"running": False}


def _ollama_running(timeout: float = 1.5) -> bool:
    """Ollama ishlayaptimi? (localhost:11434 /api/tags tekshiruvi)."""
    try:
        import urllib.request
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=timeout
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _port_in_use(port: int) -> bool:
    """Port bandmi? (restart port bo'shatishini kutish uchun)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _wait_port_free(port: int, timeout: float = 20.0) -> bool:
    """Port bo'shashini kutadi (eski server jarayoni o'lishini kutish)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_in_use(port):
            return True
        time.sleep(0.5)
    return not _port_in_use(port)


def _spawn_detached(title: str, command: str, cwd: str, log_file: Optional[str] = None):
    """Fon rejimida ko'rinmas jarayon ochadi  --  yangi terminal oynasi YO'Q.

    Windows'da CREATE_NO_WINDOW ishlatiladi (avvalgi `cmd /k` yangi oyna
    ochardi  --  endi UI restart'da hech qanday terminal paydo bo'lmaydi).
    Chiqish log fayliga yoziladi (agar berilsa). Restart qilingan jarayon
    ota-onadan mustaqil yashaydi  --  UI'ni qayta yuklash unga ta'sir qilmaydi.
    """
    out = err = subprocess.DEVNULL
    if log_file:
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
                command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                close_fds=True,
                creationflags=flags,
            )
        return subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            close_fds=True,
        )
    finally:
        # Jarayon o'zi uchun handle'ni ko'chirib oldi  -  ota-onadagi ochiq
        # fayl deskriptorlarini yopamiz (fd leak oldini olinadi).
        for h in (out, err):
            if h is not subprocess.DEVNULL and not h.closed:
                try:
                    h.close()
                except OSError:
                    pass


def _server_start_command(restart_token: str = "") -> str:
    """Backend'ni asl sozlamalari bilan qayta ishga tushirish komandasi.

    Host/port har doim yoziladi (asl argv'dan filtrlanadi, dublikat bo'lmaydi),
    qolgan flaglar  --  `python server.py ...`'dagi asl argv'dan (--model,
    --base-url, --no-llm, --no-memory, ...) olinadi.

    restart_token berilsa  --  yangi jarayon agent'ini muvaffaqiyatli boshlagach
    marker fayl yozadi; eski jarayon o'sha markerni kutib, shundan keyingina
    o'zini tugatadi (restart "soxta" bo'lmaydi  --  yangi server o'lsa, eskisi
    yashab qoladi).
    """
    script = _SERVER_PATH
    parts = [f'"{sys.executable}"', f'"{script}"',
             "--host", _RUN_HOST, "--port", str(_RUN_PORT)]
    if restart_token:
        parts += ["--restart-token", restart_token]
    parts += [str(a) for a in _RUN_EXTRA_ARGS]
    return " ".join(parts)


def _persist_launch_info():
    """Backend'ni asl sozlamalari bilan qayta ishga tushirish komandasini
    logs/server_launch.json fayliga yozadi.

    Watchdog (alohida jarayon) shu faylni o'qib, backend qulab tushsa uni
    XUDDI SHU flaglar bilan qayta ochadi  --  restart'da hech qanday sozlama
    yo'qolmaydi (--model, --no-llm, --base-url, --memory-dir ... saqlanadi).
    """
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)
        with open(os.path.join(_LOGS_DIR, "server_launch.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "command": _server_start_command(),
                "host": _RUN_HOST,
                "port": _RUN_PORT,
                "pid": os.getpid(),
                "started_at": time.time(),
            }, fh, ensure_ascii=False)
    except OSError as exc:
        print(f"[igris][system] launch info write failed: {exc}")


def _restart_marker_path(token: str) -> str:
    """Restart marker fayli  --  yangi jarayon tayyor bo'lgach yozadi."""
    return os.path.join(_LOGS_DIR, f"restart_{token}.ok")


def _write_restart_marker(token: str):
    """Yangi jarayon agent'ini boshlashga muvaffaq bo'ldi  --  marker yoziladi.

    Marker uvicorn.run'gacha bo'lgan barcha xavfli bosqichlardan (create_agent,
    model tanlash, speed sozlamasi) KEYIN yoziladi  --  shu bosqichlarda xato
    bo'lsa marker yozilmaydi va eski jarayon o'zini o'ldirmaydi.
    """
    try:
        os.makedirs(os.path.dirname(_restart_marker_path(token)), exist_ok=True)
        with open(_restart_marker_path(token), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError as exc:
        print(f"[igris][system] restart marker write failed: {exc}")
