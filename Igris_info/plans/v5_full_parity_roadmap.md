# IGRIS v5 — Full Parity Roadmap
# Real Coding Assistants Bilan tenglashish rejasi

**Sana:** 2026-09-18
**Maqsad:** OpenCode, Claude Code, Codex darajasiga yetish
**Umumiy vaqt:** ~16-20 hafta (4-5 oy)

---

## JARAYON XARITASI

```
v5.0  Foundation        (1-3 hafta)  — LLM + Edit + Read
v5.1  Language Intel    (3-6 hafta)  — LSP + AST + Git
v5.2  Dev Workflow      (6-10 hafta) — Test + Package + Context
v5.3  Advanced          (10-16 hafta) — Browser + Review + Multi-file
v5.4  Polish            (16-20 hafta) — Performance + UX + Docs
```

---

# v5.0 — FOUNDATION (1-3 hafta)

## 1.1 Cloud LLM Support
**Fayl:** `llm/cloud_client.py` (yangi)

### Detallar:
- OpenAI API (GPT-4, GPT-4o, GPT-4o-mini)
- Anthropic API (Claude 3.5 Sonnet, Claude 3 Opus)
- Google Gemini API (Gemini 1.5 Pro)
- Birlashtirilgan interfeys: `BaseLLM` → `OllamaClient`, `OpenAIClient`, `AnthropicClient`, `GeminiClient`

### Implementatsiya:
```python
# llm/base.py
class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] = None) -> dict:
        """Unified chat interface."""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass
    
    @abstractmethod
    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        pass

# llm/cloud_client.py
class OpenAIClient(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def chat(self, messages, tools=None):
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)

class AnthropicClient(BaseLLM):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
    
    def chat(self, messages, tools=None):
        # Anthropic formatiga moslashtirish
        pass
```

### API Key Management:
```python
# config/api_keys.py
class APIKeyManager:
    """Environment variables yoki config fayldan API key'larni oladi."""
    def get_openai_key(self) -> Optional[str]:
        return os.environ.get("OPENAI_API_KEY") or self._config.get("openai_key")
    
    def get_anthropic_key(self) -> Optional[str]:
        return os.environ.get("ANTHROPIC_API_KEY") or self._config.get("anthropic_key")
```

### Model Tanlash:
```python
# llm/model_selector.py
class ModelSelector:
    """Task turiga qarab model tanlaydi."""
    SELECTION_RULES = {
        "code_generation": {"preferred": "gpt-4o", "fallback": "claude-3-5-sonnet"},
        "code_review": {"preferred": "claude-3-5-sonnet", "fallback": "gpt-4o"},
        "quick问答": {"preferred": "gpt-4o-mini", "fallback": "qwen3:8b"},
        "complex_reasoning": {"preferred": "gpt-4o", "fallback": "claude-3-opus"},
    }
    
    def select(self, task_type: str, available_models: list[str]) -> str:
        pass
```

### Cost Tracking:
```python
# llm/cost_tracker.py
class CostTracker:
    """Har bir so'rov uchun xarajatlarni hisoblaydi."""
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},  # per 1M tokens
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    }
    
    def log_request(self, model: str, input_tokens: int, output_tokens: int):
        cost = self._calculate(model, input_tokens, output_tokens)
        self._total_cost += cost
        self._log.append({"model": model, "cost": cost, "timestamp": time.time()})
```

### Streaming:
```python
# llm/streaming.py
class StreamingHandler:
    """SSE streaming uchun unified handler."""
    async def stream_response(self, llm: BaseLLM, messages: list[dict]) -> AsyncIterator[str]:
        async for chunk in llm.stream_chat(messages):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "data: [DONE]\n\n"
```

### Testlar:
- `tests/test_cloud_llm.py` — OpenAI, Anthropic, Gemini client unit testlari
- Mock API responses bilan
- Cost tracking testlari
- Streaming testlari
- Fallback testlari (cloud → Ollama)

---

## 1.2 File Editing Tool — Search & Replace
**Fayl:** `tools/fs_tools.py` (yangilanadi)

### Hozirgi muammo:
`apply_patch` faqat:
- Satrni o'chirish (exact match)
- Oxiriga qo'shish
- Positional insert yo'q
- In-place replacement yo'q
- Multi-region edit yo'q

### Yangi `edit_file` tool:
```python
@tool(
    name="edit_file",
    description="Fayl ichida search & replace. Bir nechta regionni bir vaqtda tahrirlash mumkin.",
    params={
        "path": "Fayl yo'li",
        "edits": [
            {
                "old_text": "Qidiriladigan matn (exact match)",
                "new_text": "Yangi matn",
                "line": "Optional: boshlang'ich qator raqami (validation uchun)"
            }
        ],
        "create_if_missing": "Fayl yo'q bo'lsa yaratish (default: false)"
    }
)
def edit_file(ws, args):
    path = validate_path(ws, args["path"])
    edits = args["edits"]
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    applied = []
    
    for edit in edits:
        old_text = edit["old_text"]
        new_text = edit["new_text"]
        
        # Validation: old_text mavjudligini tekshirish
        if old_text not in content:
            return {"ok": False, "error": f"Text not found: {old_text[:50]}..."}
        
        # Line number validation (agar berilgan bo'lsa)
        if "line" in edit:
            line_num = edit["line"]
            lines_before = content[:content.index(old_text)].count("\n") + 1
            if abs(lines_before - line_num) > 3:
                return {"ok": False, "error": f"Line mismatch: expected ~{line_num}, found {lines_before}"}
        
        # Replace
        content = content.replace(old_text, new_text, 1)  # Birinchi mavjud bo'lganini almashtirish
        applied.append({"old": old_text[:50], "new": new_text[:50]})
    
    # Backup
    backup_path = path + ".bak"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(original)
    
    # Write
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return {"ok": True, "edits_applied": len(applied), "details": applied}
```

### Qo'shimcha — Multi-edit Support:
```python
# tools/edit_utils.py
class EditRegion:
    """Bitta tahrir regioni."""
    def __init__(self, old_text: str, new_text: str, context_lines: int = 3):
        self.old_text = old_text
        self.new_text = new_text
        self.context_lines = context_lines
    
    def validate(self, content: str) -> tuple[bool, str]:
        """Region to'g'ri ekanligini tekshirish."""
        if self.old_text not in content:
            return False, "Text not found"
        
        # Context validation — old_text atrofidagi satrlar ham to'g'ri
        idx = content.index(self.old_text)
        before = content[:idx].split("\n")[-self.context_lines:]
        after = content[idx + len(self.old_text):].split("\n")[:self.context_lines]
        
        return True, "OK"

def batch_edit(ws, path: str, edits: list[EditRegion]) -> dict:
    """Bir nechta regionni bir vaqtda tahrirlash."""
    pass
```

### `read_file` yangilanishi — Line Ranges:
```python
@tool(
    name="read_file",
    description="Faylni o'qish. Offset/limit bilan qisman o'qish mumkin.",
    params={
        "path": "Fayl yo'li",
        "offset": "Boshlang'ich qator (1-indexed, default: 1)",
        "limit": "Maksimal qatorlar soni (default: 2000)",
        "encoding": "Kodlash (default: utf-8)"
    }
)
def read_file(ws, args):
    path = validate_path(ws, args["path"])
    offset = args.get("offset", 1)
    limit = args.get("limit", 2000)
    
    with open(path, "r", encoding=args.get("encoding", "utf-8")) as f:
        lines = f.readlines()
    
    selected = lines[offset-1 : offset-1+limit]
    
    return {
        "ok": True,
        "content": "".join(selected),
        "total_lines": len(lines),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(lines)
    }
```

### Testlar:
- `tests/test_edit_file.py` — Search & replace testlari
- Multi-edit testlari
- Validation testlari (line mismatch, text not found)
- Backup testlari
- Edge cases: empty file, unicode, large files

---

## 1.3 Terminal/Shell Improvements
**Fayl:** `tools/shell_tools.py` (yangilanadi)

### Yangiliklar:
```python
@tool(
    name="run_command",
    description="Shell command ishga tushirish (yaxshilangan).",
    params={
        "command": "Buyruq",
        "cwd": "Ishchi directoriya",
        "timeout": "Timeout (soniya, default: 30)",
        "env": "Environment variables (dict)"
    }
)
def run_command(ws, args):
    command = args["command"]
    cwd = args.get("cwd", ws)
    timeout = args.get("timeout", 30)
    env = {**os.environ, **args.get("env", {})}
    
    # Security: deny-list tekshirish
    if is_denied(command):
        return {"ok": False, "error": "Command denied by safety policy"}
    
    # Streaming output (long-running commands uchun)
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return {
            "ok": process.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode,
            "duration_ms": process.elapsed_time
        }
    except subprocess.TimeoutExpired:
        process.kill()
        return {"ok": False, "error": f"Timeout after {timeout}s"}
```

### Package Manager Awareness:
```python
# tools/package_managers.py
class PackageManagerDetector:
    """Loyiha turini aniqlab, to'g'ri package manager'ni tanlaydi."""
    
    DETECTIONS = {
        "package.json": {"cmd": "npm", "install": "npm install", "test": "npm test"},
        "requirements.txt": {"cmd": "pip", "install": "pip install -r requirements.txt", "test": "pytest"},
        "pyproject.toml": {"cmd": "pip", "install": "pip install -e .", "test": "pytest"},
        "Cargo.toml": {"cmd": "cargo", "install": "cargo build", "test": "cargo test"},
        "go.mod": {"cmd": "go", "install": "go mod download", "test": "go test ./..."},
    }
    
    def detect(self, workspace: str) -> Optional[dict]:
        for filename, config in self.DETECTIONS.items():
            if os.path.exists(os.path.join(workspace, filename)):
                return config
        return None

@tool(
    name="install_dependencies",
    description="Loyiha dependency'larini o'rnatish (avtomatik aniqlash).",
    params={"workspace": "Loyiha directoriyasi"}
)
def install_dependencies(ws, args):
    detector = PackageManagerDetector()
    config = detector.detect(ws)
    if not config:
        return {"ok": False, "error": "No package manager detected"}
    
    return run_command(ws, {"command": config["install"], "cwd": ws})
```

### Testlar:
- `tests/test_shell_tools.py` — Streaming output testlari
- Timeout testlari
- Package manager detection testlari
- Environment variable testlari

---

# v5.1 — LANGUAGE INTELLIGENCE (3-6 hafta)

## 2.1 LSP Integration
**Fayl:** `tools/lsp_client.py` (yangi)

### Detallar:
```python
# tools/lsp_client.py
from pygls.server import LanguageServer
from lsprotocol import types

class LSPClient:
    """Language Server Protocol client — kod tushunish uchun."""
    
    def __init__(self, language: str = "python"):
        self.language = language
        self.server = None
        self._capabilities = {}
    
    async def start(self, server_path: str = None):
        """LSP server'ni ishga tushirish."""
        if self.language == "python":
            # pylsp yoki pyright ishlatish
            cmd = server_path or "pylsp"
        elif self.language in ("javascript", "typescript"):
            cmd = server_path or "typescript-language-server"
        
        self.server = await self._start_server(cmd)
        self._capabilities = await self.server.initialize()
    
    async def goto_definition(self, file_path: str, line: int, character: int) -> list[Location]:
        """Definitsiya joyiga o'tish."""
        params = types.TextDocumentPositionParams(
            text_document=types.TextDocumentIdentifier(uri=file_path),
            position=types.Position(line=line, character=character)
        )
        result = await self.server.text_document_definition(params)
        return result
    
    async def find_references(self, file_path: str, line: int, character: int) -> list[Location]:
        """Barcha reference'larni topish."""
        params = types.ReferenceParams(
            text_document=types.TextDocumentIdentifier(uri=file_path),
            position=types.Position(line=line, character=character),
            context=types.ReferenceContext(include_declarations=True)
        )
        result = await self.server.text_document_references(params)
        return result
    
    async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Xatoliklar va ogohlantirishlar."""
        # PublishDiagnostics notification'dan olish
        return self._diagnostics.get(file_path, [])
    
    async def hover(self, file_path: str, line: int, character: int) -> Optional[Hover]:
        """Hover ma'lumot — tur, izoh."""
        params = types.TextDocumentPositionParams(
            text_document=types.TextDocumentIdentifier(uri=file_path),
            position=types.Position(line=line, character=character)
        )
        return await self.server.text_document_hover(params)
    
    async def completion(self, file_path: str, line: int, character: int) -> list[CompletionItem]:
        """Autocomplete."""
        params = types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=file_path),
            position=types.Position(line=line, character=character)
        )
        return await self.server.text_document_completion(params)
    
    async def document_symbols(self, file_path: str) -> list[SymbolInformation]:
        """Fayl ichidagi barcha symbol'lar (class, function, variable)."""
        params = types.DocumentSymbolParams(
            text_document=types.TextDocumentIdentifier(uri=file_path)
        )
        return await self.server.text_document_document_symbol(params)
    
    async def rename(self, file_path: str, line: int, character: int, new_name: str) -> WorkspaceEdit:
        """Rename refactoring — barcha reference'larni yangilash."""
        params = types.RenameParams(
            text_document=types.TextDocumentIdentifier(uri=file_path),
            position=types.Position(line=line, character=character),
            new_name=new_name
        )
        return await self.server.text_document_rename(params)
```

### Tool'lar sifatida:
```python
# tools/lsp_tools.py
@tool(name="goto_definition", description="Definitsiya joyiga o'tish")
def goto_definition(ws, args):
    file_path = args["file_path"]
    line = args["line"]
    character = args["character"]
    
    client = get_lsp_client(file_path)
    locations = client.goto_definition(file_path, line, character)
    
    return {
        "ok": True,
        "locations": [
            {"file": loc.uri, "line": loc.range.start.line, "character": loc.range.start.character}
            for loc in locations
        ]
    }

@tool(name="find_references", description="Barcha reference'larni topish")
def find_references(ws, args):
    pass

@tool(name="get_diagnostics", description="Xatoliklarni olish")
def get_diagnostics(ws, args):
    pass

@tool(name="rename_symbol", description="Symbol nomini o'zgartirish (barcha reference'lar bilan)")
def rename_symbol(ws, args):
    pass
```

### Testlar:
- `tests/test_lsp.py` — LSP client unit testlari
- Mock LSP server bilan
- Definition, references, hover, completion testlari
- Rename testlari

---

## 2.2 AST-Based Code Search
**Fayl:** `tools/ast_search.py` (yangi)

```python
# tools/ast_search.py
import ast
from typing import Optional

class ASTSearcher:
    """AST-based kod qidirish — semantik tushunish."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
    
    def find_definitions(self, query: str) -> list[dict]:
        """Definitsiya topish — class, function, variable."""
        results = []
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if query.lower() in node.name.lower():
                        results.append({
                            "type": "class",
                            "name": node.name,
                            "file": py_file,
                            "line": node.lineno,
                            "end_line": getattr(node, "end_lineno", None)
                        })
                elif isinstance(node, ast.FunctionDef):
                    if query.lower() in node.name.lower():
                        results.append({
                            "type": "function",
                            "name": node.name,
                            "file": py_file,
                            "line": node.lineno,
                            "end_line": getattr(node, "end_lineno", None),
                            "args": [arg.arg for arg in node.args.args]
                        })
        return results
    
    def find_callers(self, function_name: str) -> list[dict]:
        """Qaysi funksiyalar shu function'ni chaqiradi."""
        callers = []
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == function_name:
                        callers.append({
                            "file": py_file,
                            "line": node.lineno,
                            "context": self._get_context(py_file, node.lineno)
                        })
                    elif isinstance(node.func, ast.Attribute) and node.func.attr == function_name:
                        callers.append({
                            "file": py_file,
                            "line": node.lineno,
                            "context": self._get_context(py_file, node.lineno)
                        })
        return callers
    
    def find_imports(self, module_name: str) -> list[dict]:
        """Qaysi fayllar shu module'ni import qiladi."""
        imports = []
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if module_name in alias.name:
                            imports.append({"file": py_file, "line": node.lineno, "import": alias.name})
                elif isinstance(node, ast.ImportFrom):
                    if node.module and module_name in node.module:
                        imports.append({"file": py_file, "line": node.lineno, "from": node.module})
        return imports
    
    def get_class_hierarchy(self, class_name: str) -> dict:
        """Class ierarxiyisi — parent va children."""
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    bases = [self._get_base_name(b) for b in node.bases]
                    return {
                        "name": class_name,
                        "file": py_file,
                        "line": node.lineno,
                        "bases": bases,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    }
        return {}
    
    def get_function_calls_in_file(self, file_path: str) -> list[dict]:
        """Bitta fayldagi barcha function call'lar."""
        tree = self._parse_file(file_path)
        if tree is None:
            return []
        
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append({"name": node.func.id, "line": node.lineno})
                elif isinstance(node.func, ast.Attribute):
                    calls.append({"name": node.func.attr, "line": node.lineno})
        return calls
```

### Tool'lar:
```python
@tool(name="ast_search", description="AST-based kod qidirish")
def ast_search(ws, args):
    searcher = ASTSearcher(ws)
    query_type = args["type"]  # definition, callers, imports, hierarchy
    query = args["query"]
    
    if query_type == "definition":
        return {"ok": True, "results": searcher.find_definitions(query)}
    elif query_type == "callers":
        return {"ok": True, "results": searcher.find_callers(query)}
    elif query_type == "imports":
        return {"ok": True, "results": searcher.find_imports(query)}
    elif query_type == "hierarchy":
        return {"ok": True, "result": searcher.get_class_hierarchy(query)}
```

### Testlar:
- `tests/test_ast_search.py` — Definition, callers, imports testlari
- Hierarchy testlari
- Edge cases: circular imports, dynamic imports

---

## 2.3 Structured Git Integration
**Fayl:** `tools/git_tools.py` (yangi)

```python
# tools/git_tools.py
import subprocess
import json
from dataclasses import dataclass

@dataclass
class GitStatus:
    branch: str
    modified: list[str]
    staged: list[str]
    untracked: list[str]
    ahead: int
    behind: int

@dataclass
class GitDiff:
    file: str
    additions: int
    deletions: int
    hunks: list[dict]

@dataclass
class GitCommit:
    hash: str
    message: str
    author: str
    date: str
    files_changed: list[str]

class GitClient:
    """Structured git operations."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
    
    def status(self) -> GitStatus:
        """Git status — structured."""
        result = self._run("git status --porcelain -b")
        lines = result.strip().split("\n")
        
        branch = lines[0].replace("## ", "")
        modified, staged, untracked = [], [], []
        
        for line in lines[1:]:
            if line.startswith(" M"):
                modified.append(line[3:])
            elif line.startswith("M"):
                staged.append(line[3:])
            elif line.startswith("??"):
                untracked.append(line[3:])
        
        return GitStatus(branch=branch, modified=modified, staged=staged, untracked=untracked)
    
    def diff(self, file: str = None, staged: bool = False) -> list[GitDiff]:
        """Git diff — structured hunks."""
        cmd = "git diff --cached" if staged else "git diff"
        if file:
            cmd += f" {file}"
        
        result = self._run(cmd)
        return self._parse_diff(result)
    
    def log(self, count: int = 10) -> list[GitCommit]:
        """Git log — structured."""
        cmd = f'git log --format="%H|%s|%an|%ai" -{count}'
        result = self._run(cmd)
        
        commits = []
        for line in result.strip().split("\n"):
            if "|" in line:
                parts = line.split("|")
                commits.append(GitCommit(
                    hash=parts[0],
                    message=parts[1],
                    author=parts[2],
                    date=parts[3],
                    files_changed=[]
                ))
        return commits
    
    def commit(self, message: str, files: list[str] = None) -> dict:
        """Git commit — avtomatik message generation bilan."""
        if files:
            for f in files:
                self._run(f"git add {f}")
        else:
            self._run("git add -A")
        
        result = self._run(f'git commit -m "{message}"')
        return {"ok": "nothing to commit" not in result, "message": message}
    
    def create_branch(self, name: str) -> dict:
        """Branch yaratish va o'tish."""
        self._run(f"git checkout -b {name}")
        return {"ok": True, "branch": name}
    
    def stash(self) -> dict:
        """Stash yaratish."""
        result = self._run("git stash")
        return {"ok": "No local changes" not in result}
    
    def stash_pop(self) -> dict:
        """Stash'dan qaytarish."""
        result = self._run("git stash pop")
        return {"ok": "conflict" not in result.lower()}
    
    def blame(self, file: str) -> list[dict]:
        """Git blame — har qator uchun muallif."""
        result = self._run(f"git blame {file}")
        lines = []
        for line in result.strip().split("\n"):
            # Format: ^hash (author date line) content
            if "(" in line:
                hash_part = line[:line.index("(")].strip()
                rest = line[line.index("(")+1:]
                author = rest[:rest.index(")")].strip()
                content = rest[rest.index(")")+1:].strip()
                lines.append({"author": author, "content": content})
        return lines
    
    def generate_commit_message(self, diff: str) -> str:
        """Diff asosida commit message generatsiya qilish (LLM yordamida)."""
        # LLM chaqirish yoki rule-based generation
        pass
    
    def _run(self, command: str) -> str:
        result = subprocess.run(
            command, shell=True, cwd=self.workspace,
            capture_output=True, text=True, timeout=30
        )
        return result.stdout + result.stderr
```

### Tool'lar:
```python
@tool(name="git_status", description="Git status (structured)")
def git_status(ws, args):
    client = GitClient(ws)
    status = client.status()
    return {"ok": True, "status": status.__dict__}

@tool(name="git_diff", description="Git diff (structured hunks)")
def git_diff(ws, args):
    client = GitClient(ws)
    diffs = client.diff(args.get("file"), args.get("staged", False))
    return {"ok": True, "diffs": [d.__dict__ for d in diffs]}

@tool(name="git_commit", description="Git commit (message generation bilan)")
def git_commit(ws, args):
    client = GitClient(ws)
    message = args.get("message") or client.generate_commit_message(client.diff())
    return client.commit(message, args.get("files"))

@tool(name="git_blame", description="Git blame")
def git_blame(ws, args):
    client = GitClient(ws)
    return {"ok": True, "lines": client.blame(args["file"])}
```

### Testlar:
- `tests/test_git_tools.py` — Status, diff, commit, blame testlari
- Mock git bilan
- Branch, stash testlari

---

# v5.2 — DEV WORKFLOW (6-10 hafta)

## 3.1 Test Runner Integration
**Fayl:** `tools/test_runner.py` (yangi)

```python
# tools/test_runner.py
import subprocess
import re
from dataclasses import dataclass

@dataclass
class TestResult:
    name: str
    status: str  # passed, failed, error, skipped
    duration: float
    error_message: Optional[str]
    file: str
    line: int

@dataclass
class TestSuiteResult:
    framework: str  # pytest, jest, cargo test
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration: float
    results: list[TestResult]
    summary: str

class TestRunner:
    """Test framework integratsiyasi."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.detector = TestFrameworkDetector()
    
    def detect_framework(self) -> str:
        """Qaysi test framework ishlatilayotganini aniqlash."""
        return self.detector.detect(self.workspace)
    
    def run(self, pattern: str = None, verbose: bool = True) -> TestSuiteResult:
        """Testlarni ishga tushirish va natijalarni parse qilish."""
        framework = self.detect_framework()
        
        if framework == "pytest":
            return self._run_pytest(pattern, verbose)
        elif framework == "jest":
            return self._run_jest(pattern, verbose)
        elif framework == "cargo":
            return self._run_cargo_test(pattern, verbose)
        
        return TestSuiteResult(framework="unknown", total=0, passed=0, failed=0, 
                               errors=0, skipped=0, duration=0, results=[], summary="Unknown framework")
    
    def _run_pytest(self, pattern: str, verbose: bool) -> TestSuiteResult:
        cmd = "python -m pytest"
        if pattern:
            cmd += f" {pattern}"
        if verbose:
            cmd += " -v"
        cmd += " --tb=short -q"
        
        result = subprocess.run(cmd, shell=True, cwd=self.workspace, 
                               capture_output=True, text=True, timeout=300)
        
        return self._parse_pytest_output(result.stdout + result.stderr)
    
    def _parse_pytest_output(self, output: str) -> TestSuiteResult:
        """Pytest chiqishini parse qilish."""
        # "875 passed, 1 skipped, 0 failed" pattern
        summary_match = re.search(r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped", output)
        
        results = []
        # Individual test results
        for line in output.split("\n"):
            if "PASSED" in line:
                name = line.split("::")[-1].split(" ")[0]
                results.append(TestResult(name=name, status="passed", duration=0, 
                                         error_message=None, file="", line=0))
            elif "FAILED" in line:
                name = line.split("::")[-1].split(" ")[0]
                error = line[line.index("FAILED"):]
                results.append(TestResult(name=name, status="failed", duration=0,
                                         error_message=error, file="", line=0))
        
        return TestSuiteResult(
            framework="pytest",
            total=len(results),
            passed=sum(1 for r in results if r.status == "passed"),
            failed=sum(1 for r in results if r.status == "failed"),
            errors=0,
            skipped=sum(1 for r in results if r.status == "skipped"),
            duration=0,
            results=results,
            summary=output
        )
    
    def get_failure_details(self, test_name: str) -> dict:
        """Muvaffaqiyatsiz test uchun batafsil ma'lumot."""
        # Stack trace, expected vs actual, va hokazo
        pass
    
    def suggest_fix(self, failure: TestResult) -> str:
        """Test xatosiga qarab tuzatish taklifi."""
        # LLM yordamida xatoni tahlil qilish va tuzatish taklifi
        pass

class TestFrameworkDetector:
    def detect(self, workspace: str) -> str:
        if os.path.exists(os.path.join(workspace, "pytest.ini")) or \
           os.path.exists(os.path.join(workspace, "pyproject.toml")):
            return "pytest"
        elif os.path.exists(os.path.join(workspace, "package.json")):
            return "jest"
        elif os.path.exists(os.path.join(workspace, "Cargo.toml")):
            return "cargo"
        return "unknown"
```

### Tool'lar:
```python
@tool(name="run_tests", description="Testlarni ishga tushirish")
def run_tests(ws, args):
    runner = TestRunner(ws)
    result = runner.run(args.get("pattern"), args.get("verbose", True))
    return {"ok": True, "result": result.__dict__}

@tool(name="get_failure_details", description="Muvaffaqiyatsiz test tafsilotlari")
def get_failure_details(ws, args):
    runner = TestRunner(ws)
    details = runner.get_failure_details(args["test_name"])
    return {"ok": True, "details": details}

@tool(name="suggest_test_fix", description="Test xatosini tuzatish taklifi")
def suggest_test_fix(ws, args):
    runner = TestRunner(ws)
    # Failure obyektini yaratish va fix taklifi
    pass
```

### Auto-Fix Flow:
```python
class AutoFixEngine:
    """Test xatolarini avtomatik tuzatish."""
    
    def __init__(self, workspace: str, llm: BaseLLM):
        self.workspace = workspace
        self.llm = llm
        self.runner = TestRunner(workspace)
        self.editor = FileEditor(workspace)
    
    def fix_failing_tests(self, max_attempts: int = 3) -> dict:
        """Muvaffaqiyatsiz testlarni tuzatish."""
        for attempt in range(max_attempts):
            # 1. Testlarni ishga tushirish
            result = self.runner.run()
            
            if result.failed == 0:
                return {"ok": True, "fixed": True, "attempts": attempt + 1}
            
            # 2. Muvaffaqiyatsiz testlarni tahlil qilish
            failures = [r for r in result.results if r.status == "failed"]
            
            for failure in failures:
                # 3. Xatoni tushunish
                details = self.runner.get_failure_details(failure.name)
                
                # 4. LLM yordamida tuzatish generatsiya qilish
                fix = self._generate_fix(failure, details)
                
                # 5. Tuzatishni qo'llash
                if fix:
                    self.editor.apply_fix(fix)
            
            # 6. Qayta ishga tushirish
            continue
        
        return {"ok": False, "fixed": False, "attempts": max_attempts}
```

---

## 3.2 Context Window Management
**Fayl:** `context/smart_context.py` (yangi)

```python
# context/smart_context.py
import hashlib
from dataclasses import dataclass

@dataclass
class FileRelevance:
    path: str
    score: float  # 0.0 - 1.0
    reason: str

class SmartContextManager:
    """Kontekst boshqaruvchi — faqat muhim fayllarni qo'shadi."""
    
    def __init__(self, workspace: str, max_tokens: int = 8000):
        self.workspace = workspace
        self.max_tokens = max_tokens
        self._embeddings_cache = {}
    
    def select_files(self, task: str, all_files: list[str]) -> list[FileRelevance]:
        """Task uchun eng muhim fayllarni tanlash."""
        relevance = []
        
        for file_path in all_files:
            score = self._calculate_relevance(task, file_path)
            if score > 0.3:  # Threshold
                reason = self._explain_relevance(task, file_path)
                relevance.append(FileRelevance(path=file_path, score=score, reason=reason))
        
        # Score bo'yicha saralash
        relevance.sort(key=lambda x: x.score, reverse=True)
        
        # Token budget ichida qoldirish
        selected = []
        total_tokens = 0
        for r in relevance:
            file_tokens = self._estimate_tokens(r.path)
            if total_tokens + file_tokens <= self.max_tokens:
                selected.append(r)
                total_tokens += file_tokens
            else:
                break
        
        return selected
    
    def _calculate_relevance(self, task: str, file_path: str) -> float:
        """Faylning task uchun muhimligini hisoblash."""
        score = 0.0
        
        # 1. Nom mosligi
        task_words = set(task.lower().split())
        file_name = os.path.basename(file_path).lower()
        for word in task_words:
            if word in file_name:
                score += 0.3
        
        # 2. Import bog'liqligi
        # Agar task "edit function X" bo'lsa, X ni import qilgan fayllar muhim
        pass
        
        # 3. O'zgarishlar (git diff)
        # O'zgargan fayllar ko'proq muhim
        pass
        
        # 4. Tezlik (recently accessed)
        # oxirgi marta ochilgan fayllar
        pass
        
        return min(score, 1.0)
    
    def compact_context(self, messages: list[dict]) -> list[dict]:
        """Eski kontekstni qisqartirish."""
        if self._count_tokens(messages) <= self.max_tokens:
            return messages
        
        # Strategiya: eski xabarlarni qisqartirish
        compacted = []
        for i, msg in enumerate(messages):
            if i < len(messages) - 10:  # Oxirgi 10 xabarni saqlash
                # Faqat muhim qismlarni saqlash
                compacted.append(self._summarize_message(msg))
            else:
                compacted.append(msg)
        
        return compacted
    
    def build_prompt(self, task: str, files: list[str], history: list[dict]) -> list[dict]:
        """Optimal prompt qurish."""
        # 1. Task tavsifi
        # 2. Tanlangan fayllar (relevance score bilan)
        # 3. Qisqartirilgan tarix
        # 4. Goal pin (doimo saqlanadi)
        pass
```

---

## 3.3 Import Graph Analysis
**Fayl:** `analysis/import_graph.py` (yangi)

```python
# analysis/import_graph.py
import ast
from collections import defaultdict

class ImportGraph:
    """Modullar o'rtasidagi bog'liqlilik grafigi."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.graph = defaultdict(set)  # module -> set of imported modules
        self.reverse_graph = defaultdict(set)  # module -> set of modules that import it
    
    def build(self):
        """Grafigi qurish."""
        for py_file in self._iter_python_files():
            module = self._file_to_module(py_file)
            imports = self._get_imports(py_file)
            
            for imp in imports:
                self.graph[module].add(imp)
                self.reverse_graph[imp].add(module)
    
    def get_dependencies(self, module: str) -> set:
        """Module qaysi module'larga bog'liq."""
        return self.graph.get(module, set())
    
    def get_dependents(self, module: str) -> set:
        """Qaysi module'lar shu module'ga bog'liq."""
        return self.reverse_graph.get(module, set())
    
    def find_cycles(self) -> list[list[str]]:
        """Circular import'larni topish."""
        cycles = []
        visited = set()
        
        def dfs(node, path):
            if node in path:
                cycles.append(path[path.index(node):] + [node])
                return
            if node in visited:
                return
            
            visited.add(node)
            path.append(node)
            
            for dep in self.graph.get(node, []):
                dfs(dep, path.copy())
        
        for module in self.graph:
            dfs(module, [])
        
        return cycles
    
    def get_impact_analysis(self, file_path: str) -> dict:
        """Bitta fayl o'zgarsa — qaysi fayllar ta'sirlanadi."""
        module = self._file_to_module(file_path)
        affected = set()
        
        def collect_dependents(mod):
            for dep in self.reverse_graph.get(mod, []):
                if dep not in affected:
                    affected.add(dep)
                    collect_dependents(dep)
        
        collect_dependents(module)
        
        return {
            "file": file_path,
            "module": module,
            "directly_affected": list(self.reverse_graph.get(module, set())),
            "transitively_affected": list(affected - self.reverse_graph.get(module, set())),
            "total_affected": len(affected)
        }
    
    def visualize(self) -> str:
        """Graf vizualizatsiyasi (ASCII yoki Mermaid)."""
        lines = ["graph LR"]
        for module, deps in self.graph.items():
            for dep in deps:
                lines.append(f"  {module} --> {dep}")
        return "\n".join(lines)
```

---

# v5.3 — ADVANCED (10-16 hafta)

## 4.1 Multi-File Atomic Operations
**Fayl:** `tools/multi_file.py` (yangi)

```python
# tools/multi_file.py
class TransactionalEditor:
    """Bir nechta faylni bir vaqtda tahrirlash — atomic."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self._changes = []
        self._backups = {}
    
    def queue_edit(self, file_path: str, old_text: str, new_text: str):
        """O'zgarishni navbatga qo'shish."""
        self._changes.append({
            "file": file_path,
            "old": old_text,
            "new": new_text
        })
    
    def commit(self) -> dict:
        """Barcha o'zgarishlarni bir vaqtda qo'llash."""
        # 1. Backup
        for change in self._changes:
            path = os.path.join(self.workspace, change["file"])
            backup = path + ".transaction_backup"
            with open(path, "r") as f:
                self._backups[path] = f.read()
            with open(backup, "w") as f:
                f.write(self._backups[path])
        
        # 2. Apply changes
        applied = []
        for change in self._changes:
            path = os.path.join(self.workspace, change["file"])
            with open(path, "r") as f:
                content = f.read()
            
            if change["old"] not in content:
                # Rollback
                self._rollback()
                return {"ok": False, "error": f"Text not found in {change['file']}"}
            
            content = content.replace(change["old"], change["new"], 1)
            
            with open(path, "w") as f:
                f.write(content)
            
            applied.append(change["file"])
        
        return {"ok": True, "files_changed": applied}
    
    def rollback(self) -> dict:
        """Barcha o'zgarishlarni bekor qilish."""
        for path, content in self._backups.items():
            with open(path, "w") as f:
                f.write(content)
        
        # Backup fayllarni o'chirish
        for path in self._backups:
            backup = path + ".transaction_backup"
            if os.path.exists(backup):
                os.remove(backup)
        
        return {"ok": True, "rolled_back": len(self._backups)}

@tool(name="multi_edit", description="Bir nechta faylni bir vaqtda tahrirlash")
def multi_edit(ws, args):
    editor = TransactionalEditor(ws)
    
    for edit in args["edits"]:
        editor.queue_edit(edit["file"], edit["old_text"], edit["new_text"])
    
    return editor.commit()
```

---

## 4.2 Code Review Tool
**Fayl:** `tools/code_review.py` (yangi)

```python
# tools/code_review.py
class CodeReviewer:
    """Kod sharh — diff tahlili + lint + xavfsizlik."""
    
    def __init__(self, workspace: str, llm: BaseLLM):
        self.workspace = workspace
        self.llm = llm
    
    def review_diff(self, diff: str) -> dict:
        """Diff ni sharhlash."""
        issues = []
        
        # 1. Lint issues
        lint_issues = self._run_lint(diff)
        issues.extend(lint_issues)
        
        # 2. Security issues
        security_issues = self._check_security(diff)
        issues.extend(security_issues)
        
        # 3. Performance issues
        perf_issues = self._check_performance(diff)
        issues.extend(perf_issues)
        
        # 4. Style issues
        style_issues = self._check_style(diff)
        issues.extend(style_issues)
        
        # 5. LLM-based review
        llm_review = self._llm_review(diff)
        
        return {
            "issues": issues,
            "summary": llm_review["summary"],
            "suggestions": llm_review["suggestions"],
            "score": self._calculate_score(issues)
        }
    
    def _run_lint(self, diff: str) -> list[dict]:
        """Ruff/ESLint ishlatish."""
        issues = []
        # Ruff yoki ESLint bilan tekshirish
        pass
        return issues
    
    def _check_security(self, diff: str) -> list[dict]:
        """Xavfsizlik muammolarini tekshirish."""
        issues = []
        patterns = [
            (r"eval\(", "Use of eval() — potential security risk"),
            (r"exec\(", "Use of exec() — potential security risk"),
            (r"subprocess\.call.*shell=True", "Shell=True — command injection risk"),
            (r"password\s*=\s*['\"]", "Hardcoded password"),
            (r"api[_-]?key\s*=\s*['\"]", "Hardcoded API key"),
        ]
        for pattern, message in patterns:
            if re.search(pattern, diff):
                issues.append({"type": "security", "message": message, "severity": "high"})
        return issues
    
    def _check_performance(self, diff: str) -> list[dict]:
        """Performance muammolarini tekshirish."""
        issues = []
        # Nested loops, N+1 queries, etc.
        pass
        return issues
    
    def _llm_review(self, diff: str) -> dict:
        """LLM yordamida kod sharhi."""
        prompt = f"""Review this code diff and provide:
1. Summary of changes
2. Potential issues
3. Suggestions for improvement
4. Security concerns

Diff:
{diff}
"""
        response = self.llm.chat([{"role": "user", "content": prompt}])
        return {
            "summary": response.get("content", ""),
            "suggestions": []
        }
```

---

## 4.3 Browser/Visual Preview
**Fayl:** `tools/browser.py` (yangi)

```python
# tools/browser.py
class BrowserAutomation:
    """Browser avtomatizatsiyasi — web development uchun."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self._playwright = None
    
    async def start(self):
        """Playwright'ni ishga tushirish."""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
    
    async def screenshot(self, url: str, path: str) -> dict:
        """Screenshot olish."""
        page = await self._browser.new_page()
        await page.goto(url)
        await page.screenshot(path=path, full_page=True)
        await page.close()
        return {"ok": True, "path": path}
    
    async def get_dom(self, url: str) -> dict:
        """DOM tree'ni olish."""
        page = await self._browser.new_page()
        await page.goto(url)
        dom = await page.evaluate("document.documentElement.outerHTML")
        await page.close()
        return {"ok": True, "dom": dom}
    
    async def inspect_element(self, url: str, selector: str) -> dict:
        """Elementni tekshirish."""
        page = await self._browser.new_page()
        await page.goto(url)
        element = await page.query_selector(selector)
        if element:
            box = await element.bounding_box()
            styles = await page.evaluate(f"""
                (() => {{
                    const el = document.querySelector('{selector}');
                    const computed = window.getComputedStyle(el);
                    return {{
                        width: computed.width,
                        height: computed.height,
                        backgroundColor: computed.backgroundColor,
                        color: computed.color,
                        fontSize: computed.fontSize
                    }};
                }})()
            """)
            await page.close()
            return {"ok": True, "box": box, "styles": styles}
        await page.close()
        return {"ok": False, "error": "Element not found"}
    
    async def compare_screenshots(self, before: str, after: str) -> dict:
        """Ikki screenshot'ni solishtirish."""
        # Pixel-based comparison
        pass
```

---

# v5.4 — POLISH (16-20 hafta)

## 5.1 Performance Optimization
- Lazy loading for LSP
- Caching for AST analysis
- Incremental import graph updates
- Token counting optimization

## 5.2 UX Improvements
- Progress indicators for long operations
- Color-coded terminal output
- Interactive mode for ambiguous operations
- Undo/redo support

## 5.3 Documentation
- API reference
- Architecture guide
- Contributing guide
- User manual

## 5.4 Testing
- Integration tests with real LLMs
- E2E tests for all workflows
- Performance benchmarks
- Security audit

---

# IMPLEMENTATION SEQUENCE

## Hafta 1-2: Foundation
- [ ] `llm/cloud_client.py` — OpenAI, Anthropic, Gemini
- [ ] `llm/model_selector.py` — Task-based model selection
- [ ] `llm/cost_tracker.py` — Cost tracking
- [ ] `tools/fs_tools.py` — `edit_file` tool
- [ ] `tools/fs_tools.py` — `read_file` with offset/limit
- [ ] Testlar

## Hafta 3-4: Shell + Package
- [ ] `tools/shell_tools.py` — Streaming output
- [ ] `tools/package_managers.py` — Auto-detection
- [ ] Testlar

## Hafta 5-7: LSP
- [ ] `tools/lsp_client.py` — pygls integration
- [ ] `tools/lsp_tools.py` — Definition, references, hover
- [ ] `tools/ast_search.py` — AST-based search
- [ ] Testlar

## Hafta 8-10: Git
- [ ] `tools/git_tools.py` — Structured git operations
- [ ] `tools/git_tools.py` — Commit message generation
- [ ] Testlar

## Hafta 11-13: Test Runner
- [ ] `tools/test_runner.py` — Pytest/Jest integration
- [ ] `tools/auto_fix.py` — Auto-fix failing tests
- [ ] Testlar

## Hafta 14-16: Context
- [ ] `context/smart_context.py` — Relevance scoring
- [ ] `context/compaction.py` — Context compaction
- [ ] Testlar

## Hafta 17-18: Multi-file
- [ ] `tools/multi_file.py` — Transactional edits
- [ ] `tools/code_review.py` — Diff review
- [ ] Testlar

## Hafta 19-20: Polish
- [ ] Performance optimization
- [ ] UX improvements
- [ ] Documentation
- [ ] Final testing

---

# RESOURCE REQUIREMENTS

## API Keys (kerak bo'lganlar):
- OpenAI API key (GPT-4o access)
- Anthropic API key (Claude 3.5 access)
- Google Gemini API key (optional)

## Packages (pip install):
```
openai>=1.0
anthropic>=0.20
google-generativeai>=0.5
pygls>=1.0
lsprotocol>=2023
ruff>=0.1
playwright>=1.40
tiktoken>=0.5
```

## Infrastructure:
- LSP server binaries (pylsp, typescript-language-server)
- Playwright browsers
- Ruff linter

---

# SUCCESS METRICS

| Metric | Current | v5.0 Target | v5.4 Target |
|--------|---------|-------------|-------------|
| LLM Models | 1 (Ollama) | 4 (Ollama+Cloud) | 4+ |
| Edit Precision | 30% | 90% | 99% |
| Code Search | Regex | AST+LSP | Semantic |
| Git Operations | Shell | Structured | Full |
| Test Integration | Raw output | Parsed | Auto-fix |
| Context Efficiency | Full files | Relevant | Optimal |
| Response Time | 5-30s | 2-10s | 1-5s |
| Task Completion | 60% | 80% | 95% |
