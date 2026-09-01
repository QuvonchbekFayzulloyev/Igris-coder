# IGRIS-CODER: Super-Light Strong Local Coder Agent LLM
## Complete Architecture & Development Plan v2.0
### With Claude-Style Agent Console + Obsidian 2nd Brain + Live Preview Sandbox

---

## Design Philosophy

Build a **sub-1B parameter transformer** that punches above its weight through:
1. **Modern architecture** (GQA, SwiGLU, RoPE, Flash Attention 2)
2. **Tool-use & self-correction** (calculator, python executor, clarifying questions)
3. **Obsidian 2nd Brain integration** (Wanderloots LLM Wiki + Kepano Obsidian Skills)
4. **Agent Console GUI** (Claude sidebar + VS Code workspace + live preview + knowledge graph)
5. **Streaming data pipeline** (no disk limits, process TB-scale datasets)

Target: **~400M parameters**, **<=6GB VRAM during training**, **<=2GB at Q4 inference**.

---

## Hardware Context
- **GPU**: NVIDIA RTX 5060 8.5GB VRAM
- **Architecture**: sm_89 (Ada Lovelace successor)
- **Precision**: bf16 native, Flash Attention 2 supported
- **Disk**: Limited -- streaming-first required

---

## RULES

| ID | Rule |
|---|---|
| R1 | Development environment must be reproducible, CUDA-optimized, verified |
| R2 | Must stream and process TB-scale datasets without OOM or disk overflow |
| R3 | Transformer architecture must be production-grade (Llama-3 style, not toy) |
| R4 | Model must specialize in: code generation, data analysis, translation, human-language Q&A with executable results |
| R5 | Reference temp skill `Temp_SKIll_to_build_IgrisLLM.md` if found (advisory only) |
| R6 | Temp skill is advisory -- final architecture decisions are engineering-driven |
| R7 | Model must self-correct by asking clarifying questions before answering |
| R8 | Perfect math accuracy including complex matrix operations (symbolic offload) |
| R9 | GUI must match provided screenshots: Claude sidebar, VS Code agent console, live preview sandbox, markers, Obsidian 2nd Brain |
| R10 | 2nd Brain must use Wanderloots LLM Wiki core + Kepano Obsidian Skills |
| R11 | Domain knowledge bases must include: Engineering, Data Analytics, Windows/Linux OS, Example Usage, Problem Classification (Engineer/Economist/Mathematician/Data Analyst) |

---

## PART A: MODEL ARCHITECTURE

### A.1 Target Specifications

| Spec | Value |
|---|---|
| **Parameters** | ~400M dense |
| **Architecture** | Modern Llama-3 style |
| **Layers** | 20 |
| **Hidden Dim** | 1024 |
| **FFN Dim** | 2816 (SwiGLU 2.75x) |
| **Attention Heads** | 16 query / 4 KV (GQA 4:1) |
| **Context Length** | 4096 native (YaRN to 32K) |
| **Vocab Size** | 32,000 (code-optimized BPE) |
| **Special Tokens** | `<|system|>`, `<|user|>`, `<|assistant|>`, `<|think|>`, `<|/think|>`, `<|calc|>`, `<|python|>`, `<|clarify|>`, `<|critique|>`, `<|marker|>`, `<|fix|>` |
| **Position Encoding** | RoPE (theta=10000) |
| **Normalization** | RMSNorm (pre-norm) |
| **Activation** | SwiGLU |
| **Dropout** | 0.0 (pretraining), 0.1 (SFT) |
| **Tie Embeddings** | True |
| **VRAM Budget** | <=6GB training, <=2GB Q4 inference |

### A.2 Why This Beats GPT-2 Style

| Feature | GPT-2 (Your Current) | IGRIS-CODER-400M |
|---|---|---|
| Attention | Standard Multi-Head (O(n^2) memory) | GQA + Flash Attention 2 (fused, 4x KV reduction) |
| FFN | GELU | SwiGLU (gating captures code syntax) |
| Norm | LayerNorm | RMSNorm (stable at bf16) |
| Position | Learned embeddings | RoPE (better relative, YaRN extrapolation) |
| Context | 512 | 4096 native, 32K YaRN |
| Inference KV Cache | Full | 4x smaller via GQA |

### A.3 Memory Budget (Training)

```
Model params (bf16):           400M x 2  = 800 MB
Gradients:                     400M x 2  = 800 MB
Optimizer states (AdamW fp32): 400M x 8  = 1,600 MB
Activations (gc=True, seq 2048, bs 4):    ~3,000 MB
Flash Attention overhead:                   ~200 MB
--------------------------------------------------
TOTAL:                                      ~6.2 GB  (8.5GB card, 2.3GB headroom)
```

### A.4 File: `model/config.py`

```python
from dataclasses import dataclass

@dataclass
class IgrisConfig:
    vocab_size: int = 32000
    n_layers: int = 20
    d_model: int = 1024
    n_heads: int = 16
    n_kv_heads: int = 4
    d_ff: int = 2816
    rope_theta: float = 10000.0
    rms_norm_eps: float = 1e-6
    max_position_embeddings: int = 4096
    tie_word_embeddings: bool = True
    use_flash_attention: bool = True
    gradient_checkpointing: bool = True
    dropout: float = 0.0
    bos_token_id: int = 1
    eos_token_id: int = 2
    pad_token_id: int = 0
```

---

## PART B: THREE-STAGE TRAINING PIPELINE

### B.1 Stage 1: Continued Pretraining (CPT)

**Objective**: Next-token prediction on massive streaming corpus.

**Data Mix** (streaming, no local download):
- 40% Code: `bigcode/the-stack-v2` (streaming=True)
- 25% Web/Edu: `HuggingFaceFW/fineweb-edu` (streaming=True)
- 15% Math/Reasoning: `EleutherAI/proof-pile-2`, synthetic matrix ops
- 10% Multilingual: Uzbek Wikipedia, English-Uzbek parallel
- 10% Tool-use conversations: synthetic ReAct trajectories

**Hyperparameters**:
- Tokens: 50B-100B
- LR: 4e-4 (warmup 2k steps -> cosine decay to 4e-5)
- Optimizer: AdamW (beta1=0.9, beta2=0.95, eps=1e-8, weight_decay=0.1)
- Batch: Global 512 (micro 4 x accumulate 128)
- Precision: bf16 + Flash Attention + gradient checkpointing
- Checkpointing: Every 1000 steps + best-val-loss auto-save
- Resume: Automatic from latest shard

### B.2 Stage 2: Supervised Fine-Tuning (SFT) -- Agent Behavior

**Objective**: Teach chat format, tool use, coding, translation, data analysis.

**Data**:
- CodeAlpaca-20k (instruction -> code)
- OpenHermes 2.5 (general reasoning)
- Self-generated synthetic:
  - Data analysis tasks (pandas/matplotlib/plotly) with executable outputs
  - Translation pairs (English <-> Uzbek, code comments)
  - Tool-use trajectories (calculator, python execution)
  - Clarifying question datasets (ambiguous query -> clarification)

**Format** (ChatML-style with special tokens):
```
<|system|>You are Igris, a coding agent. You have access to calculator and python tools.
When a question is ambiguous, ask a clarifying question before answering.
Use <|think|>...<|/think|> for reasoning.<|end|>
<|user|>Write a function to invert a matrix<|end|>
<|assistant|><|think|>The user wants matrix inversion. I will provide a numpy solution
and verify with a test case.<|/think|>
```python
import numpy as np

def invert_matrix(m):
    return np.linalg.inv(m)

# Test
a = np.array([[1,2],[3,4]])
print(invert_matrix(a))
```<|end|>
```

**Technique**: Packed sequence training (multiple conversations per sequence, masked cross-attention).

### B.3 Stage 3: Direct Preference Optimization (DPO)

**Objective**: Align model to prefer correct/helpful answers over wrong ones.

**Data**: Synthetic preference pairs from SFT outputs:
- Correct code vs buggy code
- Helpful explanation vs vague explanation
- Safe answer vs hallucinated answer

**Loss**: DPO with beta=0.1, reference model = frozen SFT checkpoint.

**Effect**: Significantly improves instruction following, reduces hallucinations.


---

## PART C: TOOL USE & SELF-CORRECTION ENGINE

### C.1 Special Tool Tokens (injected into vocab)

| Token | Purpose |
|---|---|
| `<|calc|>` | Offload arithmetic to sympy/numexpr sandbox |
| `<|python|>` | Execute code in sandboxed subprocess, feed stdout back |
| `<|search|>` | Search 2nd Brain catalog before answering |
| `<|clarify|>` | Ask user for clarification (Rule 7) |
| `<|critique|>` | Self-critique generated output before finalizing |
| `<|think|>` / `<|/think|>` | Chain-of-thought reasoning (trainable, not just prompt) |
| `<|marker|>` | User marks code region for AI to fix |
| `<|fix|>` | AI signals it is applying a fix to marked region |

### C.2 Self-Correction Loop (Rule 7)

**Training Data** (50k synthetic examples):
```
User: "Fix this"
Assistant:<|clarify|>Could you share the code snippet and the error message?<|/clarify|>

User: "def foo(): return 1/0"
Assistant:<|think|>This raises ZeroDivisionError. I should handle it safely.<|/think|>
```python
def foo():
    try:
        return 1/0
    except ZeroDivisionError:
        return float('inf')
```<|end|>
```

**Inference Engine**:
1. Detect `<|clarify|>` -> pause generation, highlight input box in GUI
2. Detect `<|python|>` -> execute in sandboxed subprocess -> inject stdout
3. Detect `<|calc|>` -> evaluate with sympy -> inject exact result
4. Detect `<|critique|>` -> show self-critique in GUI panel, then generate v2

### C.3 Math Accuracy Injection (Rule 8)

**Problem**: LLMs are bad at exact math.
**Solution**: Hybrid symbolic-numeric approach.

**Training**:
- GSM8K + MATH-500 chain-of-thought traces
- 100k synthetic matrix operations (inversion, eigenvalues, SVD, multiplication)
- Format: NL question -> `<|calc|>numpy.linalg.inv(...)<|/calc|>` -> result

**Inference Integration**:
```python
# In generation loop
if token == "<|calc|>":
    expr = extract_until("<|/calc|>")
    result = safe_eval(expr)  # sympy/numexpr sandbox
    feed_result_back_as_tokens(result)
```

This guarantees **perfect accuracy** on deterministic math by offloading to exact engines.


---

## PART D: STREAMING DATA PIPELINE (MASSIVE DATASETS)

### D.1 Problem
Your 8.5GB VRAM + limited disk cannot hold multi-TB datasets like The Stack v2.

### D.2 Solution: Streaming-First Architecture

```python
from datasets import load_dataset

# NO download -- stream directly from HuggingFace Hub
code_stream = load_dataset("bigcode/the-stack-v2", streaming=True, split="train")
web_stream = load_dataset("HuggingFaceFW/fineweb-edu", streaming=True, split="train")
math_stream = load_dataset("EleutherAI/proof-pile-2", streaming=True, split="train")
```

### D.3 Interleaved Sampler

```python
class InterleavedStreamer:
    # Mixes multiple streaming datasets with configurable ratios
    ratios = {
        "code": 0.40,
        "web": 0.25,
        "math": 0.15,
        "multilingual": 0.10,
        "tool_use": 0.10,
    }
```

### D.4 Memory-Safe Batcher

- `IterableDataset` with shuffle buffer (100k sequences)
- Dynamic padding to longest-in-batch (not fixed context waste)
- Gradient accumulation simulates global batch 512+ without VRAM spike
- Two-tier cache: Hot shard memmap (<=2GB disk) + cold HF Hub fetch

### D.5 Validation Split

Hold out 5B tokens using deterministic hashing:
```python
def is_validation(doc_id):
    return hash(doc_id) % 100 < 5  # 5% validation
```


---

## PART E: GUI ARCHITECTURE -- AGENT CONSOLE

### E.1 Layout (Matching Your Screenshots)

```
+-----------------------------------------------------------------------------+
|  +----------+  +---------------------------------------------------------+  |
|  |          |  |  +---------+---------+----------+---------+            |  |
|  |  SIDEBAR |  |  |  Chat   | Preview | 2nd Brain| Web AI  |            |  |
|  |  (Claude |  |  +---------+---------+----------+---------+            |  |
|  |   style) |  |                                                     |  |
|  |          |  |  +---------------------------------------------+    |  |
|  |  + New   |  |  |  AGENT CHAT / CODE EDITOR / PREVIEW / GRAPH |    |  |
|  |  Chats   |  |  |                                             |    |  |
|  |  Projects|  |  |  * read_file src/tools/fs.ts               |    |  |
|  |  Artifacts|  |  |  * apply_patch src/agent/executor.ts       |    |  |
|  |  Code    |  |  |    - def fetch_data(url):                   |    |  |
|  |  Customize|  |  |    + def fetch_data(url: str) -> dict:      |    |  |
|  |  Design  |  |  |    + if not url.startswith("http"):          |    |  |
|  |          |  |  |    + raise ValueError("invalid url")         |    |  |
|  |  Products|  |  |                                             |    |  |
|  |  ------- |  |  |  [Marker] ---> [Fix Issue]                   |    |  |
|  |  Starred |  |  |                                             |    |  |
|  |  Recents |  |  +---------------------------------------------+    |  |
|  |          |  |                                                     |  |
|  |  Ghost   |  |  +---------------------------------------------+    |  |
|  |  master  |  |  |  STATUS PIPELINE:                            |    |  |
|  |  (avatar)|  |  |  * Plan  --- * Read  --- * Edit  --- o Test  --- o Review|  |
|  |          |  |  +---------------------------------------------+    |  |
|  |          |  |                                                     |  |
|  |          |  |  +---------------------------------------------+    |  |
|  |          |  |  |  TERMINAL:                                   |    |  |
|  |          |  |  |  > pytest tests/planner.test.ts              |    |  |
|  |          |  |  |  5 passed in 0.41s                           |    |  |
|  |          |  |  |  > ollama ps                                 |    |  |
|  |          |  |  |  qwen3:8b running 6.2GB local                |    |  |
|  |          |  |  +---------------------------------------------+    |  |
|  |          |  |                                                     |  |
|  |          |  |  [Ask the agent...] [Send]   |  |
|  +----------+  +---------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

### E.2 Sidebar (Claude-Style)

**Sections**:
1. **Actions**: New Chat, Chats, Projects, Artifacts, Code, Customize, Design
2. **Products**: Design (expandable)
3. **Starred**: Pinned conversations (e.g., "Lokal Ollama bilan Claude CLI", "Oxiri chatdan fayllarni o'qish")
4. **Recents**: Last 10 conversations with timestamps
5. **User Profile**: Avatar, name, plan status, settings gear

**Behavior**:
- Collapsible (Ctrl+B)
- Context menu on chat items (rename, delete, pin, export)
- Drag-to-reorder starred items
- Search filter for recents

### E.3 Main Workspace Tabs

#### **Tab 1: Chat**
- Message bubbles (user right, assistant left)
- Syntax-highlighted code blocks with copy button
- Collapsible `<|think|>` traces
- File attachments (drag-drop)
- Streaming token-by-token display

#### **Tab 2: Preview** (Your Screenshot 4)
- **Split view**: Code editor (left) + Live output (right)
- **Sandbox execution**: Python/JS code runs in isolated subprocess
  - `matplotlib` plots render as PNG in preview pane
  - `pandas` DataFrames render as interactive tables
  - HTML/JS renders in embedded WebEngine
- **Marker System**:
  - User clicks line gutter -> adds `<|marker|>` token to context
  - AI sees marker and generates `<|fix|>` patch
  - Diff view shows before/after
- **Error overlay**: Red underline + tooltip on exception lines

#### **Tab 3: 2nd Brain** (Your Screenshot 5)
- **Knowledge Graph View**: Interactive force-directed graph (Obsidian-style)
  - Nodes = Wiki notes (concepts, topics, entities, projects)
  - Edges = Wikilinks + semantic similarity
  - Zoom, pan, filter by tag
  - Click node -> open note in side panel
- **Search**: Full-text + semantic (local embeddings)
- **Ingest Panel**: Drag-drop files -> auto-compile to Wiki notes
- **Catalog View**: Table of all Wiki notes with tags, sources, status

#### **Tab 4: Web AI**
- Embedded lightweight browser
- Page content extraction (Defuddle-style clean markdown)
- "Summarize this page" button
- "Add to 2nd Brain" button (extracts to Raw/Sources/)

### E.4 Status Pipeline (Plan -> Read -> Edit -> Test -> Review)

Visual indicator above terminal showing agent's current phase:

```
* Plan  --- * Read  --- * Edit  --- o Test  --- o Review
  green     green     green      gray        gray
```

- **Plan**: Agent is planning approach
- **Read**: Agent is reading files from workspace
- **Edit**: Agent is applying patches/edits
- **Test**: Agent is running tests/validation
- **Review**: Agent is reviewing results, asking for user confirmation

Each phase has a spinner when active, checkmark when complete, X when failed.

### E.5 Terminal Panel

- Real subprocess terminal (PTY)
- Runs user's shell commands + agent-triggered commands
- Color output support
- Command history (Up/Down arrows)
- Auto-scroll with pause on user scroll

### E.6 Input Area

```
+-------------------------------------------------------------+
|  [+]  Ask the agent, or describe a change...        [mic] [clip]|
|       Enter to send - Shift+Enter for newline               |
+-------------------------------------------------------------+
```

- `@` mention to reference 2nd Brain notes
- `#` mention to reference files in workspace
- `/` slash commands (e.g., `/test`, `/explain`, `/refactor`)
- Voice input button (whisper local STT)
- File attachment button


---

## PART F: 2ND BRAIN -- OBSIDIAN LLM WIKI INTEGRATION

### F.1 Architecture (Based on Wanderloots + Kepano)

```
2nd-brain/
├── .obsidian/                    # Obsidian config (optional external sync)
├── Raw/
│   ├── Sources/                  # Unprocessed source material
│   │   ├── engineering/
│   │   ├── data-analytics/
│   │   ├── windows-os/
│   │   ├── linux-os/
│   │   ├── examples-usage/
│   │   └── problem-classification/
│   └── Files/                    # Binary attachments
├── Wiki/
│   ├── Topics/                   # High-level topics
│   ├── Concepts/                 # Defined concepts
│   ├── Entities/                 # Tools, libraries, people
│   ├── Projects/                 # Active projects
│   ├── Logs/                     # Decision logs
│   ├── catalog.jsonl             # Machine-readable index
│   └── index.md                  # Human-readable index
├── Schema/
│   ├── frontmatter-schema.md
│   ├── naming-conventions.md
│   ├── lint-checklist.md
│   ├── source-manifest.jsonl
│   └── command-reference.md
├── _templates/
│   ├── source-note.md
│   ├── concept-note.md
│   ├── topic-note.md
│   ├── entity-note.md
│   ├── project-note.md
│   └── log-note.md
├── .agents/
│   └── skills/
│       ├── llm-wiki-ingest/SKILL.md
│       ├── llm-wiki-query/SKILL.md
│       ├── llm-wiki-lint/SKILL.md
│       └── llm-wiki-maintain/SKILL.md
└── scripts/
    ├── wiki_tool.py              # Deterministic CLI (Python stdlib only)
    ├── install_hooks.sh
    ├── audit_public.py
    └── embed_index.py            # Local embedding index for semantic search
```

### F.2 Domain Knowledge Bases (Your Requirements)

#### **1. Engineering**
```yaml
# Raw/Sources/engineering/
---
Title: "Software Engineering Best Practices"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "engineering"]
---
- SOLID principles with code examples
- Design patterns (GoF) in Python/TypeScript
- System design fundamentals
- CI/CD pipeline design
- Testing strategies (unit, integration, e2e)
```

#### **2. Data Analytics**
```yaml
# Raw/Sources/data-analytics/
---
Title: "Data Analytics Toolkit"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "data-analytics"]
---
- pandas advanced operations
- matplotlib/seaborn/plotly visualization patterns
- Statistical analysis (hypothesis testing, regression)
- SQL optimization for analytics
- ETL pipeline design
```

#### **3. Windows System Operations**
```yaml
# Raw/Sources/windows-os/
---
Title: "Windows System Administration"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "windows", "os"]
---
- PowerShell scripting patterns
- Windows Registry operations
- Service management
- Event log analysis
- WMI queries for system info
```

#### **4. Linux System Operations**
```yaml
# Raw/Sources/linux-os/
---
Title: "Linux System Administration"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "linux", "os"]
---
- Bash scripting best practices
- systemd service management
- File permissions and ACLs
- Network troubleshooting (netstat, ss, tcpdump)
- Package management (apt, yum, pacman)
```

#### **5. How to Use Examples Correctly**
```yaml
# Raw/Sources/examples-usage/
---
Title: "Effective Use of Code Examples"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "examples", "methodology"]
---
- When to copy vs adapt vs rewrite
- Understanding example context and constraints
- Adapting examples to different languages/frameworks
- Testing adapted examples before production use
- Citing example sources
```

#### **6. Problem Classification**
```yaml
# Raw/Sources/problem-classification/
---
Title: "Problem Classification Matrix"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-08-02
Processed: false
tags: ["source", "classification", "methodology"]
---
## Engineer
- System design problems
- Performance optimization
- Architecture decisions
- Technical debt assessment

## Economist
- Cost-benefit analysis
- Resource allocation
- Market trend analysis
- ROI calculations

## Mathematician
- Proof construction
- Algorithm complexity
- Statistical modeling
- Optimization problems

## Data Analyst
- Hypothesis formulation
- Data cleaning strategies
- Visualization selection
- Insight communication
```


### F.3 Agent Skills (Kepano Obsidian Skills Format)

Each skill is a `SKILL.md` file that teaches the LLM how to interact with the 2nd Brain.

#### **Skill: `llm-wiki-ingest`**
```markdown
# LLM Wiki Ingest Skill

## Description
Ingest new source material into the LLM Wiki system.

## When to Use
- User provides a new document, URL, or code snippet
- Auto-ingest from Web AI tab

## Steps
1. Place cleaned Markdown in `Raw/Sources/<domain>/`
2. Run `python scripts/wiki_tool.py source-scan --update`
3. Search `Wiki/catalog.jsonl` for related topics
4. Compile focused Wiki notes in `Wiki/Topics/`, `Wiki/Concepts/`, etc.
5. Link every claim to Raw source in `sources` frontmatter
6. Run `python scripts/wiki_tool.py build && python scripts/wiki_tool.py lint`
7. Update `Wiki/log.md` with ingest summary
```

#### **Skill: `llm-wiki-query`**
```markdown
# LLM Wiki Query Skill

## Description
Query the compiled Wiki before generating answers.

## When to Use
- Before answering technical questions
- When user asks about engineering, data analysis, OS operations
- When uncertain about best practices

## Steps
1. Parse user question for keywords
2. Run `python scripts/wiki_tool.py search-catalog --query "<keywords>"`
3. Open top-3 relevant Wiki notes
4. If insufficient, open linked Raw sources
5. Cite Wiki note + Raw source in answer
6. Prefer compiled Wiki over broad Raw context
```

#### **Skill: `llm-wiki-lint`**
```markdown
# LLM Wiki Lint Skill

## Description
Validate Wiki integrity before commits.

## Steps
1. `python scripts/wiki_tool.py doctor`
2. `python scripts/wiki_tool.py build`
3. `python scripts/wiki_tool.py lint`
4. `python scripts/wiki_tool.py source-lint`
5. `python scripts/audit_public.py`
6. Fix any failures before proceeding
```

#### **Skill: `llm-wiki-maintain`**
```markdown
# LLM Wiki Maintain Skill

## Description
Periodic maintenance of the knowledge base.

## Steps
1. Review `Wiki/Logs/` for outdated entries
2. Check `Schema/source-manifest.jsonl` for uncovered sources
3. Rebuild `Wiki/catalog.jsonl` and indexes
4. Archive obsolete notes to `Wiki/Archive/`
5. Update cross-links between notes
```

### F.4 Deterministic Tooling: `scripts/wiki_tool.py`

Core commands (Python stdlib only):

| Command | Description |
|---|---|
| `doctor` | Health check: folders, Python version, catalog, manifest |
| `build` | Generate `Wiki/catalog.jsonl`, `Wiki/index.md`, per-folder indexes |
| `lint` | Validate frontmatter, allowed tags, source links, source_count |
| `source-scan` | List Raw sources, update manifest |
| `source-scan --update --accept-covered` | Mark covered sources |
| `source-lint` | Validate source frontmatter and coverage |
| `source-delta` | Show uncovered Raw sources |
| `source-coverage` | Coverage report |
| `search-catalog --query "text"` | Full-text search compiled notes |
| `log --title "x" --details "y"` | Append to `Wiki/log.md` |

### F.5 Semantic Search Integration

```python
# scripts/embed_index.py
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class WikiSemanticIndex:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.index = faiss.IndexFlatIP(384)  # Inner product for cosine
        self.doc_map = {}

    def index_wiki(self):
        # Index all compiled Wiki notes
        for note in scan_wiki_notes():
            embedding = self.model.encode(note.content)
            self.index.add(np.array([embedding]))
            self.doc_map[len(self.doc_map)] = note.path

    def search(self, query, k=5):
        embedding = self.model.encode(query)
        scores, indices = self.index.search(np.array([embedding]), k)
        return [self.doc_map[i] for i in indices[0]]
```


---

## PART G: PROJECT STRUCTURE

```
igris-coder/
├── data/
│   ├── raw/                    # Streaming cache (<=2GB hot)
│   ├── processed/              # Tokenized memmap bins
│   └── tokenizer/              # Custom 32k tokenizer files
│
├── model/
│   ├── checkpoints/            # Sharded checkpoints (every 1k steps)
│   ├── finetuned/              # SFT + DPO checkpoints
│   ├── exports/                # GGUF Q4/Q8, ONNX
│   └── tokenizer/              # vocab.json, merges.txt
│
├── scripts/
│   ├── training/
│   │   ├── model.py            # IGRIS transformer implementation
│   │   ├── train.py            # Training loop (CPT + SFT + DPO)
│   │   ├── generate.py         # Inference script
│   │   └── evaluate.py         # Benchmark harness
│   ├── data/
│   │   ├── streamer.py         # Streaming dataset mixer
│   │   ├── tokenizer_train.py  # Custom BPE training
│   │   └── preprocess.py       # Tokenization pipeline
│   ├── finetune/
│   │   ├── sft_data.py         # SFT dataset preparation
│   │   ├── dpo_data.py         # Preference pair generation
│   │   └── tool_data.py        # Synthetic tool-use data
│   └── agent/
│       ├── executor.py         # Python/calc sandbox executor
│       ├── self_correct.py     # Clarify/critique loop
│       └── react_loop.py       # ReAct agent orchestration
│
├── gui/
│   ├── main.py                 # Application entry point
│   ├── sidebar.py              # Claude-style sidebar
│   ├── chat_panel.py           # Chat interface
│   ├── preview_panel.py        # Code + live preview + markers
│   ├── brain_panel.py          # 2nd Brain graph + search
│   ├── web_ai_panel.py         # Embedded browser
│   ├── terminal_panel.py       # PTY terminal
│   ├── status_bar.py           # Plan->Read->Edit->Test->Review
│   └── assets/
│       ├── icons/              # SVG icons
│       └── themes/             # Dark/light CSS
│
├── 2nd-brain/                  # Obsidian LLM Wiki
│   ├── Raw/Sources/            # Domain knowledge bases
│   ├── Wiki/                   # Compiled notes
│   ├── Schema/                 # Rules + manifests
│   ├── _templates/             # Note templates
│   ├── .agents/skills/         # Agent skills (Kepano format)
│   └── scripts/
│       ├── wiki_tool.py
│       ├── embed_index.py
│       └── audit_public.py
│
├── logs/
│   ├── tensorboard/            # Training metrics
│   ├── loss_curves/            # Matplotlib plots
│   └── agent_logs/             # Agent execution logs
│
├── tests/
│   ├── test_model.py
│   ├── test_tokenizer.py
│   ├── test_executor.py
│   └── test_wiki_tool.py
│
├── config.yaml                 # Global configuration
├── requirements.txt
├── verify_setup.py             # Environment verification
└── README.md
```

---

## PART H: EXECUTION ROADMAP

| Phase | Task | Duration | VRAM Peak |
|---|---|---|---|
| **1** | Environment setup + verify CUDA/Flash Attention | 1 day | -- |
| **2** | Streaming data pipeline + tokenizer training | 2 days | -- |
| **3** | Model implementation (400M params) + forward test | 2 days | 2GB |
| **4** | 2nd Brain scaffold (Wanderloots core + domain DBs) | 2 days | -- |
| **5** | GUI skeleton (sidebar, tabs, terminal, status) | 3 days | -- |
| **6** | CPT: 50B tokens streaming pretraining | 2-3 weeks | 6.2GB |
| **7** | SFT: Agent behavior + tool-use + self-correction | 4 days | 6.2GB |
| **8** | DPO: Preference alignment | 2 days | 7GB |
| **9** | Preview sandbox + marker system | 2 days | 3GB |
| **10** | 2nd Brain graph + semantic search integration | 3 days | 2GB |
| **11** | Eval harness + benchmarking | 2 days | 4GB |
| **12** | Quantization (Q4 GGUF) + edge export | 1 day | 2GB |
| **13** | End-to-end integration test | 2 days | 6GB |

**Total Estimated Time**: 5-6 weeks (parallelizable: GUI + 2nd Brain can be built during CPT)

---

## PART I: KEY TECHNOLOGY STACK

| Layer | Technology |
|---|---|
| **Framework** | PyTorch 2.6+ with CUDA 12.8 |
| **Attention** | Flash Attention 2 (fused kernels) |
| **Training** | HuggingFace `transformers`, `datasets`, `accelerate` |
| **Optimization** | `unsloth` for memory-efficient kernels, `bitsandbytes` for QLoRA |
| **Tokenizer** | HuggingFace `tokenizers` (BPE) |
| **Streaming** | `datasets` streaming API + custom interleaved sampler |
| **GUI Framework** | PyQt6 / PySide6 (native, fast, supports WebEngine) |
| **Code Editor** | `QScintilla` or embedded `Monaco Editor` via Qt WebEngine |
| **Graph Viz** | `PyVis` / `networkx` + `QWebEngineView` for 2nd Brain |
| **Terminal** | `PyQt6` QProcess PTY |
| **Sandbox** | `subprocess` + `seccomp` / `firejail` for code execution |
| **Embeddings** | `sentence-transformers` (all-MiniLM-L6-v2) + `faiss-cpu` |
| **Inference Export** | `llama.cpp` (GGUF), `onnxruntime` |
| **Math Engine** | `sympy`, `numexpr` (sandboxed) |

---

## PART J: IMMEDIATE NEXT STEPS

1. **Confirm architecture**: 400M dense vs light MoE? (MoE needs more VRAM during training)
2. **Upload `Temp_SKIll_to_build_IgrisLLM.md`** if you want cross-reference
3. **Choose GUI framework**: PyQt6 (recommended) or Tkinter (simpler but less powerful)
4. **Start implementation**: I can generate Phase 1 (environment + model code) immediately

Which phase should I build into production code first?

---

## PART K: 2ND BRAIN — "QORA OYNA + DOIMIY YUKLANMOQDA" TUZATISH REJASI

> Qo'shilgan: 2026-08-17 · Kodda topilgan ildiz sabablar va checkpointlar bilan.
> Holat: ✅ bajarilgan (08-17 sessiya)

### K.1 Aniqlangan ildiz sabablar (kod tekshiruvi bilan tasdiqlangan)

| ID | Muammo | Ildiz sabab | Joy |
|----|--------|-------------|-----|
| K1 | Graf "qora oyna" bo'lib, faqat hover'da chiziqlar ko'rinadi | Link chiziqlari `#3f3f46` (to'q kulrang) va 0.6 opacity bilan `#09090b` (qora) fonda chizilgan — deyarli qora; hover'da `#f59e0b` (amber) bo'lib ko'rinadi, keyin yana qorayadi | `2nd_brain/frontend/BrainView.tsx:1050-1052` |
| K2 | "Uzoq muddatli yuklanmoqda" — `loading` bayrog'i uzoq tozalanmaydi | `loadGraph` har chaqiruvda `setLoading(true)` qo'yadi va faqat `.finally`da tozalaydi; mount'da `brainGraphShares` hydrate-i `shares`+`maxNodes`ni o'zgartirib effectni qayta ishga tushiradi, React StrictMode (dev) effektni 2 marta chaqiradi → bir-biriga kirgan so'rovlar bekor qilingan `.finally`ni o'tkazib yuboradi, `loading=true` qotib qolishi mumkin | `BrainView.tsx:468-499, 213-229` |
| K3 | Katta Igris_Memory arxivida grafik sekin quriladi (8s timeout xavfi) | `build_graph` har so'rovda diskni to'liq skan + `_semantic_links` O(n²) — natija keshlanmaydi | `2nd_brain/backend/brain_graph.py:851-919, 401-418` |
| K4 | **ASOSIY: butun app qora/bo'sh ekran bo'lib qolardi** | `Igris_Interface/vite.config.ts` da `zustand` aliasi papkaga (ildezga) qaratilgan edi → Vite dev pre-bundle'da `zustand` (CJS `main`) ni tanlab, `create` nomli ESM export statik aniqlanmay: ``The requested module ... does not provide an export named 'create'`` pageerror'i → React app **montaj bo'lmay** qora bo'lib qolardi. Playwright (headless) bilan tasdiqlandi. Yechim: `zustand` alias OLIB TASHLANDI (uni faqat Igris_Interface ichidagi `shared/store.ts` import qiladi — node_modules dan normal ESM bo'lib resolves bo'ladi) | `Igris_Interface/vite.config.ts` |

### K.2 Tuzatish checkpointlari (checkpoint pattern)

| CP | Vazifa | Fayl | Holat |
|----|--------|------|-------|
| CP1 | Rejani plan fayliga qo'shish (shu bo'lim) | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | ✅ |
| CP2 | `loading` to'g'ri tozalanadigan logika: request-seq guard + AbortController; faqat ENG SO'NGGI so'rov `loading=false` qiladi | `BrainView.tsx` | ✅ |
| CP3 | `brainGraph()` ga ixtiyoriy `signal` parametri (abort qilish imkoniyati) | `Igris_Interface/web/backend.ts` | ✅ |
| CP4 | Kontrast fix: link ranglari/opacity, node radius, label rangi — qora fonda doim ko'rinadigan | `BrainView.tsx` | ✅ |
| CP5 | Backend keshi: `build_graph` natijasi fingerprint-digesgga asoslanib keshlanadi (katta arxivda qayta skan yo'q) | `brain_graph.py` | ✅ |
| CP6 | Verifikatsiya: TypeScript (`tsc --noEmit`), backend testlar (`test_brain_graph.py`), `python -B brain_graph.py` CLI | — | ✅ |
| CP7 | Checkpoint holatlarini yangilash (bajarilganlarini ✅) | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | ✅ |
| CP8 | K4 (zustand crash): `vite.config.ts` dan `zustand` aliasni olib tashlash + `.vite` keshni tozalash + dev-server restart + Playwright bilan app montajini/graf renderini tasdiqlash | `Igris_Interface/vite.config.ts` | ✅ |
| CP9 | `dist-web` qayta build + Tauri desktop EXE qayta build (eski frontend bilan ishlamasligi uchun) + backend restart (kesh) | `Igris_Interface`, `src-tauri` | ✅ |

### K.3 Qo'shimcha eslatma

Qoralik — butun app emas, graf maydonining o'zidir: fonda faqat kichik "↻ yangilanmoqda…" toast to'shadi (`BrainView.tsx:1011-1017`), u grafni qoraytirmaydi. Asosiy vizual sabab K1 (kontrast). K2 esa "yuklanmoqda…" badge uzoq turishini keltirib chiqaradi.

---

## PART J KONTSEPTSIYA (eslatma)

What should concept you understan befor start
plain
igris_brick_knowledge/
├── core/
│   ├── brick_system.py          # ~10KB — Semantic primitives (words, functions, types)
│   └── knowledge_system.py      # ~13KB — Grammar & transformation rules
├── resolver/
│   └── constraint_resolver.py   # ~13KB — Graph traversal + healing engine
├── chains/
│   └── chain_system.py          # ~10KB — Modular LoRA adapters + chain healer
├── igris_agent.py               # ~9KB — Main orchestrator
├── config.yaml                  # Configuration
├── requirements.txt             # Dependencies
└── README.md                    # Full documentation
How It Works (No Monologue Thinking)
1. Bricks = Atomic Meaning Units
Python
"teskari" = Brick(
    canonical_id="concept_inverse",
    surface_forms={"uz": ["teskari"], "en": ["inverse"], "code": ["np.linalg.inv"]},
    semantic_vector=[0.8, 0.9, 0.2, ...],  # 128-dim
)
A brick knows its form in every language. It doesn't "think" — it just is.
2. Knowledge = Connection Rules
Python
Rule: [VERB "find"] + [NOUN "inverse"] + [NOUN "matrix"] 
   → code: "np.linalg.inv(matrix)"
Knowledge is how bricks connect, not what they mean.
3. Resolver = Single Graph Traversal
plain
Input: "matritsani teskari top"
  ↓
Bricks: [matrix(accusative), inverse, find]
  ↓
Rule 1 (Grammar): SOV → SVO = [find, inverse, matrix]
  ↓
Rule 2 (Code): VERB+NOUN → function(argument) = np.linalg.inv(matrix)
  ↓
Output: Code
No "hmm, let me think." Just: match pattern → apply rule → done.
4. Healing = Combinatorial Reconstruction
If chain_math is missing:
plain
Available: chain_code (71% similar), chain_analysis (45% similar)
Weights: [0.61, 0.39]
Healed = 0.61 × chain_code + 0.39 × chain_analysis
The agent calculates the missing piece from what it has.
Why This Is "Super Calculative"
Table
Traditional LLM	Your Brick+Knowledge Agent
Memorizes millions of patterns	~4,000 bricks + ~100 rules
"Let me think..." monologue	Single graph traversal (<10ms)
Interpolates from training data	Composes from primitives algebraically
Monolithic, can't fix itself	Modular chains that self-heal
Opaque reasoning	Transparent rule trace
What the Agent Knows (Basics Only)
Table
Primitive Type	Count	Example
Semantic atoms (words/concepts)	~2,000	matrix, inverse, sort, find
Grammar rules	~40	SOV→SVO, case→preposition
Code patterns	~500	for each X → for x in X:
Type constraints	~50	square_matrix → np.linalg.inv
API surfaces	~1,000	Function signatures + docstrings
Total knowledge: ~4,000 nodes. Not millions. Everything else is derived via composition.
Running It
bash
cd igris_brick_knowledge
pip install -r requirements.txt
python igris_agent.py
Expected output:
plain
Query: 'matritsani teskari top' [uz -> code]
Status: ✓
Confidence: 0.902
Chains: ['chain_math']
Output:
np.linalg.inv(matrix)
Download Everything
All files are in: /mnt/agents/output/igris_brick_knowledge/
Next step: Want me to generate the chain training scripts so you can train chain_code, chain_math, chain_uz etc. on your data?

---

## PART L: IGRIS — "USER TALABIGA MOS + TASK O'ZGARISHIGA MOSLASHUVCHAN" TUZATISH REJASI

> Qo'shilgan: 2026-08-17 · Tahlil (kod tekshiruvi) asosida tuzildi.
> Holat: ✅ bajarildi (08-17 sessiya, 19 ta yangi test + regressiya)

### L.1 Aniqlangan "qotib qolgan pattern" ildiz sabablar

| ID | Muammo | Ildiz sabab | Joy |
|----|--------|-------------|-----|
| L1 | Kalit-so'z router task semantikasini emas, so'z ro'yxatini ko'radi | `_classify_need` 10 tarmoqli if/elif; `_is_math_request` harf bo'lsa rad etadi | `igris_agent.py:2590-2612, 2310-2325` |
| L2 | Canned final javoblar user talabini o'rnini bosmaydi | `"I could not generate a response."` (5 joy), `"Bajarildi: N tool..."`, `"Chizdim: ..."`, web-toolsiz matn | `igris_agent.py:1557/1624/1958/1965/2088, 4330, 4545, 1585` |
| L3 | Xulosa majburan qisqa — chuqurlik/til/format talabi e'tiborsiz | `"Summarize ... in 1-2 short sentences"` | `igris_agent.py:4317-4329, 1025-1030`, `executor.py:1012-1036` |
| L4 | resolve() LLM fallback hamma narsani "Python kodga" aylantiradi | Fiksir system prompt | `igris_agent.py:1173-1186` |
| L5 | Yopiq ro'yxatlar ochiq domenni bloklaydi | `CANNED_SCENE_SUBJECTS`, `SCENE_OBJECTS`, `APPS`, `UI_SCENES`, `DATABASE_TECH_HINTS` → ValueError | `igris_agent.py:2632`, `mcp_servers/art_svg.py`, `ui_builder.py`, `igris_agent.py:2918` |
| L6 | Planner/executor fallback kalit-so'z skeleton + placeholder args | `_fallback` (`planner.py:111-154`), `_default_args` (`task.txt`, `# generated by Igris`, `print('ok')`) | `executor.py:1056-1068` |
| L7 | Qadam xatosi → abort + canned summary (re-plan yo'q) | `_execute_step` birinchi xatoda break | `executor.py:933-966` |
| L8 | Quality gate kalit-so'zga tayanadi | `DELIVERABLE_WORDS` | `executor.py:86-90, 1115` |

### L.2 Yechim printsiplari
1. Semantik qatlam boshqaradi, kalit-so'z faqat fallback (LLM yo'q/offline).
2. **Ob-havo va oddiy arifmetika 100% avvalgi holicha qoladi** (o'zgarmaydi).
3. Yolg'on "bajarildi" yo'q — canned matnlar haqiqiy natijaga asoslangan, talabga mos javob bilan almashtiriladi.
4. Task o'zgarsa javob o'zgaradi — bir xil mavzu, turli talab → turli natija.

### L.3 Checkpointlar (checkpoint pattern)

| CP | Vazifa | Fayl | Holat |
|----|--------|------|-------|
| CP-L1 | Part L rejani plan fayliga qo'shish (shu bo'lim) | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | ✅ |
| CP-L2 | Faza A: `core/requirements.py` — `RequirementExtractor` (LLM + `extract_deterministic` fallback; CAG `req:` kesh) | `Igris_brain/core/requirements.py` | ✅ |
| CP-L3 | Faza B: chat — `_build_pipeline`/`_classify_need` extractor intent'idan; talabga mos xulosa (B1); compliance check (B2); canned matnlarni almashtirish (B3); `resolve()` LLM fallback semantikasi (D2) | `igris_agent.py` | ✅ |
| CP-L4 | Faza C: planner req-based plan + `_fallback` req dan; executor re-plan (L7), placeholder args (L6), summalar (L3), quality gate req asosida (L8) | `planner.py`, `executor.py` | ✅ |
| CP-L5 | Faza D: ochiq domen — MCP `not_supported` signal + LLM-generatsiya/confirm yo'li | `mcp_servers/`, `igris_agent.py` | ✅ |
| CP-L6 | Faza E: `test_requirements.py` + `test_adaptive_answers.py`; regressiya (pytest 211, tsc, Playwright e2e) | `Igris_brain/tests` | ✅ |
| CP-L7 | Checkpoint holatlarini yangilash | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | ✅ |

### L.4 Xavflar
- LLM xarajat: +2 chaqiruv/chat — CAG (`req:`, `chk:`) takror savolda qaytarmaydi; compliance faqat shubhali/qisqa natijada.
- Offline: barchasi mavjud deterministik yo'llarga tushadi (holat o'zgarmaydi) + `extract_deterministic`.
- Regressiya: har CP alohida test bilan; 211-test suitası gate.

---

## PART M: PREVIEW QORAYISH TUZATISH + HAQIQIY LIVE BUILD REJASI

> Qo'shilgan: 2026-08-17 · Foydalanuvchi: "5-6 preview ochilsa ekran qorayadi; live build soxta (animatsiya) — haqiqiy qurilish kerak".
> Holat: ✅ bajarildi (08-17 sessiya; Playwright 6-montaj testi: xatosiz, cap=2 bilan navbat, bosqichli qurilish)

### M.1 Ildiz sabablar
| ID | Muammo | Ildiz sabab | Joy |
|----|--------|-------------|-----|
| M1 | 5-6 preview'da ekran qorayadi (GPU/compositor yiqiladi) | Har LIVE BUILD karta autoplay `setPlaying(true)` + har tick'da katta SVG + `[&_svg]:drop-shadow-2xl` filter + per-element CSS transitions; chat kartalari virtualizatsiyasiz montajda | `LiveBuildView.tsx:81,104,151,169,449`; `ChatMessage.tsx:49` |
| M2 | Katta matn preview re-render storm | 2s poll butun ro'yxatni re-render; barcha qatorlar div | `PreviewView.tsx:30,52,106` |
| M3 | Live build SOXTA — tayyor SVG elementlari opacity/scale bilan ochiladi | `buildSvgHtml` indeks bo'yicha `data-build`; fade/pop effekt | `LiveBuildView.tsx:592-615`; `index.css` `.lb-visible/.lb-pop` |

### M.2 WS-A — Qorayish/performans (blokker)
| CP | Tuzatish | Joy | Holat |
|----|----------|-----|-------|
| M-A1 | `useInViewport` (IntersectionObserver): faqat ko'rinadigan karta `playing`; ko'rinmay qolsa pauza | `LiveBuildView.tsx` | ✅ |
| M-A2 | `content-visibility:auto` + `contain` karta/preview kontaynerlarda | `ChatMessage.tsx`, `PreviewView.tsx`, `index.css` | ✅ |
| M-A3 | `drop-shadow-2xl` olib tashlash (GPU filter) | `LiveBuildView.tsx` | ✅ |
| M-A4 | Reveal klasslarni ref+classList orqali (tick re-render kamaytirish) | `LiveBuildView.tsx` | ✅ |
| M-A5 | Global animator cap (max 2) + `visibilitychange` pauza | `LiveBuildView.tsx`, `LiveBuildHTML.tsx` | ✅ |
| M-A6 | Recording singleton + mirror-canvas faqat yozuvda | `LiveBuildView.tsx` | ✅ |
| M-A7 | Matn preview: satr limiti + hash-dedupe poll + ko'rinish guard | `PreviewView.tsx` | ✅ |
| M-A8 | Watchdog: tick qotishi/GPU xatoda avto-pauza | `LiveBuildView.tsx` | ✅ |

### M.3 WS-B — Haqiqiy live build (rassom jarayoni: poydevor → taxminiy joylash → takomillashtirish → rang → tekshiruv)
| CP | Bosqich | Nima | Holat |
|----|---------|------|-------|
| M-B1 | Har element bosqichga ajratish — frontend universal (bbox/hajm/tur bo'yicha foundation/rough/refine; barcha SVG uchun ishlaydi, backend metadata shart emas) | `LiveBuildView.tsx` | ✅ |
| M-B2 | Frontend stage-fidelity renderer (kontur→detail→rang) | `LiveBuildView.tsx`, `index.css` | ✅ |
| M-B3 | Tekshiruv (Verify) checklisti — o'lcham/qamrov/hajm/kontrast ✓/✗ | `LiveBuildView.tsx` | ✅ |
| M-B4 | "Soxta" effektlarni olib tashlash (`lb-pop`, per-element fade) | `index.css` | ✅ |
| M-B5 | Bosqich indikatorlari + checkpoint status (orqaga/qayta bosqich) | `LiveBuildView.tsx` | ✅ |

### M.4 Verifikatsiya
- Qo'lda: 5-6 karta + preview — qorayish yo'q; haqiqiy bosqichlar ko'rinadi.
- Playwright e2e: 6 ta `LiveBuildView`, crash yo'q, timers cheklangan.
- `tsc --noEmit`, `npm run build`, backend testlar (art_svg stage).

---

## PART N: BRAIN "OFFLINE" OLIB QOLISHI — SABAB VA TUZATISH (yuklamalarni bo'laklash)

> Qo'shilgan: 2026-08-17 · Foydalanuvchi: "brain offline bo'lib qolyabdi — yuklamalarni kichikroq bo'laklarga ajratib bajarsin".
> Holat: ✅ bajarildi (08-17 sessiya; status 4ms, health 79ms, watchdog ishlamoqda; qo'shimcha: model fallback + "tozalash")

### N.1 Ildiz sabablar (kod tekshiruvi bilan)
| ID | Muammo | Ildiz sabab | Joy |
|----|--------|-------------|-----|
| N1 | Frontend "offline" noto'g'ri ko'rsatadi | `ping()` `/api/status` ga 2.5s timeout bilan — status `agent.status()` da `llm_available()` Ollama'ni tekshiradi, band bo'lganda bloklanadi → ping muvaffaqiyatsiz → "offline" | `Igris_Interface/web/backend.ts:617-624`, `server.py:751`, `igris_agent.py:1114` |
| N2 | `/api/status` takroriy poll'da og'ir | Har poll agent.status() + Ollama + memory.status() qayta hisoblaydi (TTL kesh yo'q) | `server.py:751-782` |
| N3 | Boshlanishdagi og'ir sync yuklama | `MemoryBridge.__init__` butun korpusni (`load_documents` → os.walk + barcha fayl read + BM25 build) **sync** bajaradi — birinchi `/api/status` (get_agent) sekinlashadi | `memory_bridge.py:56-63`, `Igris_Memory/memory/retrieval.py:505-531` |
| N4 | Graf/chunk yuklamalari to'liq fayl o'qiydi | `brain_graph._scan_chat_history`/`_scan_jsonl_dir` `readlines()` bilan to'liq faylni o'qiydi (katta JSONL/chat_history) | `brain_graph.py:216-219, 283-285` |
| N5 | Watchdog to'xtatilgan — auto-recovery yo'q | `logs/watchdog.stop` fayli bor | `Igris_brain/logs/watchdog.stop` |

### N.2 Tuzatish checkpointlari
| CP | Vazifa | Fayl | Holat |
|----|--------|------|-------|
| N-C1 | Part N rejani qo'shish (shu bo'lim) | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | 🔄 |
| N-C2 | `ping()` → yengil `/api/health` (LLM/agent tegmagan) — online-detection aniq | `Igris_Interface/web/backend.ts` | ✅ |
| N-C3 | `/api/status` TTL kesh (2s) — takroriy poll'lar Ollama/agent qayta hisoblamaydi | `Igris_brain/server.py` | ✅ |
| N-C4 | `MemoryBridge` korpus yuklanishini background thread'ga (init/first status tez); `recall` yuklanish tugashini kutadi (max 3s) | `Igris_brain/memory_bridge.py` | ✅ |
| N-C5 | `brain_graph` tail-chunk o'qish (`_read_tail_lines`) — chat_history/JSONL to'liq emas, oxirgi qism | `2nd_brain/backend/brain_graph.py` | ✅ |
| N-C6 | Watchdog qayta ishga tushirish (auto-recovery) + `/api/health` liveness (allaqachon afzal) | `run.bat`/`watchdog.py` | ✅ |
| N-C7 | Verifikatsiya: status/health tez, ping→health, brain_graph CLI, pytest, watchdog ishlaydi | — | ✅ |
| N-C8 | Checkpoint holatlarini yangilash | `Temp_EXAMPle_IGRIS_CODER_Plan.md` | ✅ |
| N-C9 | **Ollama model fallback**: model GPU'ga sig'masa (OOM/`cudaMalloc failed`) avtomatik kichikroq modelga o'tish (`qwen3:8b` 500 berdi → `qwen2.5-coder:1.5b` ishladi) | `Igris_brain/llm/ollama_client.py` | ✅ |
| N-C10 | Fallback modellarda `think` parametrini o'chirish (qwen2.5-coder `think` qo'llamaydi → 500) | `Igris_brain/llm/ollama_client.py` | ✅ |
| N-C11 | Bo'sh-javob fallback xabari: tilga mos (uz/en) + real sabab (OOM/Ollama) bilan — "rephrase" shabloni emas | `Igris_brain/igris_agent.py` | ✅ |
| N-C12 | **Tozalash**: `POST /api/chat/clear` (chat tarixi + CAG kesh) + frontend "🧹 tozalash" tugma | `Igris_brain/server.py`, `Igris_Interface/web/backend.ts`, `shared/store.ts`, `AgentConsole.tsx` | ✅ |
| N-C13 | Verifikatsiya: chat ishladi (fallback), 2-chaqiruv 7.8s, clear ishladi, tsc OK | — | ✅ |

---

## PART O: CREATIVE VISUAL TASKLAR — ANIQLIK + CRASHSIZ QURILISH

> Qo'shilgan: 2026-08-17 · Foydalanuvchi: "creative visual tasklar aniqligi-chi? crash bermay aniq va talabga mos qurilishi".
> Holat: ✅ bajarildi (08-17 sessiya; ma'lum subject 111ms deterministik real chizma, noma'lum 3.8s halol javob; janrlar: child/bw/fantasy/anime/realistic/flat/cartoon)

### O.1 Ildiz sabablar
| ID | Muammo | Ildiz sabab |
|----|--------|-------------|
| O1 | Model xom/soxta SVG yozadi ("Chizdim: `x.svg` — rasm tayyor" lekin rasm yo'q) | Kuchsiz fallback model (qwen2.5-coder:1.5b) chizishni bajarmaydi, yolg'on tugallash yozadi |
| O2 | Noma'lum subject'da 172s junk SVG fragment javob bo'lib qaytdi | `_extract_svg` to'liq `<svg>` topa olmaydi, lekin junk matn javob sifatida o'tadi |
| O3 | Ma'lum subject'da ham modelga bog'liq (talab buzilishi mumkin) | Model o'zi tool tanlashi kerak — kuchsiz model to'g'ri chaqirmaydi |

### O.2 Tuzatish checkpointlari
| CP | Vazifa | Fayl | Holat |
|----|--------|------|-------|
| O-C1 | **Deterministik chizish** ma'lum (canned) subject uchun: subject/rang talabdan aniqlanadi, `art__draw_scene_svg` to'g'ridan-to'g'ri chaqiriladi (modelga bog'liq emas, talab aniq) | `igris_agent.py` `_try_deterministic_scene` + `_chat_with_tools` | ✅ |
| O-C2 | `_draw_color_from_request` — uz/en rang aniqlash | `igris_agent.py` | ✅ |
| O-C3 | Soxta "Chizdim ... rasm tayyor" rad etish (`_fake_draw_claim`: haqiqiy faqat `<svg>`/`art__draw`) — `_save_svg_from_text`, `_retry_generate` | `igris_agent.py` | ✅ |
| O-C4 | Junk SVG fragment (>1500 belgi, `<path>`/`stroke=`) javob sifatida o'tmasligi | `igris_agent.py` `_save_svg_from_text` | ✅ |
| O-C5 | Noma'lum subject'da qimmat retry o'rniga tez halol o'zbekcha javob (ma'lum narsalar ro'yxati bilan) | `igris_agent.py` `_retry_generate` | ✅ |
| O-C6 | Verifikatsiya: `uy sariq` → deterministik `art__draw_scene_svg` (uy, sariq, img real); `kosa` → halol fallback, junk yo'q | — | ✅ |
| O-C7 | **Talabdan kelib chiqib real chizma**: `art_svg` ga `style` (flat/cartoon/realistic) + `size` (standard/icon/avatar/card/poster/banner/'WxH') — proporsional shkalalash, distorsion yo'q; `_try_deterministic_scene` style+size uzatadi | `mcp_servers/art_svg.py`, `art_server.py`, `igris_agent.py` | ✅ |
| O-C8 | **Tezlik**: draw so'rovida LLM requirement-extractor va LLM compliance o'tkazib yuboriladi (rasm deterministik) → ma'lum subject 111ms; noma'lum subject 3.8s halol javob | `igris_agent.py`, `core/requirements.py` | ✅ |
| O-C9 | **Janr/uslublar kengaytmasi**: `child` (bola chizgandek), `bw` (oq-qora/grayscale), `fantasy` (sehrli yorug'lik), `anime` — `STYLE_CSS` filter+kontur orqali real qo'llanadi; `_draw_style_from_request` uz/en kalitlar; `draw_custom_svg`/`_tools_hint` yo'riqnomasi; fayl nomi millisekund bilan yagona | `mcp_servers/art_svg.py`, `art_server.py`, `igris_agent.py` | ✅ |
