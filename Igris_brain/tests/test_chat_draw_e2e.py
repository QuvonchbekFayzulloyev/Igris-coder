"""
E2E: real Chrome -> localhost:1420 chat -> "Draw a blue apple" -> agent tool card + drawing card.
Web-ai-bridge MCP orqali brauzerni haydaydi.
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
SHOT = "web_ai_bridge__browser_screenshot"


def call(tool, args):
    r = b.call_tool(tool, args)
    if not r.get("ok"):
        return f"ERR: {r.get('error')}"
    return r.get("output") or ""


def safe(t):
    try:
        return str(t)
    except Exception:
        return repr(t).encode("ascii", "replace").decode("ascii")


def main():
    b.start()
    print("1) navigate to app...")
    print(call(NAV, {"url": "http://localhost:1420", "timeout_ms": 20000})[:200])

    print("2) wait for chat input...")
    time.sleep(3)
    print(call(WAIT, {"selector": "textarea", "timeout_ms": 15000})[:150])

    print("3) type the task + Enter...")
    print(call(TYPE, {
        "selector": 'textarea[placeholder^="Ask the agent"]',
        "text": "Draw a blue apple and save it to blue_apple.png",
        "submit": True,
    })[:200])

    print("4) poll for the tool call card / agent response (up to ~200s)...")
    found = False
    for i in range(25):
        time.sleep(8)
        txt = safe(call(GET_TEXT, {}))
        low = txt.lower()
        # Tool-call kartasi yoki drawing kartasi paydo bo'ldimi?
        if "art__draw_object_png" in low or "live build" in low or "blue_apple.png" in low:
            print(f"poll {i}: evidence found (len {len(txt)})")
            found = True
            time.sleep(6)  # animatsiya tugashini kutamiz
            break
        print(f"poll {i}: waiting... (len {len(txt)})")

    print("5) screenshot...")
    shot = safe(call(SHOT, {"full_page": False}))
    os.makedirs("e2e_shots", exist_ok=True)
    out = os.path.abspath("e2e_shots/chat_draw_blue_apple.png")
    m = re.search(r"data='([A-Za-z0-9+/=]+)'", shot)
    if m:
        with open(out, "wb") as fh:
            fh.write(base64.b64decode(m.group(1)))
        print("screenshot saved:", out)
    else:
        print("screenshot raw head:", shot[:120])

    print("6) final page text (relevant tail)...")
    txt = safe(call(GET_TEXT, {}))
    print(txt[-1400:].encode("ascii", "replace").decode("ascii"))

    b.close()
    print("DONE")


if __name__ == "__main__":
    main()
