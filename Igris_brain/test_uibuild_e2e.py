"""
E2E: real Chrome -> chat "build a working dashboard UI" -> art__ui_build_spec
-> LiveBuildHTML REAL construction mode:
  - stage-by-stage build (QURILMOQDA -> QURILISH TUGADI)
  - sidebar toggle click collapses sidebar
  - "+ Yangi loyiha" button opens the modal, x closes it
  - record button produces a .webm download
"""
import base64
import os
import re
import sys
import time

sys.path.insert(0, os.getcwd())
from mcp_bridge import McpBridge

b = McpBridge()
NAV = "web_ai_bridge__browser_navigate"
GET_TEXT = "web_ai_bridge__browser_get_text"
TYPE = "web_ai_bridge__browser_type"
WAIT = "web_ai_bridge__browser_wait_for"
CLICK = "web_ai_bridge__browser_click"
SHOT = "web_ai_bridge__browser_screenshot"
LIST_DL = "web_ai_bridge__browser_list_downloads"


def call(tool, args):
    r = b.call_tool(tool, args)
    if not r.get("ok"):
        return "ERR: " + str(r.get("error"))
    return r.get("output") or ""


def safe(t):
    try:
        return str(t).encode("ascii", "replace").decode("ascii")
    except Exception:
        return repr(t).encode("ascii", "replace").decode("ascii")


def shot_bytes():
    shot = safe(call(SHOT, {"full_page": False}))
    m = re.search(r"data='([A-Za-z0-9+/=]+)'", shot)
    if not m:
        return None
    return base64.b64decode(m.group(1))


def main():
    b.start()
    print("1) navigate...")
    print(call(NAV, {"url": "http://localhost:1420", "timeout_ms": 20000})[:100])
    time.sleep(2)
    print(call(WAIT, {"selector": "textarea", "timeout_ms": 15000})[:80])

    print("2) chat: build a working dashboard UI (uibuild)...")
    print(call(TYPE, {
        "selector": 'textarea[placeholder^="Ask the agent"]',
        "text": "Build a real working dashboard UI screen with a sidebar and a button that opens a window, save it to dashboard_live.uibuild.json",
        "submit": True,
    })[:100])

    print("3) wait for LIVE BUILD real-construction card...")
    started = False
    for i in range(24):
        time.sleep(4)
        txt = safe(call(GET_TEXT, {}))
        if "QURILMOQDA" in txt or "QURILISH TUGADI" in txt:
            started = True
            print(f"  poll {i}: construction mode started")
            break
        print(f"  poll {i}: waiting... (len {len(txt)})")
    if not started:
        print("  !! construction mode never appeared")
        b.close()
        raise SystemExit(1)

    print("4) wait for construction to finish (stage by stage)...")
    finished = False
    txt = ""
    for i in range(30):
        time.sleep(5)
        txt = safe(call(GET_TEXT, {}))
        if "QURILISH TUGADI" in txt:
            finished = True
            print(f"  poll {i}: QURILISH TUGADI")
            break
        if i % 3 == 0:
            print(f"  poll {i}: still building...")
    print("  stages seen:", "Fon" if "Fon" in txt else "-",
          "|", "Section" if "Section" in txt else "-",
          "|", "Amallar" if "Amallar" in txt else "-",
          "|", "Ochiladigan oyna" if "Ochiladigan oyna" in txt else "-")
    if not finished:
        print("  !! construction did not finish in time")
        b.close()
        raise SystemExit(1)

    print("5) sidebar toggle click -> collapse...")
    shot_before = shot_bytes()
    print(safe(call(CLICK, {"selector": '[data-ub="toggle"]', "confirm": False}))[:120])
    time.sleep(1.5)
    shot_after = shot_bytes()
    if shot_before and shot_after:
        os.makedirs("e2e_shots", exist_ok=True)
        open("e2e_shots/ub_sidebar_before.png", "wb").write(shot_before)
        open("e2e_shots/ub_sidebar_after.png", "wb").write(shot_after)
        try:
            from PIL import Image
            a = Image.open("e2e_shots/ub_sidebar_before.png").convert("RGB")
            c = Image.open("e2e_shots/ub_sidebar_after.png").convert("RGB")
            # sidebar chizig'i (chap yuqori hudud) farqini solishtiramiz
            diff = 0
            for x in range(10, min(180, min(a.width, c.width)), 3):
                for y in range(60, 200, 4):
                    p1 = a.getpixel((x, y))
                    p2 = c.getpixel((x, y))
                    if abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2]) > 30:
                        diff += 1
            print(f"  sidebar region pixel diff: {diff} (0 => no visual change)")
            print("  SIDEBAR TOGGLE:", "WORKS" if diff > 15 else "no visible change")
        except Exception as exc:
            print("  pixel compare skipped:", exc)
    else:
        print("  !! screenshots missing - toggle visual check skipped")

    print("6) modal: click '+ Yangi loyiha' -> window opens...")
    print(safe(call(CLICK, {"selector": "#btn-modal-new", "confirm": False}))[:120])
    time.sleep(1.5)
    txt_open = safe(call(GET_TEXT, {}))
    if "Yangi loyiha yaratish" in txt_open:
        print("  MODAL OPEN: OK - window content visible")
    else:
        print("  MODAL OPEN: FAIL - text not found")

    print("7) modal: click x -> window closes...")
    print(safe(call(CLICK, {"selector": '[data-ub="icon-\u2715"]', "confirm": False}))[:120])
    time.sleep(1.0)
    txt_closed = safe(call(GET_TEXT, {}))
    if "Yangi loyiha yaratish" not in txt_closed:
        print("  MODAL CLOSE: OK - window hidden again")
    else:
        print("  MODAL CLOSE: FAIL - still visible")

    print("8) record button -> WebM...")
    print(safe(call(CLICK, {"selector": 'button[title^="Qurilishni videoga"]', "confirm": False}))[:120])
    time.sleep(2)
    for i in range(12):
        time.sleep(4)
        txt = safe(call(GET_TEXT, {}))
        if "REC" not in txt and i >= 3:
            print(f"  poll {i}: REC finished")
            break
    dl = safe(call(LIST_DL, {}))
    print("  downloads:", dl[:300])
    if "webm" in dl.lower():
        print("  VIDEO RECORD: OK - webm downloaded")
    else:
        print("  VIDEO RECORD: maybe -", dl[:120])

    print("9) final screenshot...")
    shot = safe(call(SHOT, {"full_page": False}))
    m = re.search(r"data='([A-Za-z0-9+/=]+)'", shot)
    if m:
        os.makedirs("e2e_shots", exist_ok=True)
        with open(os.path.abspath("e2e_shots/uibuild_final.png"), "wb") as fh:
            fh.write(base64.b64decode(m.group(1)))
        print("  screenshot: e2e_shots/uibuild_final.png")
    else:
        print("  shot head:", shot[:80])

    print("10) page tail...")
    print(safe(call(GET_TEXT, {}))[-700:])

    b.close()
    print("DONE")


if __name__ == "__main__":
    main()
