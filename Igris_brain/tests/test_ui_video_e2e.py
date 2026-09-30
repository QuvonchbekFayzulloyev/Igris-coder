"""
E2E: real Chrome -> chat -> "draw a dashboard UI" -> LIVE BUILD element-by-element
reveal -> 🎬 record -> WebM download. Web-ai-bridge MCP orqali.
"""
import base64
import os
import re
import sys
import time

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))
from tools.mcp_bridge import McpBridge

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
        return f"ERR: {r.get('error')}"
    return r.get("output") or ""


def safe(t):
    try:
        return str(t).encode("ascii", "replace").decode("ascii")
    except Exception:
        return repr(t).encode("ascii", "replace").decode("ascii")


def main():
    b.start()
    print("1) navigate...")
    print(call(NAV, {"url": "http://localhost:1420", "timeout_ms": 20000})[:120])
    time.sleep(2)
    print(call(WAIT, {"selector": "textarea", "timeout_ms": 15000})[:80])

    print("2) chat task: draw dashboard UI...")
    print(call(TYPE, {
        "selector": 'textarea[placeholder^="Ask the agent"]',
        "text": "Draw a dark dashboard UI design with gradient texture, save it to ui_dashboard.svg",
        "submit": True,
    })[:120])

    print("3) wait for LIVE BUILD card with 25/25 elements...")
    revealed_ok = False
    for i in range(20):
        time.sleep(5)
        txt = safe(call(GET_TEXT, {}))
        if "25/25 elements" in txt or ("BUILD COMPLETE" in txt and "ui_dashboard.svg" in txt):
            revealed_ok = True
            print(f"  poll {i}: element-by-element reveal OK")
            break
        print(f"  poll {i}: waiting... (len {len(txt)})")

    print("4) click RECORD button...")
    time.sleep(2)
    print(safe(call(CLICK, {"selector": 'button[title^="Animatsiyani videoga"]', "confirm": False}))[:160])

    print("5) wait for record to finish (build replay ~20s)...")
    for i in range(10):
        time.sleep(4)
        txt = safe(call(GET_TEXT, {}))
        # REC indikator yo'qolgan bo'lsa — yozuv tugagan
        if "REC" not in txt and i >= 3:
            print(f"  poll {i}: REC indicator gone (recording finished)")
            break
        print(f"  poll {i}: ...")

    print("6) check downloads...")
    time.sleep(2)
    dl = safe(call(LIST_DL, {}))
    print("downloads:", dl[:400])

    print("7) screenshot...")
    shot = safe(call(SHOT, {"full_page": False}))
    os.makedirs("e2e_shots", exist_ok=True)
    out = os.path.abspath("e2e_shots/ui_dashboard_livebuild.png")
    m = re.search(r"data='([A-Za-z0-9+/=]+)'", shot)
    if m:
        with open(out, "wb") as fh:
            fh.write(base64.b64decode(m.group(1)))
        print("screenshot saved:", out)
    else:
        print("shot head:", shot[:80])

    print("8) final page text (tail)...")
    print(safe(call(GET_TEXT, {}))[-900:].encode("ascii", "replace").decode("ascii"))

    b.close()
    print("DONE")


if __name__ == "__main__":
    main()
