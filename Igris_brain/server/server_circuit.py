"""
IGRIS BRAIN — ServerCircuit — S5 modullashtirish
================================================
problems_to_fix.md :: S5 (qism) — server.py god-file'dan ajratilgan.

Circuit Breaker  -  agent xatolarini kuzatadi, avtomatik tiklaydi:
  CLOSED     — normal ish (xato yo'q yoki kam)
  OPEN       — og'ir xato: agent qayta yaratiladi (cooldown davomida)
  HALF_OPEN  — cooldown tugadi: birinchi muvaffaqiyatli chaqiruv bilan
               yana CLOSED ga qaytadi

`_CIRCUIT` — server uchun yagona nusxa. Faqat stdlib (fastapi yo'q).
"""

from __future__ import annotations

import threading
import time

__all__ = ["CircuitBreaker", "_CIRCUIT"]

# ------------------------------------------------------------------ #
# Circuit Breaker  --  agent xatolarini kuzatadi, avtomatik tiklaydi
# ------------------------------------------------------------------ #

class CircuitBreaker:
    """Agent stabilizatsiya: ketma-ket xatolarni qayd etadi, og'ir xatolarda
    agent'ni qayta yaratadi (Ollama qulab tushsa yoki model yuklanmasa).

    Holatlar:
      CLOSED   -  normal ish (xato yo'q yoki kam)
      OPEN     -  og'ir xato: agent qayta yaratiladi (cooldown davomida)
      HALF_OPEN  -  cooldown tugadi: birinchi muvaffaqiyatli chaqiruv bilan
                  yana CLOSED ga qaytadi

    Xavfsizlik: hech qachon cheksiz loop yo'q - agent doimo yaratiladi,
    faqat qanchalik tez qayta yaratilishi farq qiladi.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self):
        self.state = self.CLOSED
        self._failure_count = 0
        self._last_failure = 0.0
        self._last_success = time.time()
        self._open_since = 0.0
        self._lock = threading.Lock()
        # Konfiguratsiya
        self._failure_threshold = 3       # shuncha ketma-ket xatodan keyin OPEN
        self._cooldown_seconds = 30.0     # OPEN holatida shuncha vaqt kutish
        self._recovery_timeout = 60.0     # HALF_OPEN da shuncha vaqt ichida muvaffaqiyat kerak

    def record_success(self):
        """Muvaffaqiyatli chaqiruv - xato hisoblagichini tozalaydi."""
        with self._lock:
            self._failure_count = 0
            self._last_success = time.time()
            if self.state != self.CLOSED:
                print(f"[circuit] {self.state} -> CLOSED (muvaffaqiyat)")
                self.state = self.CLOSED

    def record_failure(self, error: str = ""):
        """Xato  --  ketma-ket xato hisobini oshiradi."""
        with self._lock:
            self._failure_count += 1
            self._last_failure = time.time()
            if self.state == self.HALF_OPEN:
                print(f"[circuit] HALF_OPEN -> OPEN (xato: {error[:80]})")
                self.state = self.OPEN
                self._open_since = time.time()
            elif self._failure_count >= self._failure_threshold and self.state == self.CLOSED:
                print(f"[circuit] CLOSED -> OPEN (ketma-ket {self._failure_count} xato: {error[:80]})")
                self.state = self.OPEN
                self._open_since = time.time()

    def should_allow(self) -> bool:
        """Chaqiruvga ruxsat berilimi? OPEN bo'lsa cooldown tugamaguncha yo'q."""
        with self._lock:
            if self.state == self.CLOSED:
                return True
            if self.state == self.HALF_OPEN:
                return True
            # OPEN  -  cooldown tekshirish
            elapsed = time.time() - self._open_since
            if elapsed >= self._cooldown_seconds:
                print(f"[circuit] OPEN -> HALF_OPEN (cooldown {elapsed:.0f}s o'tdi)")
                self.state = self.HALF_OPEN
                return True
            return False

    def force_reset(self):
        """Qo'lda reset  --  server restart yoki UI'dan."""
        with self._lock:
            self.state = self.CLOSED
            self._failure_count = 0
            self._open_since = 0.0
            print("[circuit] qo'lda reset -> CLOSED")

    def status(self) -> dict:
        """Holat ma'lumotlari  --  /api/status uchun."""
        with self._lock:
            return {
                "state": self.state,
                "failure_count": self._failure_count,
                "last_failure": self._last_failure,
                "last_success": self._last_success,
                "open_since": self._open_since if self.state == self.OPEN else None,
            }


_CIRCUIT = CircuitBreaker()


