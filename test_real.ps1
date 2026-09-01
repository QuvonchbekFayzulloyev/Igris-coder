# ============================================================================
#  IGRIS REAL TEST — yagona command (PowerShell)
#  ---------------------------------------------------------------------------
#  Igrisni REAL tarzda sinaydi:
#    1. Igris Brain server (FastAPI, :8765)  -> ishga tushadi
#    2. Desktop GUI (Tauri)                  -> ochiladi (browser EMAS, oyna)
#    3. Agent haqiqiy brauzerda odam kabi task bajaradi
#       (web-ai-bridge MCP + real Chrome CDP, mr.wtin profili)
#    4. Natija tekshiriladi, screenshot olinadi, hisobot ko'rsatiladi
#
#  Ishlatish (PowerShell 5.1+, Windows 10/11):
#     powershell -ExecutionPolicy Bypass -File test_real.ps1
#     powershell -ExecutionPolicy Bypass -File test_real.ps1 -NoLlm
#     powershell -ExecutionPolicy Bypass -File test_real.ps1 -NoGui
#     powershell -ExecutionPolicy Bypass -File test_real.ps1 -Keep
#     powershell -ExecutionPolicy Bypass -File test_real.ps1 -Port 8765 -Model qwen3:8b
#
#  Eskicha --bayroq uslubi ham ishlaydi:
#     powershell -ExecutionPolicy Bypass -File test_real.ps1 --no-llm --no-gui --keep
#
#  Jarayonni avtomatik tozalaydi (finally): server, vite, Tauri, bridge.
# ============================================================================

param(
  [switch]$NoLlm,          # Ollama'siz (fallback agent)
  [switch]$NoGui,          # desktop oynani ochmaydi (faqat server+task)
  [switch]$Keep,           # tugatganda server/GUI ni o'chirmaydi
  [int]$Port   = 0,        # --port 8765
  [string]$Model = ""      # --model qwen3:8b
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8

# --- 0) Asosiy sozlamalar ---------------------------------------------------
$ROOT    = $PSScriptRoot
$BRAIN   = Join-Path $ROOT 'Igris_brain'
$UI      = Join-Path $ROOT 'Igris_Interface'
$SHOTS   = Join-Path $BRAIN 'e2e_shots'
$REPORTS = Join-Path $BRAIN 'reports'
New-Item -ItemType Directory -Force -Path $SHOTS, $REPORTS | Out-Null

if ($Port -eq 0) {
  $Port = 8765
  if ($env:IGRIS_PORT) { $Port = [int]$env:IGRIS_PORT }
}
if (-not $Model) {
  $Model = 'qwen3:8b'
  if ($env:IGRIS_MODEL) { $Model = $env:IGRIS_MODEL }
}

$BASE    = "http://127.0.0.1:${Port}"
$GUI_EXE = Join-Path $UI 'src-tauri/target/debug/igris-agent-console.exe'
$DEV_URL = 'http://localhost:1420'

# Eskicha bash uslubidagi --bayroq argumentlarini ham qabul qilish
for ($i = 0; $i -lt $args.Count; $i++) {
  switch ($args[$i]) {
    '--no-llm' { $NoLlm = $true }
    '--no-gui' { $NoGui = $true }
    '--keep'   { $Keep = $true }
    '--port'   { if ($i + 1 -lt $args.Count) { $Port = [int]$args[++$i]; $BASE = "http://127.0.0.1:${Port}" } }
    '--model'  { if ($i + 1 -lt $args.Count) { $Model = $args[++$i] } }
    default    { Write-Host "noma'lum bayroq: $($args[$i])" -ForegroundColor Red; exit 2 }
  }
}

$PIDS     = New-Object System.Collections.ArrayList
$LOG_FILE = Join-Path $REPORTS 'real_test.log'
if (Test-Path $LOG_FILE) { Remove-Item $LOG_FILE -Force }
# Har bir jarayon o'z log fayliga yozadi (Start-Process redirection uchun alohida kerak)
$SVR_LOG = Join-Path $REPORTS 'real_server.log'
$VITE_LOG = Join-Path $REPORTS 'real_vite.log'
$TAURI_LOG = Join-Path $REPORTS 'real_tauri.log'

function log  { param([string]$m) $line = "[test] $m"; Write-Host $line; Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8 }
function fail { param([string]$m) $line = "[test] ✗ $m"; Write-Host $line -ForegroundColor Red; Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8 }
function ok   { param([string]$m) $line = "[test] ✓ $m"; Write-Host $line -ForegroundColor Green; Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8 }

# URL tekshiruvi (curl.exe — Windows 10/11 da standart mavjud)
function Test-Uri {
  param([string]$Url, [int]$TimeoutSec = 2)
  & curl.exe -sf --max-time $TimeoutSec $Url *> $null
  return ($LASTEXITCODE -eq 0)
}

# JSON GET (xato bo'lsa $null qaytaradi)
function Get-Json {
  param([string]$Url)
  try { return Invoke-RestMethod -Uri $Url -TimeoutSec 15 -ErrorAction Stop } catch { return $null }
}

function Cleanup {
  if ($Keep) {
    log "KEEP=1 — jarayonlar ishlab qoladi: $($PIDS.Id -join ', ')"
    return
  }
  foreach ($p in $PIDS) {
    # Bola jarayonlar (node, cargo, uvicorn) ham o'chishi uchun daraxtni o'chiramiz
    if (Get-Command taskkill.exe -ErrorAction SilentlyContinue) {
      & taskkill.exe /PID $p.Id /T /F *> $null
    } else {
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
  }
  log "tozalandi ($($PIDS.Count) jarayon o'chirildi)"
}

# Ctrl+C / to'satdan to'xtatishda ham tozalash ishlashi uchun xavfsizlik tarmog'i
# (idempotent — finally bilan birga ikki marta ishlasa ham zarar yo'q)
trap { Cleanup; break }

# Asosiy tekshiruvlar
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { fail "curl topilmadi"; exit 1 }
$PYTHON = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PYTHON) { fail "python topilmadi"; exit 1 }

$BANNER = "=========================================================="
log $BANNER
log "  IGRIS REAL TEST  —  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$llmState = if ($NoLlm) { 'OFF' } else { 'ON' }
log "  model=${Model}  port=${Port}  llm=${llmState}"
log $BANNER

# Ollama mavjudligi (real brauzer task LLM talab qiladi)
if (-not $NoLlm) {
  if (Test-Uri 'http://127.0.0.1:11434/api/tags' 3) {
    ok 'Ollama ishlayapti (127.0.0.1:11434)'
  } else {
    fail 'Ollama topilmadi! (http://127.0.0.1:11434)'
    fail ("Iltimos:  ollama serve   (yoki modelni o'rnating: ollama pull " + $Model + ")")
    fail "Ollama'siz real brauzer task ishlamaydi. -NoLlm bilan faqat fallback sinashi mumkin."
    exit 1
  }
}

try {
# ---------------------------------------------------------------------------
# 1) Igris Brain server
# ---------------------------------------------------------------------------
if (Test-Uri "$BASE/api/status") {
  ok "server allaqachon ishlayapti: $BASE"
} else {
  log "server ishga tushirilmoqda: python server.py --port $Port ..."
  if (-not (Test-Path $BRAIN)) { fail 'Igris_brain topilmadi'; exit 1 }
  $svrArgs = @('server.py', '--port', "$Port", '--model', $Model)
  if ($NoLlm) { $svrArgs += '--no-llm' }
  $proc = Start-Process -FilePath $PYTHON -ArgumentList $svrArgs `
          -WorkingDirectory $BRAIN `
          -RedirectStandardOutput $SVR_LOG -RedirectStandardError "$SVR_LOG.err" `
          -WindowStyle Hidden -PassThru
  $null = $PIDS.Add($proc)
  # status ready bo'lguncha kutamiz (30s)
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    if (Test-Uri "$BASE/api/status") { $ready = $true; break }
    Start-Sleep -Seconds 1
  }
  if (-not $ready) { fail "server 30s ichida chiqmadi — log: $SVR_LOG"; exit 1 }
  ok "server tayyor: $BASE"
}

$s = Get-Json "$BASE/api/status"
if ($s) {
  log "  agent: bricks=$($s.agent.bricks) rules=$($s.agent.rules)"
  log "  llm:   enabled=$($s.llm.enabled) available=$($s.llm.available) model=$($s.llm.model)"
  log "  memory: enabled=$($s.memory.enabled) error=$($s.memory.error)"
}

# ---------------------------------------------------------------------------
# 2) Desktop GUI (Tauri) — browser EMAS
# ---------------------------------------------------------------------------
if ($NoGui) {    log 'GUI o''tkazib yuborildi (--no-gui)'
} else {
  # Vite dev server GUI uchun zarur (Tauri devUrl = localhost:1420)
  if (Test-Uri $DEV_URL) {
    ok "vite dev server allaqachon: $DEV_URL"
  } else {
    log 'vite dev server ishga tushirilmoqda (Tauri uchun)...'
    if (-not (Test-Path $UI)) { fail 'Igris_Interface topilmadi'; exit 1 }
    $proc = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') `
            -WorkingDirectory $UI `
            -RedirectStandardOutput $VITE_LOG -RedirectStandardError "$VITE_LOG.err" `
            -WindowStyle Hidden -PassThru
    $null = $PIDS.Add($proc)
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
      if (Test-Uri $DEV_URL) { $ready = $true; break }
      Start-Sleep -Seconds 1
    }
    if (-not $ready) { fail "vite 60s ichida chiqmadi — log: $VITE_LOG"; exit 1 }
    ok "vite tayyor: $DEV_URL"
  }

  # Prebuilt Tauri debug binary — bor bo'lsa ishlatamiz, yo'q bo'lsa npm run tauri dev
  if (Test-Path $GUI_EXE) {
    log "desktop GUI ishga tushirilmoqda: $(Split-Path $GUI_EXE -Leaf)"
    $proc = Start-Process -FilePath $GUI_EXE -WorkingDirectory (Split-Path $GUI_EXE) -PassThru
    $null = $PIDS.Add($proc)
    Start-Sleep -Seconds 5
    if (-not $proc.HasExited) {
      ok "desktop GUI oynasi ochildi (pid $($proc.Id))"
    } else {
      fail "desktop GUI tezda yopildi — log: $LOG_FILE"; exit 1
    }
  } else {
    log "prebuilt binary yo'q — 'npm run tauri dev' (birinchi marta 1-5 daqiqa Rust build)..."
    $proc = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'tauri', 'dev') `
            -WorkingDirectory $UI `
            -RedirectStandardOutput $TAURI_LOG -RedirectStandardError "$TAURI_LOG.err" `
            -WindowStyle Hidden -PassThru
    $null = $PIDS.Add($proc)
    Start-Sleep -Seconds 20
    ok 'tauri dev ishga tushdi (birinchi build uzoq bo''lishi mumkin)'
  }
}

# ---------------------------------------------------------------------------
# 3) Real brauzer task — agent odam kabi bajaradi (web-ai-bridge MCP)
# ---------------------------------------------------------------------------
log $BANNER
log 'agent vazifasi yuborilmoqda (real Chrome, human-like)...'

$TASK = @'
Real browser task: use the web_ai_bridge browser tools via mcp_call like a human would.
1) mcp_call("web_ai_bridge__browser_navigate", {"url": "https://example.com"})
2) mcp_call("web_ai_bridge__browser_get_text", {}) to read the page text
3) Summarize in 2-3 sentences what the page is about.
Use ONLY browser tools, do not create files. Final answer must contain the summary.
'@

$body = @{ task = $TASK } | ConvertTo-Json
$runResp = $null
try {
  $runResp = Invoke-RestMethod -Uri "$BASE/api/agent/task" -Method Post `
              -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 60
} catch {
  fail "vazifa boshlanmadi — javob: $($_.Exception.Message)"; exit 1
}
$runId = if ($runResp) { "$($runResp.run_id)" } else { '' }
if (-not $runId) {
  fail "vazifa boshlanmadi — javob: $($runResp | ConvertTo-Json -Compress)"; exit 1
}
ok "run boshlandi: run_id=$runId"

# Poll — max 8 daqiqa, har 25s da progress chiqadi
$t0     = Get-Date
$done   = $false
$hitl   = $false
$state  = $null
$status = ''
for ($i = 1; $i -le 96; $i++) {
  $state = Get-Json "$BASE/api/agent/run/$runId"
  $status = if ($state) { "$($state.status)" } else { '' }
  if ($status -eq 'done' -or $status -eq 'error') { $done = $true; break }
  if ($status -eq 'awaiting_human') {
    if (-not $hitl) {
      $q = if ($state -and $state.question) { "$($state.question)" } else { '' }
      $hitl = $true
      fail 'agent savol so''radi (HITL) — test avtomatik javob bera olmaydi.'
      fail "savol: $($q.Substring(0, [Math]::Min(200, $q.Length)))"
      fail "GUI orqali javob bering yoki run ni yakunlang: run_id=$runId"
      exit 1
    }
  }
  if ($i % 5 -eq 0) {
    $el = [int]((Get-Date) - $t0).TotalSeconds
    log "poll ${i}: holat=${status}  ($el s o'tdi)..."
  }
  Start-Sleep -Seconds 5
}
if (-not $done) {
  fail "vaqt tugadi (8 min) — run hali yakunlanmadi (holat=$status)"
  exit 1
}
$elapsed = [int]((Get-Date) - $t0).TotalSeconds
log "run yakunlandi: holat=${status}  (${elapsed}s)"

$runStatus = if ($state -and $state.result) { "$($state.result.status)" } else { '' }
$final     = if ($state -and $state.result) { "$($state.result.final)" } else { '' }
$toolCalls = @(if ($state -and $state.result -and $state.result.tool_calls) { @($state.result.tool_calls) } else { @() })

log "  run status : $status"
log "  agent status: $runStatus"
$toolNames = @($toolCalls | ForEach-Object { "$($_.name)$($_.tool)" } | Select-Object -First 10)
log "  tool calls : $($toolCalls.Count) -> $($toolNames -join ', ')"
if ($final.Length -gt 300) { $finalShort = $final.Substring(0, 300) } else { $finalShort = $final }
log "  final: $finalShort"

# MCP bridge holati — web_ai_bridge ulanganmi?
log 'MCP / brauzer holati:'
$mcp = Get-Json "$BASE/api/agent/mcp"
if ($mcp) {
  log ("  mcp servers: " + ($mcp.servers | ConvertTo-Json -Compress -Depth 4))
  log ("  mcp tools  : " + ($mcp.tools | ConvertTo-Json -Compress -Depth 4))
} else {
  log "  mcp: oqib bo'lmadi"
}

# Screenshot (real Chrome)
log 'screenshot olinmoqda (real Chrome)...'
$SHOT_OUT = Join-Path $SHOTS ("real_test_" + (Get-Date -Format 'HHmmss') + ".png")
& curl.exe -sf "$BASE/api/webai/screenshot" -o $SHOT_OUT *> $null
if ($LASTEXITCODE -eq 0 -and (Test-Path $SHOT_OUT) -and (Get-Item $SHOT_OUT).Length -gt 0) {
  ok "screenshot: $SHOT_OUT"
} else {
  fail "screenshot olib bo'lmadi"
}

# ---------------------------------------------------------------------------
# 4) Baholash
# ---------------------------------------------------------------------------
$usedBrowser = $false
foreach ($t in $toolCalls) {
  $n = "$($t.name)$($t.tool)"
  $inner = if ($t.args) { "$($t.args.tool)" } else { '' }
  if ($n -match 'browser_|web_ai' -or $inner -match 'browser_|web_ai') { $usedBrowser = $true; break }
}
$hasFinal = ($final.Trim().Length -gt 0)
$pass = ($status -eq 'done' -and $runStatus -eq 'ok' -and $usedBrowser -and $hasFinal)

log $BANNER
if ($pass) {
  ok 'REAL TEST: PASS — agent real brauzerda taskni bajardi ✅'
  log "Hisobot: $LOG_FILE"
  exit 0
} else {
  fail 'REAL TEST: FAIL — natija talabga javob bermadi ❌'
  log "Hisobot: $LOG_FILE"
  exit 1
}
} finally {
  Cleanup
}
