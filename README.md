# 🍝🔍 SpaghettiLens-AI (`v0.5.0`)

**Neuro-Symbolic Legacy Code Analyzer & Hierarchical Multi-Agent Strangler-Fig Refactoring Engine (Perl / PHP $\rightarrow$ Python / FastAPI)**  
*Featuring 3-Level `smolagents` CodeAgent Orchestration, Local Snapdragon NPU Hardware Acceleration & Multi-Provider Cloud SSE Inference*

[![CI](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml/badge.svg)](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
[![smolagents PR #3115](https://img.shields.io/badge/smolagents-PR%20%233115%20(3--Tier%20Hierarchy)-orange.svg)](https://github.com/huggingface/smolagents/pull/3115)
[![smolagents PR #3110](https://img.shields.io/badge/smolagents-PR%20%233110%20(Truncated%20JSON%20Guard)-orange.svg)](https://github.com/huggingface/smolagents/pull/3110)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🎯 Overview

Modernizing legacy enterprise systems—especially 15-to-20-year-old **Perl CGI/DBI** scripts and procedural **PHP (`ext/mysql`)** monoliths—is notoriously error-prone. Naive "paste-and-refactor" LLM prompts frequently hallucinate database columns, miss implicit global inputs (`$_GET`, `$_POST`, `CGI::param`), or break critical financial ledger invariants (such as IEEE 754 floating-point drift on monetary totals).

**SpaghettiLens-AI (`v0.5.0`)** solves this using a **Neuro-Symbolic Strangler-Fig Architecture**:

1. **Deterministic Static Extraction (`core/schema_graph.py`)**: Parses legacy Perl/PHP source files and optional SQL DDL schemas (`--schema`) *before* invoking the LLM. Extracts embedded SQL queries, maps them to table definitions, identifies untrusted HTTP/CGI entry points, and flags security/financial invariants (`LEDGER_INVARIANT`).
2. **Unified Multi-Provider Inference (`core/providers.py`)**: Streams analysis or refactored code through **Zero-Data-Leakage Local Hardware** (`npu` via `npurun`, `foundry`, `ollama`) or **OpenAI-Compatible Cloud SSE APIs** (`meta`, `baseten`, `fireworks`, `modal`, `openai`).
3. **Deterministic Verification Sandbox (`core/sandbox_runner.py`)**: Validates generated Python/FastAPI code via AST parsing (`ast.parse`), bytecode compilation, SQL parameterization checks, financial `Decimal` enforcement, and ephemeral SQLite schema execution.
4. **Autonomous Self-Healing Agent (`core/strangler_agent.py`)**: Orchestrates multi-turn refactoring (`--agent`) that automatically feeds deterministic sandbox failures back into the LLM until all syntax, security, and financial invariants pass.
5. **3-Level `smolagents` Hierarchical Orchestration (`core/smol_hierarchy.py`)**: Implements a multi-tier `CodeAgent` hierarchy (`--smolagents`) with custom NPU-optimized Jinja2 prompt templates, sliding-window context management, truncated-generation guards, and AST-level `<code>...</code>` sanitization so compact 4B local NPU models execute deterministic multi-agent pipelines without syntax loops or tool-shadowing failures.
---

## 🏗️ System Architecture

### 1. Core Neuro-Symbolic Pipeline
```text
+-------------------------------------------------------------------------+
|                        Legacy Source & DDL Input                        |
|        spaghettiCode.pl (Perl CGI) / spaghettiCode.php + schema.sql     |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|              1. Static Dependency & Invariant Graph Engine              |
|                          (core/schema_graph.py)                         |
|  • Extracts embedded SQL queries & maps target relational tables        |
|  • Traces untrusted HTTP/CGI inputs ($_GET, $_POST, CGI->param)         |
|  • Detects SQL Injection vectors & IEEE 754 float ledger invariants     |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|             2. Self-Healing Strangler Agent & LLM Providers             |
|              (core/strangler_agent.py & core/providers.py)              |
|  • Local Zero-Leakage: Snapdragon NPU (npurun), Foundry, Ollama         |
|  • Cloud SSE APIs: Meta, Baseten, Fireworks, Modal, OpenAI              |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                 3. Deterministic Verification Sandbox                   |
|                         (core/sandbox_runner.py)                        |
|  • AST Syntax & Bytecode Compilation Check                              |
|  • Zero-SQLi Parameterization & Credential Environment Enforcement      |
|  • LEDGER_INVARIANT (`decimal.Decimal`) Verification + Ephemeral SQLite |
|  * If checks fail -> Feeds structured error report back to Agent        |
+-------------------------------------------------------------------------+
### 2. 3-Level `smolagents` CodeAgent Hierarchy (`--smolagents`)
Powered by `core/smol_hierarchy.py`, serving as a production edge-NPU testbed and reference architecture for upstream [`huggingface/smolagents`](https://github.com/huggingface/smolagents) contributions:

* **[PR #3115 — Multi-Level Managed Agent Hierarchy](https://github.com/huggingface/smolagents/pull/3115)**: Enables 3-tier orchestration (`Supervisor` $\rightarrow$ `L1 Team Leads` $\rightarrow$ `L2 Specialists`) where intermediate `CodeAgent` leads coordinate specialized sub-agents and deterministic verification tools.
* **[PR #3110 — Truncated JSON Blob Detection (`fix #1783`)](https://github.com/huggingface/smolagents/pull/3110)**: Distinguishes missing JSON blobs from truncated outputs (`{` without closing `}` when hitting `max_completion_tokens` / NPU context ceilings), preventing infinite retry loops on compact local models.

```text
                      +-----------------------------------+
                      |   Level 0: Root Orchestrator      |
                      |     spaghettilens_supervisor      |
                      +-----------------+-----------------+
                                        |
                   +--------------------+--------------------+
                   |                                         |
                   v                                         v
   +-------------------------------+         +-------------------------------+
   |      Level 1: Team Lead       |         |      Level 1: Team Lead       |
   |        discovery_lead         |         |      modernization_lead       |
   +---------------+---------------+         +---------------+---------------+
                   |                                         |
         +---------+---------+                               v
         |                   |               +-------------------------------+
         v                   v               |   Level 2: Specialist Agent   |
+-----------------+ +-----------------+      |    strangler_sandbox_agent    |
| Level 2: Agent  | | Level 2: Agent  |      | Tools:                        |
| dependency_     | | security_       |      | • execute_strangler_          |
| graph_agent     | | invariant_agent |      |   refactoring                 |
| Tool:           | | Tool:           |      | • run_standalone_sandbox_check|
| • extract_      | | • audit_        |      +-------------------------------+
|   static_       | |   security_and_ |
|   dependency_   | |   ledger_       |
|   graph         | |   invariants    |
+-----------------+ +-----------------+
🚀 Quick Start & Usage
1. 3-Level smolagents Hierarchical Mode (--smolagents)
Run the strict, multi-agent orchestrator using local Snapdragon NPU hardware acceleration (optimized to eliminate hallucinations on 4B models):

Bash
python3 spaghettilens.py spaghettiCode.php \
  --schema fixtures/schema.sql \
  --provider npu \
  --model qwen3-4b-instruct-2507 \
  --smolagents \
  --max-retries 3
2. Autonomous Self-Healing Agent Mode (--agent)
Run the standard self-healing loop on legacy code using a local NPU:

Bash
python3 spaghettilens.py spaghettiCode.php \
  --schema fixtures/schema.sql \
  --provider npu \
  --model qwen3-4b-instruct-2507 \
  --agent \
  --max-retries 3
Or with local Ollama (llama3) or Cloud SSE Providers (meta, baseten, fireworks, modal, openai):

Bash
python3 spaghettilens.py spaghettiCode.pl \
  --schema fixtures/schema.sql \
  --provider ollama \
  --model llama3 \
  --agent \
  --max-retries 3
3. Inspect the Deterministic Dependency Graph (--dump-graph)
Extract the JSON dependency and invariant graph without invoking any LLM:

Bash
python3 spaghettilens.py spaghettiCode.pl --schema fixtures/schema.sql --dump-graph
4. Interactive CLI Modes (security, refactor, document)
Bash
python3 spaghettilens.py spaghettiCode.php \
  --action security \
  --schema fixtures/schema.sql \
  --provider foundry \
  --model llama3
🧪 Automated Test Suite & CI
Run the full offline unit test suite (36 tests covering local/cloud providers, static schema graph extraction, sandbox verification, self-healing agent loops, and the 3-level smolagents hierarchy)[cite: 7]:

Bash
python3 -m pytest -v
📂 Repository Structure
Plaintext
spaghettilens-ai/
├── .github/workflows/ci.yml      # GitHub Actions CI pipeline
├── core/
│   ├── __init__.py
│   ├── providers.py              # Unified multi-provider streaming abstraction
│   ├── schema_graph.py           # Static SQL/AST & financial invariant extractor
│   ├── sandbox_runner.py         # Deterministic AST, SQLi, Decimal & SQLite verifier
│   ├── strangler_agent.py        # Autonomous self-healing refactoring orchestrator
│   └── smol_hierarchy.py         # 3-level smolagents CodeAgent hierarchy & NPU adapter
├── fixtures/
│   └── schema.sql                # Relational DDL test schema (invoices & enrollments)
├── tests/
│   ├── test_providers.py         # Unit tests for local & cloud SSE providers
│   ├── test_schema_graph.py      # Unit tests for static Perl/PHP/SQL graph engine
│   ├── test_strangler_agent.py   # Unit tests for SandboxRunner & self-healing loop
│   ├── test_smol_hierarchy.py    # Unit tests for 3-level smolagents hierarchy & sanitizer
│   ├── test_spaghettilens.py     # Unit tests for main CLI orchestrator
│   ├── test_spaghettilensNPU.py  # Unit tests for NPU wrapper
│   └── test_spaghettilensOllam.py# Unit tests for Ollama wrapper
├── spaghettilens.py              # Primary unified CLI entry point
├── spaghettilensNPU.py           # Dedicated Snapdragon NPU CLI module
├── spaghettilensOllam.py         # Dedicated Ollama HTTP CLI module
├── spaghettiCode.pl              # Legacy Perl CGI/DBI invoice fixture
└── spaghettiCode.php             # Legacy PHP course enrollment fixture
📜 License
Distributed under the MIT License. Created by Giuseppe Camiolo.
