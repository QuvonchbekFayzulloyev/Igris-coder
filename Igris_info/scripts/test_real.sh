#!/usr/bin/env bash
# ============================================================================
#  IGRIS REAL TEST — yagona command
#  ---------------------------------------------------------------------------
#  Igrisni REAL tarzda sinaydi:
#    1. Igris Brain server (FastAPI, :8765)  -> ishga tushadi
#    2. Desktop GUI (Tauri)                  -> ochiladi (browser EMAS, oyna)
#    3. Agent haqiqiy brauzerda odam kabi task bajaradi
#       (web-ai-bridge MCP + real Chrome CDP, mr.wtin profili)
#    4. Natija tekshiriladi, screenshot olinadi, hisobot ko'rsatiladi
#
#  Ishlatish:
#     bash test_real.sh                # to'liq real test
#     bash test_real.sh --no-llm       # Ollama'siz (fallback agent)
#     bash test_real.sh --no-gui       # desktop oynani ochmaydi (faqat server+task)
#     bash test_real.sh --keep         # tugatganda server/GUI ni o'chirmaydi
#     bash test_real.sh --port 8765 --model qwen3:8b
#
#  Jarayonni avtomatik tozalaydi (trap): server, vite, Tauri, bridge.
# ============================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN="$ROOT/Igris_brain"
UI="$ROOT/Igris_Interface"
SHOTS="$BRAIN/e2e_shots"
REPORTS="$BRAIN/reports"
mkdir -p "$SHOTS" "$REPORTS"

PORT="${IGRIS_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"
MODEL="${IGRIS_MODEL:-qwen3:8b}"
NO_LLM=0
NO_GUI=0
KEEP=0
GUI_EXE="$UI/src-tauri/target/debug/igris-agent-console.exe"
DEV_URL="http://localhost:1420"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-llm) NO_LLM=1 ;;
    --no-gui) NO_GUI=1 ;;
    --keep)   KEEP=1 ;;
    --port)   PORT="$2"; BASE="http://127.0.0.1:${PORT}"; shift ;;
    --model)  MODEL="$2"; shift ;;
    *) echo "noma'lum bayroq: $1"; exit 2 ;;
  esac
  shift
done

PIDS=()
LOG_FILE="$REPORTS/real_test.log"
: > "$LOG_FILE"

log()  { echo "[test] $*" | tee -a "$LOG_FILE"; }
fail() { echo "[test] ✗ $*" | tee -a "$LOG_FILE"; }
ok()   { echo "[test] ✓ $*" | tee -a "$LOG_FILE"; }

cleanup() {
  if [[ "$KEEP" == "1" ]]; then
    log "KEEP=1 — jarayonlar ishlab qoladi: ${PIDS[*]:-}"
    return
  fi
  for pid in "${PIDS[@]:-}"; do
    # Git-Bash PID'larida taskkill ishonchsiz (MSYS/Windows PID farqi) — oddiy kill
    # to'g'ri jarayonni o'chiradi; server o'lganida bola jarayonlar ham yopiladi.
    kill "$pid" 2>/dev/null || true
  done
  log "tozalandi (${#PIDS[@]} jarayon o'chirildi)"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 0) Asosiy tekshiruvlar
# ---------------------------------------------------------------------------
command -v curl >/dev/null || { fail "curl topilmadi"; exit 1; }
command -v python >/dev/null || { fail "python topilmadi"; exit 1; }

echo "==========================================================" | tee -a "$LOG_FILE"
echo "  IGRIS REAL TEST  —  $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "  model=${MODEL}  port=${PORT}  llm=$([ $NO_LLM -eq 1 ] && echo OFF || echo ON)" | tee -a "$LOG_FILE"
echo "==========================================================" | tee -a "$LOG_FILE"

# Ollama mavjudligi (real brauzer task LLM talab qiladi)
if [[ "$NO_LLM" == "0" ]]; then
  if curl -sf --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama ishlayapti (127.0.0.1:11434)"
  else
    fail "Ollama topilmadi! (http://127.0.0.1:11434)"
    fail "Iltimos:  ollama serve   (yoki modelni o'rnating: ollama pull $MODEL)"
    fail "Ollama'siz real brauzer task ishlamaydi. --no-llm bilan faqat fallback sinashi mumkin."
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 1) Igris Brain server
# ---------------------------------------------------------------------------
if curl -sf --max-time 2 "$BASE/api/status" >/dev/null 2>&1; then
  ok "server allaqachon ishlayapti: $BASE"
else
  log "server ishga tushirilmoqda: python server.py --port $PORT ..."
  cd "$BRAIN" || { fail "Igris_brain topilmadi"; exit 1; }
  LLM_FLAG=()
  [[ "$NO_LLM" == "1" ]] && LLM_FLAG=(--no-llm)
  python server.py --port "$PORT" --model "$MODEL" "${LLM_FLAG[@]}" \
    >>"$LOG_FILE" 2>&1 &
  PIDS+=("$!")
  # status ready bo'lguncha kutamiz (30s)
  READY=0
  for _ in $(seq 1 30); do
    if curl -sf --max-time 2 "$BASE/api/status" >/dev/null 2>&1; then READY=1; break; fi
    sleep 1
  done
  [[ "$READY" == "1" ]] || { fail "server 30s ichida chiqmadi — log: $LOG_FILE"; exit 1; }
  ok "server tayyor: $BASE"
fi

STATUS_JSON="$(curl -sf "$BASE/api/status" 2>/dev/null || echo '{}')"
echo "$STATUS_JSON" | python -c '
import json,sys
d = json.load(sys.stdin)
a = d.get("agent", {})
l = d.get("llm", {})
m = d.get("memory", {})
print(f"  agent: bricks={a.get(\"bricks\")} rules={a.get(\"rules\")}")
print(f"  llm:   enabled={l.get(\"enabled\")} available={l.get(\"available\")} model={l.get(\"model\")}")
print(f"  memory: enabled={m.get(\"enabled\")} error={m.get(\"error\") or \"-\"}")
' | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 2) Desktop GUI (Tauri) — browser EMAS
# ---------------------------------------------------------------------------
if [[ "$NO_GUI" == "1" ]]; then
  log "GUI o'tkazib yuborildi (--no-gui)"
else
  # Vite dev server GUI uchun zarur (Tauri devUrl = localhost:1420)
  if curl -sf --max-time 2 "$DEV_URL" >/dev/null 2>&1; then
    ok "vite dev server allaqachon: $DEV_URL"
  else
    log "vite dev server ishga tushirilmoqda (Tauri uchun)..."
    cd "$UI" || { fail "Igris_Interface topilmadi"; exit 1; }
    npm run dev >>"$LOG_FILE" 2>&1 &
    PIDS+=("$!")
    READY=0
    for _ in $(seq 1 60); do
      if curl -sf --max-time 2 "$DEV_URL" >/dev/null 2>&1; then READY=1; break; fi
      sleep 1
    done
    [[ "$READY" == "1" ]] || { fail "vite 60s ichida chiqmadi — log: $LOG_FILE"; exit 1; }
    ok "vite tayyor: $DEV_URL"
  fi

  # Prebuilt Tauri debug binary — bor bo'lsa ishlatamiz, yo'q bo'lsa npm run tauri dev
  if [[ -f "$GUI_EXE" ]]; then
    log "desktop GUI ishga tushirilmoqda: $(basename "$GUI_EXE")"
    "$GUI_EXE" >>"$LOG_FILE" 2>&1 &
    PIDS+=("$!")
    sleep 5
    if kill -0 "${PIDS[-1]}" 2>/dev/null; then
      ok "desktop GUI oynasi ochildi (pid ${PIDS[-1]})"
    else
      fail "desktop GUI tezda yopildi — log: $LOG_FILE"; exit 1
    fi
  else
    log "prebuilt binary yo'q — 'npm run tauri dev' (birinchi marta 1-5 daqiqa Rust build)..."
    cd "$UI" || exit 1
    npm run tauri dev >>"$LOG_FILE" 2>&1 &
    PIDS+=("$!")
    sleep 20
    ok "tauri dev ishga tushdi (birinchi build uzoq bo'lishi mumkin)"
  fi
fi

# ---------------------------------------------------------------------------
# 3) Real brauzer task — agent odam kabi bajaradi (web-ai-bridge MCP)
# ---------------------------------------------------------------------------
echo "----------------------------------------------------------" | tee -a "$LOG_FILE"
log "agent vazifasi yuborilmoqda (real Chrome, human-like)..."

TASK='Real browser task: use the web_ai_bridge browser tools via mcp_call like a human would.
1) mcp_call("web_ai_bridge__browser_navigate", {"url": "https://example.com"})
2) mcp_call("web_ai_bridge__browser_get_text", {}) to read the page text
3) Summarize in 2-3 sentences what the page is about.
Use ONLY browser tools, do not create files. Final answer must contain the summary.'

RUN_JSON="$(curl -sf -X POST "$BASE/api/agent/task" \
  -H 'Content-Type: application/json' \
  -d "$(python -c "import json,sys;print(json.dumps({'task':sys.argv[1]}))" "$TASK")" 2>/dev/null || echo '{}')"
RUN_ID="$(echo "$RUN_JSON" | python -c "import json,sys;print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null)"
if [[ -z "$RUN_ID" ]]; then
  fail "vazifa boshlanmadi — javob: $RUN_JSON"; exit 1
fi
ok "run boshlandi: run_id=$RUN_ID"

# Poll — max 8 daqiqa, har 25s da progress chiqadi
t0_sec=$(date +%s)
DONE=0
HITL=0
for i in $(seq 1 96); do
  STATE="$(curl -sf "$BASE/api/agent/run/$RUN_ID" 2>/dev/null || echo '{}')"
  STATUS="$(echo "$STATE" | python -c "import json,sys;print(json.load(sys.stdin).get('status',''))" 2>/dev/null)"
  case "$STATUS" in
    done|error) DONE=1; break ;;
    awaiting_human)
      if [[ "$HITL" == "0" ]]; then
        Q="$(echo "$STATE" | python -c "import json,sys;print(json.load(sys.stdin).get('question') or '')" 2>/dev/null)"
        HITL=1
        fail "agent savol so'radi (HITL) — test avtomatik javob bera olmaydi."
        fail "savol: ${Q:0:200}"
        fail "GUI orqali javob bering yoki run ni yakunlang: run_id=$RUN_ID"
        exit 1
      fi
      ;;
  esac
  if (( i % 5 == 0 )); then
    el=$(( $(date +%s) - t0_sec ))
    log "poll ${i}: holat=${STATUS:-?}  ($el s o'tdi)..."
  fi
  sleep 5
done
if [[ "$DONE" != "1" ]]; then
  fail "vaqt tugadi (8 min) — run hali yakunlanmadi (holat=${STATUS:-?})"
  exit 1
fi
elapsed=$(( $(date +%s) - t0_sec ))
log "run yakunlandi: holat=${STATUS}  (${elapsed}s)"

RESULT_JSON="$(echo "$STATE" | python -c '
import json,sys
d = json.load(sys.stdin)
r = d.get("result") or {}
print(json.dumps({"status": d.get("status"), "run_status": r.get("status"), "final": r.get("final") or "", "tool_calls": r.get("tool_calls") or [], "error": d.get("error")}))
')"

echo "$RESULT_JSON" | python -c '
import json,sys
d = json.load(sys.stdin)
print("  run status :", d["status"])
print("  agent status:", d["run_status"])
tools = [t.get("name") or t.get("tool") for t in d["tool_calls"]]
print("  tool calls :", len(tools), "->", ", ".join(str(t) for t in tools[:10]))
final = (d["final"] or "").strip()
print("  final:", final[:300])
' | tee -a "$LOG_FILE"

# MCP bridge holati — web_ai_bridge ulanganmi?
log "MCP / brauzer holati:"
curl -sf "$BASE/api/agent/mcp" 2>/dev/null | python -c '
import json,sys
try:
    d = json.load(sys.stdin)
    print("  mcp servers:", d.get("servers"))
    print("  mcp tools  :", d.get("tools"))
except Exception:
    print("  mcp: oqib bo\u2019lmadi")
' | tee -a "$LOG_FILE"

# Screenshot (real Chrome)
log "screenshot olinmoqda (real Chrome)..."
SHOT_OUT="$SHOTS/real_test_$(date +%H%M%S).png"
curl -sf "$BASE/api/webai/screenshot" -o "$SHOT_OUT" 2>/dev/null && \
  [[ -s "$SHOT_OUT" ]] && ok "screenshot: $SHOT_OUT" || fail "screenshot olib bo'lmadi"

# ---------------------------------------------------------------------------
# 4) Baholash
# ---------------------------------------------------------------------------
PASS=0
echo "$RESULT_JSON" | python -c '
import json,sys
d = json.load(sys.stdin)
ok = d["status"] == "done" and d["run_status"] == "ok"
# LLM path: model mcp_call chaqiradi va haqiqiy tool args.tool da bo\u2019ladi;
# fallback path: tool nomi to\u2019g\u2019ridan-to\u2019g\u2019ri MCP nomi bilan yoziladi.
used_browser = False
for t in d["tool_calls"]:
    n = str(t.get("name") or t.get("tool") or "")
    a = t.get("args") or {}
    inner = str(a.get("tool") or "")
    if "browser_" in n or "web_ai" in n or "browser_" in inner or "web_ai" in inner:
        used_browser = True
        break
has_final = bool((d["final"] or "").strip())
verdict = ok and used_browser and has_final
print("1" if verdict else "0")
' > "$REPORTS/.verdict" 2>/dev/null
PASS="$(cat "$REPORTS/.verdict" 2>/dev/null || echo 0)"

echo "----------------------------------------------------------" | tee -a "$LOG_FILE"
if [[ "$PASS" == "1" ]]; then
  ok "REAL TEST: PASS — agent real brauzerda taskni bajardi ✅"
  echo "[test] Hisobot: $LOG_FILE" | tee -a "$LOG_FILE"
  exit 0
else
  fail "REAL TEST: FAIL — natija talabga javob bermadi ❌"
  echo "[test] Hisobot: $LOG_FILE" | tee -a "$LOG_FILE"
  exit 1
fi
