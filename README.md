# spaghettilens 🔍 (`v0.3.0`)

[![SpaghettiLens CI](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml/badge.svg)](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Architecture](https://img.shields.io/badge/architecture-Neuro--Symbolic%20%2B%20WSL2--Interop-purple.svg)

**AI-Powered Legacy Code Analyzer & Neuro-Symbolic Refactoring Orchestrator via WSL-PowerShell Interoperability**

SpaghettiLens-AI is a CLI tool and static analysis engine designed for Senior Backend Engineers tasked with modernizing legacy ERP codebases (Perl, PHP procedural). It leverages local Large Language Models (LLMs) — alongside optional cloud OpenAI-compatible SSE endpoints — to automatically document, audit, and refactor aging scripts without exposing proprietary company code to unauthorized third-party APIs.

By exploiting the seamless interoperability between Windows 11 WSL2 and the native PowerShell environment, this tool runs the Python orchestration and static SQL/AST dependency extraction layer in a Unix environment while delegating heavy AI inference to the Windows host or cloud runtime. It supports multiple inference backends through a unified provider layer (`core/providers.py`):
*   **Foundry** (`foundry`): Local model runner passing prompts securely via `wslpath` temporary file redirection to avoid PowerShell `stdin` pipe deadlocks.
*   **npurun** (`npu`): NPU-first local LLM runtime for Snapdragon X-series Windows-on-ARM laptops for highly efficient on-device AI (`qwen3-4b-instruct-2507`).
*   **Ollama** (`ollama` / `ollama-http`): Local LLM runner executing natively within the WSL environment via CLI or REST streaming.
*   **Cloud SSE Endpoints** (`meta`, `baseten`, `fireworks`, `modal`, `openai`): Optional OpenAI-compatible streaming backends for hybrid or cloud-scale refactoring workflows.

---

## 🚀 Key Features

*   **Zero Data Leakage (Local-First):** Code analysis can run 100% locally on your machine using Foundry, NPU, or Ollama — ideal for enterprise environments with strict NDA and data privacy policies.
*   **Neuro-Symbolic Static Dependency & Invariant Graph (`core/schema_graph.py`):** Before invoking the LLM, SpaghettiLens deterministically extracts:
    *   Embedded SQL queries (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) and referenced relational tables mapped against `.sql` DDL schemas.
    *   HTTP/CGI entry points (`$_GET`, `$_POST`, `CGI->param`).
    *   **Security & Runtime Risks:** Unparameterized SQL variable interpolation (SQL Injection), hardcoded database credentials, reflected XSS, and deprecated PHP 5 `mysql_*` calls.
    *   **Financial & Ledger Invariants:** Detects IEEE 754 floating-point accumulation on monetary columns (`$total_amount += $ref->{'amount'}`) and flags the need for fixed-point integer cents or SQL `DECIMAL(10, 2)` aggregation.
*   **Automated Documentation:** Generates comprehensive PHPDoc or POD comments for undocumented spaghetti code without altering execution behavior.
*   **Security Auditing:** Flags deprecated functions (e.g., `mysql_*`) and critical vulnerabilities (e.g., SQL Injections, missing parameter binding).
*   **Migration Scaffolding:** Proposes modernized architectural patterns (e.g., migrating Perl CGI to Perl/Dancer2 or FastAPI, and procedural PHP to PDO/OOP).
*   **Cross-Environment Execution:** Python logic runs in Linux (WSL2), while hardware-accelerated LLM execution runs natively on the Windows Host via transparent PowerShell interop.
*   **Interactive Prompt Engineering:** Inspect and manually edit the generated prompt (including the injected JSON dependency graph and SQL schema) in your preferred terminal editor (`nano`/`vim`) prior to inference, or bypass it via `--no-interactive` for automated agentic pipelines.

---

## 🏗️ Architecture & Tech Stack

*   **Core:** Python 3.11+ (CLI, Static SQL/AST Regex Graph Extractor, Subprocess & SSE Streaming Orchestration)
*   **Host Environment:** Windows 11 + WSL2 (Debian/Ubuntu)
*   **AI Engine:** Local LLMs via Foundry, `npurun` (`qwen3-4b-instruct-2507`), or Ollama (`llama3`, `qwen2.5`, `mistral`), plus Cloud SSE (`meta` / `muse-spark`, `baseten`, `fireworks`, `modal`)
*   **Target Languages:** Perl (`CGI`, `DBI`, `DB_File`, `GTK`), PHP (Legacy Procedural `ext/mysql`), and Relational SQL Schemas (`.sql`).

```text
spaghettilens-ai/
├── .github/workflows/ci.yml  # Automated pytest CI pipeline
├── core/
│   ├── __init__.py
│   ├── providers.py          # Unified LLM provider abstraction (Foundry, NPU, Ollama, Cloud SSE)
│   └── schema_graph.py       # Static SQL/AST dependency & financial invariant extractor
├── fixtures/
│   └── schema.sql            # Relational DDL & seed data for S-GeO invoices & course bookings
├── tests/                    # 20+ unit tests covering providers, static graph, and prompt builders
├── spaghettiCode.pl          # Legacy Perl CGI/DBI ERP invoice generator fixture
├── spaghettiCode.php         # Legacy PHP 5 procedural course enrollment fixture
├── spaghettilens.py          # Main unified CLI orchestrator
├── spaghettilensNPU.py       # Dedicated NPU PowerShell interop script
└── spaghettilensOllam.py     # Dedicated native WSL Ollama script
```

## 📜 Scripts Overview

The repository provides a unified orchestrator alongside standalone backend scripts:

**`spaghettilens.py` (Unified Orchestrator & Foundry Default)**
* Supports all providers via `--provider {foundry,npu,ollama,meta,baseten,fireworks,modal,openai}`.
* Automatically builds and injects the static LegacyDependencyGraph JSON and optional `--schema` SQL definitions into the prompt.
* Includes `--dump-graph` for zero-LLM deterministic static analysis and `--no-interactive` for automated workflows.

**`spaghettilensNPU.py`**
* Uses `npurun` as the dedicated backend (`qwen3-4b-instruct-2507` default).
* Leverages the Snapdragon X-series NPU for accelerated, low-power inference.
* Passes the prompt dynamically via PowerShell `[Console]::In.ReadToEnd()` into a trailing CLI argument required by the `npurun` architecture.

**`spaghettilensOllam.py`**
* Uses `ollama` natively within the WSL environment, eliminating the need for PowerShell interop.
* Passes the prompt securely via standard input (`stdin`) piping.

## 📦 Installation & Setup
Ensure you have Windows 11 with WSL2 enabled and at least one local LLM engine (`foundry`, `npurun`, or `ollama`) installed and accessible in your PATH.

Clone this repository into your WSL environment:

```bash
git clone https://github.com/giuseppecamiolo-dev/spagnettilens.git
cd spagnettilens
```

(Optional) Create and activate a Python virtual environment for running the test suite:

```bash
python3 -m venv ~/.venvs/spaghettilens
source ~/.venvs/spaghettilens/bin/activate
pip install pytest
```

## 💻 Usage Examples

### 1. Deterministic Static Dependency & Invariant Graph (`--dump-graph`)
Extract SQL queries, referenced tables, CGI/HTTP inputs, SQL injection vectors, and ledger floating-point risks as JSON without invoking an LLM:

```bash
python3 spaghettilens.py spaghettiCode.pl --schema fixtures/schema.sql --dump-graph
```

### 2. Security Audit & Refactoring via Local Hardware Backends
**Foundry (Default WSL-to-PowerShell Bridge):**

```bash
python3 spaghettilens.py spaghettiCode.pl --action security --model llama3 --schema fixtures/schema.sql
```

**Snapdragon NPU (`npurun`):**

```bash
python3 spaghettilens.py spaghettiCode.php --provider npu --model qwen3-4b-instruct-2507 --action refactor
# Or via the dedicated NPU script:
python3 spaghettilensNPU.py spaghettiCode.php --action refactor
```

**Native WSL Ollama:**

```bash
python3 spaghettilens.py spaghettiCode.pl --provider ollama --model llama3 --action document --no-interactive
# Or via the dedicated Ollama script:
python3 spaghettilensOllam.py spaghettiCode.pl --action document
```

### 3. Cloud SSE Inference (Meta / Baseten / Modal / Fireworks)

```bash
export META_API_KEY="your-api-key"
python3 spaghettilens.py spaghettiCode.pl \
  --provider meta \
  --model muse-spark \
  --action refactor \
  --schema fixtures/schema.sql \
  --no-interactive
```

## 🧪 Running the Test Suite
Run the full unit test suite (20 tests covering prompt generation, WSL/PowerShell mocked bridges, SSE streaming, and Perl/PHP static graph extraction):

```bash
pytest -v
```
