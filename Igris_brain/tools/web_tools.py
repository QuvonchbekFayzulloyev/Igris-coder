"""
IGRIS BRAIN — Tez web vositalari
================================
Brauzer (web_ai_bridge) ishga tushirmasdan TEZ va deterministik HTTP
so'rovlar. Lokal LLM uchun juda muhim: ob-havo, fakt, rasm qidirish kabi
vazifalarni bir necha soniyada, aniq bajaradi.

Tools:
    web_fetch(url)          -> sahifa matni (text), brauzersiz
    web_search_image(query) -> Wikimedia Commons'dan rasm topib, workspace'ga
                               yuklaydi ("image saved to ..." formatida qaytaradi
                               — chat karta avtomatik ko'rsatadi)

Xavfsizlik:
  - http/https URL'lardan boshqasi rad etiladi (file://, ftp://, ...)
  - chiqish hajmi cheklangan (max_chars / max_bytes)
  - timeout har bir so'rovda qat'iy
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import Tool

from safety.safety import has_suspicious, sanitize  # noqa: E402 (N3: web chiqishini tozalash)

# Wikimedia Commons so'rovlari uchun majburiy User-Agent (API qoidasi)
_UA = "IgrisAgent/2.0 (local coding agent; contact: localhost)"

# http/https dan boshqa sxemalar rad etiladi
_SAFE_SCHEME = re.compile(r"^https?://", re.IGNORECASE)


def _http_get(url: str, timeout: float = 8.0, headers: dict | None = None,
              max_bytes: int = 3_000_000) -> bytes:
    """Xavfsiz HTTP GET — faqat http/https, hajm cheklangan."""
    if not _SAFE_SCHEME.match(url):
        raise ValueError("only http/https URLs are allowed")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept": "*/*", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"response too large (> {max_bytes} bytes)")
    return data


def _web_fetch(ws, args: dict) -> dict:
    url = str(args.get("url") or "").strip()
    max_chars = int(args.get("max_chars") or 3000)
    if not url:
        return {"ok": False, "error": "url is required"}
    if not _SAFE_SCHEME.match(url):
        return {"ok": False, "error": "only http/https URLs are allowed"}
    try:
        raw = _http_get(url, timeout=float(args.get("timeout") or 8.0))
    except Exception as exc:
        return {"ok": False, "error": f"web_fetch failed: {exc}"}
    text = raw.decode("utf-8", errors="replace")
    # HTML bo'lsa — tag'larni tozalab, ko'rinadigan matnni olamiz
    if "<" in text and ">" in text:
        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
    text = text.strip()
    # N3: chiqish-tomon tekshiruv — sahifada yashirin injection ko'rsatma bo'lsa,
    # u LLM'ga yetib bormasligi uchun maskalanadi (agentni aldash hujumiga qarshi).
    if has_suspicious(text):
        text = sanitize(text)
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    if not text:
        return {"ok": False, "error": "page returned no readable text"}
    return {"ok": True, "output": text[:max_chars], "content": text[:max_chars]}


def _wikimedia_search_images(query: str, limit: int = 5) -> list[dict]:
    """Wikimedia Commons qidiruvi — rasm URL'lari ro'yxati.

    API (bepul, kalit talab qilinmaydi):
      action=query, generator=search, gsrnamespace=6 (fayllar),
      prop=imageinfo, iiprop=url|mime|size, iiurlwidth=512 (thumb).
    """
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "512",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    raw = _http_get(url, timeout=10.0)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict] = []
    for page in pages.values():
        infos = (page.get("imageinfo") or [{}])[0]
        thumb = infos.get("thumburl") or infos.get("url")
        mime = infos.get("mime") or ""
        size = infos.get("size") or 0
        # Faqat HAQIQIY rasm fayllari (PDF/SVG-loyiha kabi narsalar emas)
        if not thumb or not mime.startswith("image/"):
            continue
        out.append({"title": page.get("title") or "", "url": thumb, "mime": mime, "size": size})
    return out


# Kichik o'zbekcha -> inglizcha lug'at — birinchi qidiruv natija bermasa,
# so'rov inglizchaga o'girilib qayta sinab ko'riladi ("yashil olma" -> "green apple").
_UZ_EN_HINTS = {
    "olma": "apple", "yashil": "green", "qizil": "red", "sariq": "yellow",
    "kok": "blue", "ko'k": "blue", "pushti": "pink", "binafsha": "purple",
    "uy": "house", "daraxt": "tree", "mushuk": "cat", "it": "dog",
    "gul": "flower", "yulduz": "star", "yurak": "heart",
    "mashina": "car", "avtomobil": "car", "raketa": "rocket", "tog": "mountain",
    "rasm": "picture", "tabiat": "nature", "quyosh": "sun", "oy": "moon",
}


def _uz_to_en(query: str) -> str:
    """Qidiruv so'zlarini inglizchaga o'giradi (bilganlarini)."""
    words = re.findall(r"[a-zA-Z']+", (query or "").lower())
    mapped = []
    for w in words:
        mapped.append(_UZ_EN_HINTS.get(w, w))
    return " ".join(mapped) if mapped else query


def _web_search_image(ws, args: dict) -> dict:
    query = str(args.get("query") or "").strip()
    output = str(args.get("output") or "").strip()
    if not query:
        return {"ok": False, "error": "query is required"}
    # Output nomi ruxsat etilgan kengaytmalar bilan — faqat rasm fayllari
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(output)) if output else ""
    if base and not re.search(r"\.(png|jpe?g|gif|webp|bmp)$", base, re.IGNORECASE):
        base += ".jpg"
    if not base:
        base = re.sub(r"[^A-Za-z0-9]+", "_", query.lower()).strip("_")[:40] or "image"
        base += ".jpg"
    try:
        hits = _wikimedia_search_images(query)
    except Exception as exc:
        return {"ok": False, "error": f"image search failed: {exc}"}
    # O'zbekcha so'rov natija bermasa — inglizcha variant bilan qayta urinamiz
    # (yashil olma -> green apple). Shunda birinchi chaqiruvda ham topiladi.
    if not hits and any(c.isalpha() for c in query):
        en_q = _uz_to_en(query)
        if en_q and en_q.lower() != query.lower():
            try:
                hits = _wikimedia_search_images(en_q)
            except Exception:
                hits = []
    if not hits:
        return {"ok": False, "error": f"no images found for '{query}'"}
    # Birinchi topilgan rasmni yuklaymiz; xato bo'lsa keyingisini sinaymiz
    last_err = "no image downloaded"
    for hit in hits:
        try:
            raw = _http_get(hit["url"], timeout=12.0)
        except Exception as exc:
            last_err = f"download failed: {exc}"
            continue
        if len(raw) < 100:
            last_err = "downloaded file too small (likely an error page)"
            continue
        # Kengaytma: mime yoki URL'ga qarab
        ext = base.rsplit(".", 1)[-1].lower()
        mime = hit.get("mime") or ""
        if ext not in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
            ext = {"image/png": "png", "image/gif": "gif", "image/webp": "webp",
                   "image/bmp": "bmp"}.get(mime, "jpg")
            base = base.rsplit(".", 1)[0] + "." + ext
        try:
            abs_path = ws.resolve(base)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        try:
            with open(abs_path, "wb") as fh:
                fh.write(raw)
        except OSError as exc:
            return {"ok": False, "error": f"cannot save image: {exc}"}
        return {
            "ok": True,
            "output": f"image saved to {abs_path}",
            "content": f"image saved to {abs_path}",
            "source": hit.get("url"),
        }
    return {"ok": False, "error": last_err}


WEB_FETCH = Tool(
    name="web_fetch",
    description=(
        "Fetch a web page's readable TEXT over HTTP directly (no browser). "
        "Fast and reliable for factual lookups: weather (wttr.in/<city>), "
        "API endpoints, public pages. Returns plain text. Use for quick "
        "information instead of a browser when possible."
    ),
    parameters=[
        {"name": "url", "type": "string", "description": "http/https URL to fetch"},
        {"name": "max_chars", "type": "integer", "description": "Max characters to return (default 3000)", "default": 3000},
        {"name": "timeout", "type": "integer", "description": "Timeout in seconds (default 8)", "default": 8},
    ],
    required=["url"],
    fn=_web_fetch,
)

WEB_SEARCH_IMAGE = Tool(
    name="web_search_image",
    description=(
        "Search the web (Wikimedia Commons) for an image matching the query and "
        "download it into the workspace. Returns the saved file path. Use when "
        "the user asks to find/find a picture/photo of something (e.g. 'green "
        "apple image')."
    ),
    parameters=[
        {"name": "query", "type": "string", "description": "Image search query, e.g. 'green apple'"},
        {"name": "output", "type": "string", "description": "Output filename (e.g. 'green_apple.jpg'). Optional.", "default": ""},
    ],
    required=["query"],
    fn=_web_search_image,
)
