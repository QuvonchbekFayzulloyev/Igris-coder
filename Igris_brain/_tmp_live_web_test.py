"""JONLI test: 'chatgptdan so'ra' so'rovida model ask_web_ai'ni tanlaydimi.

Real LLM (qwen3:8b) + yangi (qayta ishga tushirilgan) web-ai-bridge server.
Tool EXECUTION mock qilinadi (real Chrome/ChatGPT ochilmaydi) — biz faqat
MODELNING TANLOVINI tekshiramiz. Bridge schema'laridagi server-hint ham
tekshiriladi (dublikat yo'qligi).
"""
import sys, os, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from igris_agent import IgrisAgent

agent = IgrisAgent(use_llm=True, llm_model="qwen3:8b", memory_enabled=False)

# ---- 1) Schema tekshiruvi: server hint'i bridge'dan to'g'ri kelmoqdami ----
mcp = agent._mcp()
assert mcp is not None, "MCP (web-ai-bridge) ulanmadi!"
tools = agent._web_tools("delegate")
by_name = {t["function"]["name"]: t["function"]["description"] for t in tools}
ask = by_name.get("web_ai_bridge__ask_web_ai", "")
print("== SCHEMA TEKSHIRUVI ==")
print("ask_web_ai mavjud:", bool(ask))
print("WHEN TO USE bor (server manba):", "WHEN TO USE" in ask)
print("WHEN TO USE soni (1 = dublikat YO'Q):", ask.count("WHEN TO USE"))
print("DELEGATES ko'rsatmasi bor:", "DELEGATES" in ask)
print("login izohi bor:", "log in" in ask or "logged in" in ask)
print("description uzunligi:", len(ask))

# ---- 2) Model tanlovi: tool execution'ni yozib olamiz ----
calls: list[str] = []

def fake_exec(name, args):
    calls.append(name)
    return {"ok": True, "output": f"[MOCK] {name} bajarildi (haqiqiy brauzer ochilmadi)"}

agent._execute_chat_tool = fake_exec
agent._image_from_art_call = lambda r: None

print("\n== JONLI MODEL TANLOVI ==")
# Model BILMAYDIGAN savol — jonli (real-time) ma'lumot kerak, shuning uchun
# delegatsiya (ask_web_ai) majburiy bo'ladi. Birinchi sinov 'poytaxt qayerda'
# edi — model o'z bilimidan javob berdi, bu aqlli, lekin test uchun emas.
# 'ob-havo' so'zi agent'ning weather quick-path'ini chaqiradi (wttr.in,
# LLMga yetib bormaydi) — shuning uchun boshqa real-time mavzu: valyuta kursi.
QUESTION = (
    "chatgptdan so'ra: bugun USD/O'zbekiston so'mi kursi qanday o'zgardi? "
    "(bugungi real kurs ma'lumoti)"
)
print(f"So'rov: {QUESTION}")
t0 = time.time()
done = None
for ev in agent.chat_stream(QUESTION, use_memory=False):
    et = ev.get("type")
    if et == "stage":
        print(f"  [stage] {ev.get('stage')}: {ev.get('detail')}")
    elif et == "done":
        done = ev
    elif et in ("token", "thinking"):
        pass  # shovqin qilmaymiz
print(f"  (davomiylik {time.time() - t0:.1f}s)")

# ---- 3) Natija ----
tool_calls = (done or {}).get("tool_calls") or []
names = []
for tc in tool_calls:
    if isinstance(tc, dict):
        names.append(tc.get("tool") or tc.get("name") or str(tc)[:60])
    else:
        names.append(str(tc)[:60])

print("\n== NATIJA ==")
print("Model chaqirgan tool'lar:", names or calls or "(hech qanday tool chaqirilmadi)")
print("Bajarilgan (mock) tool'lar:", calls)
engine = (done or {}).get("engine")
print("engine:", engine)
content = (done or {}).get("content", "")
print("javob (boshi):", str(content)[:220].replace("\n", " "))

verdict = "PASS" if "web_ai_bridge__ask_web_ai" in (names + calls) else "FAIL"
print("\nVERDICT:", verdict)

# ---- 4) web_strategy log'da qayd borligi ----
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "web_strategy.jsonl")
if os.path.isfile(log_path):
    with open(log_path, encoding="utf-8") as fh:
        lines = [l for l in fh if l.strip()]
    if lines:
        last = json.loads(lines[-1])
        print("web_strategy.log so'nggi yozuv:", last.get("verdict"), "|", last.get("strategy"))

sys.exit(0 if verdict == "PASS" else 1)
