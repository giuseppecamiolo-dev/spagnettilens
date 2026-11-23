# 🍝🔍 SpaghettiLens-AI (`v0.6.0`)

**Neuro-Symbolic Legacy Code Analyzer & Hierarchical Multi-Agent Strangler-Fig Refactoring Engine (Perl / PHP $\rightarrow$ Python / FastAPI)**  
*Featuring 3-Level `smolagents` CodeAgent Orchestration, Out-of-Window Call-Inventory Loop Guards, Local Snapdragon NPU Acceleration & Reproducible Trace Diffing CLI*

[![CI](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml/badge.svg)](https://github.com/giuseppecamiolo-dev/spagnettilens/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
[![smolagents PR #3115](https://img.shields.io/badge/smolagents-PR%20%233115%20(3--Tier%20Hierarchy)-orange.svg)](https://github.com/huggingface/smolagents/pull/3115)
[![smolagents PR #3110](https://img.shields.io/badge/smolagents-PR%20%233110%20(Truncated%20JSON%20Guard)-orange.svg)](https://github.com/huggingface/smolagents/pull/3110)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🎯 Overview

Modernizing legacy enterprise systems—especially 15-to-20-year-old **Perl CGI/DBI** scripts and procedural **PHP (`ext/mysql`)** monoliths—is notoriously error-prone. Naive "paste-and-refactor" LLM prompts frequently hallucinate database columns, miss implicit global inputs (`$_GET`, `$_POST`, `CGI::param`), or break critical financial ledger invariants (such as IEEE 754 floating-point drift on monetary totals).

**SpaghettiLens-AI (`v0.6.0`)** solves this using a **Neuro-Symbolic Strangler-Fig Architecture**:

1. **Deterministic Static Extraction (`core/schema_graph.py`)**: Parses legacy Perl/PHP source files and optional SQL DDL schemas (`--schema`) *before* invoking the LLM. Extracts embedded SQL queries, maps them to table definitions, identifies untrusted HTTP/CGI entry points, and flags security/financial invariants (`LEDGER_INVARIANT`).
2. **Unified Multi-Provider Inference (`core/providers.py`)**: Streams analysis or refactored code through **Zero-Data-Leakage Local Hardware** (`npu` via `npurun`, `foundry`, `ollama`, `ollama-http`) or **OpenAI-Compatible Cloud SSE APIs** (`meta`, `baseten`, `fireworks`, `modal`, `openai`).
3. **Deterministic Verification Sandbox (`core/sandbox_runner.py`)**: Validates generated Python/FastAPI code via AST parsing (`ast.parse`), bytecode compilation, SQL parameterization checks, financial `Decimal` enforcement, and ephemeral SQLite schema execution.
4. **Autonomous Self-Healing Agent (`core/strangler_agent.py`)**: Orchestrates multi-turn refactoring (`--agent`) that automatically feeds deterministic sandbox failures back into the LLM until all syntax, security, and financial invariants pass.
5. **3-Level `smolagents` Hierarchy & Out-of-Window `CallLedger` (`core/smol_hierarchy.py`, `core/call_ledger.py`)**: Implements a multi-tier `LedgerCodeAgent` hierarchy (`--smolagents`) with custom NPU-optimized Jinja2 prompt templates, sliding-window call-inventory digests, pre-execution duplicate-call interception, and AST-level `<code>...</code>` sanitization so compact 4B local NPU models execute deterministic multi-agent pipelines within a 4,096-token ceiling.
6. **Automated Same-Input Trace Diffing (`core/trace_diff.py`, `cli/bench.py`)**: Runs identical legacy fixtures across a frontier baseline and a local/edge candidate, comparing both per-step topologies and flattened AST call sequences (Levenshtein distance) alongside the 4-gate sandbox oracle.

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
|       2. Self-Healing Strangler Agent, CallLedger & LLM Providers       |
|       (core/strangler_agent.py, core/call_ledger.py, providers.py)      |
|  • Local Zero-Leakage: Snapdragon NPU (npurun), Foundry, Ollama         |
|  • Cloud SSE APIs: Meta, Baseten, Fireworks, Modal, OpenAI              |
|  • Out-of-window AST CallLedger prevents duplicate NPU tool loops       |
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
```

### 2. 3-Level `smolagents` CodeAgent Hierarchy (`--smolagents`)

Powered by `core/smol_hierarchy.py` and `core/call_ledger.py`, serving as a production edge-NPU testbed and reference architecture for upstream `huggingface/smolagents` contributions:
- **PR #3115 — Multi-Level Managed Agent Hierarchy**: Enables 3-tier orchestration (Supervisor $\rightarrow$ L1 Team Leads $\rightarrow$ L2 Specialists) where intermediate CodeAgent leads coordinate specialized sub-agents and deterministic verification tools.
- **PR #3110 — Truncated JSON Blob Detection (fix #1783)**: Distinguishes missing JSON blobs from truncated outputs (`{` without closing `}` when hitting max_completion_tokens / NPU context ceilings), preventing infinite retry loops on compact local models.

```text
                      +-----------------------------------+
                      |   Level 0: Root Orchestrator      |
                      |     spaghettilens_supervisor      |
                      |     + Scoped AST CallLedger       |
                      +-----------------+-----------------+
                                        |
                   +--------------------+--------------------+
                   |                                         |
                   v                                         v
   +-------------------------------+         +-------------------------------+
   |      Level 1: Team Lead       |         |      Level 1: Team Lead       |
   |        discovery_lead         |         |      modernization_lead       |
   |     + Scoped AST CallLedger   |         |     + Scoped AST CallLedger   |
   +---------------+---------------+         +---------------+---------------+
                   |                                         |
         +---------+---------+                               v
         |                   |               +-------------------------------+
         v                   v               |   Level 2: Specialist Agent   |
+-----------------+ +-----------------+      |    strangler_sandbox_agent    |
| Level 2: Agent  | | Level 2: Agent  |      |    + Scoped AST CallLedger    |
| dependency_     | | security_       |      | Tools:                        |
| graph_agent     | | invariant_agent |      | • execute_strangler_          |
| Tool:           | | Tool:           |      |   refactoring                 |
| • extract_      | | • audit_        |      | • run_standalone_sandbox_check|
|   static_       | |   security_and_ |      +-------------------------------+
|   dependency_   | |   ledger_       |
|   graph         | |   invariants    |
+-----------------+ +-----------------+
```

---

## 📦 Installation

Requires **Python 3.11+** and `smolagents`:

```bash
pip install smolagents pytest
```

---

## 🚀 Quick Start & Usage

### 1. 3-Level `smolagents` Hierarchical Mode (`--smolagents`)

Run the strict, multi-agent orchestrator using local Snapdragon NPU hardware acceleration (with per-tier out-of-window CallLedger digests and duplicate-call guards):

```bash
python3 spaghettilens.py fixtures/spaghettiCode.php \
  --schema fixtures/schema.sql \
  --provider npu \
  --model qwen3-4b-instruct-2507 \
  --smolagents \
  --max-retries 3
```

### 2. Automated Same-Input Trace Diffing CLI (`cli/bench.py`)

Compare a frontier baseline against a local NPU/edge candidate on identical fixtures—scoring both AST call-inventory sequences and 4-gate sandbox verdicts:

```bash
python3 -m cli.bench \
  --fixture fixtures/legacy_invoice_batch.pl \
  --schema fixtures/schema.sql \
  --baseline openai/gpt-4o \
  --candidate npu/qwen3-4b-instruct-2507 \
  --diff \
  --out reports/invoice_trace_diff.md
```

### 3. Autonomous Self-Healing Agent Mode (`--agent`)

Run the standard self-healing loop on legacy code using a local NPU or Ollama:

```bash
python3 spaghettilens.py fixtures/spaghettiCode.pl \
  --schema fixtures/schema.sql \
  --provider ollama \
  --model llama3 \
  --agent \
  --max-retries 3
```

### 4. Inspect the Deterministic Dependency Graph (`--dump-graph`)

Extract the JSON dependency and invariant graph without invoking any LLM:

```bash
python3 spaghettilens.py fixtures/spaghettiCode.pl --schema fixtures/schema.sql --dump-graph
```

### 5. Interactive CLI Modes (`security`, `refactor`, `document`)

```bash
python3 spaghettilens.py fixtures/spaghettiCode.php \
  --action security \
  --schema fixtures/schema.sql \
  --provider foundry \
  --model llama3
```

### 6. Reproducible Offline Benchmarks (4B NPU vs. Frontier Cloud)

Run the offline deterministic verification simulator (5 configurations x 2 fixtures x 10 runs):

```bash
python3 benchmarks/run_eval.py --mode dry-run --runs 10 --seed 42
```

---

## 🧪 Automated Test Suite & CI

Run the full offline unit test suite (**62 tests** covering local/cloud providers, static schema graph extraction, sandbox verification, self-healing agent loops, out-of-window CallLedger deduplication, AST trace diffing, and the 3-level smolagents hierarchy):

```bash
python3 -m pytest -v
```

---

## 📂 Repository Structure

```text
spaghettilens-ai/
├── .github/workflows/ci.yml       # GitHub Actions CI pipeline
├── benchmarks/                    # 4-Gate verification & tool-trace suite
│   ├── run_eval.py                # Offline simulator & baseline telemetry
│   └── run_live_cloud_trace.py    # Live Gemini AST call trace extractor
├── cli/
│   └── bench.py                   # Same-input trace diffing CLI (`python -m cli.bench`)
├── core/
│   ├── __init__.py
│   ├── call_ledger.py             # Out-of-window AST CallLedger & duplicate-call guard
│   ├── providers.py               # Unified multi-provider streaming abstraction
│   ├── sandbox_runner.py          # Deterministic AST, SQLi, Decimal & SQLite verifier
│   ├── schema_graph.py            # Static SQL/AST & financial invariant extractor
│   ├── smol_hierarchy.py          # 3-level LedgerCodeAgent hierarchy & NPU adapter
│   ├── strangler_agent.py         # Autonomous self-healing refactoring orchestrator
│   └── trace_diff.py              # AST call-sequence diffing & 4-gate oracle classifier
├── fixtures/
│   ├── legacy_invoice_batch.pl    # Multi-table Perl DBI batch invoice benchmark fixture
│   ├── schema.sql                 # Relational DDL test schema (invoices & enrollments)
│   ├── spaghettiCode.pl           # Legacy Perl CGI/DBI invoice fixture
│   └── spaghettiCode.php          # Legacy PHP course enrollment fixture
├── tests/
│   ├── test_call_ledger.py        # Unit tests for CallLedger normalization & loop guard
│   ├── test_providers.py          # Unit tests for local & cloud SSE providers
│   ├── test_schema_graph.py       # Unit tests for static Perl/PHP/SQL graph engine
│   ├── test_smol_hierarchy.py     # Unit tests for 3-level smolagents hierarchy & sanitizer
│   ├── test_spaghettilens.py      # Unit tests for main CLI orchestrator
│   ├── test_spaghettilensNPU.py   # Unit tests for NPU wrapper
│   ├── test_spaghettilensOllam.py # Unit tests for Ollama wrapper
│   ├── test_strangler_agent.py    # Unit tests for SandboxRunner & self-healing loop
│   └── test_trace_diff.py         # Unit tests for AST trace diffing & oracle verdicts
├── spaghettilens.py               # Primary unified CLI entry point
├── spaghettilensNPU.py            # Dedicated Snapdragon NPU CLI module
└── spaghettilensOllam.py          # Dedicated Ollama HTTP CLI module
```

---

## 🧪 Case Study: The 4B Edge NPU as a Multi-Agent Stress Test

Most multi-agent frameworks are developed on 70B+ cloud models, whose large parameter capacity and wide context windows can sometimes compensate for orchestration flaws—working around ambiguous agent descriptions, verbose system prompts, or missing tool schemas.

In **SpaghettiLens-AI (`v0.6.0`)**, we use a compact **4B parameter model (`qwen3-4b-instruct-2507`)** on a local **Snapdragon NPU** (configured with a **4,096-token sliding context limit**) as a reproducible "wind tunnel" to stress-test a **3-tier `smolagents` `CodeAgent` hierarchy** (`L0 Supervisor` $\rightarrow$ `L1 Team Leads` $\rightarrow$ `L2 Specialists`).

### Failure Modes Exposed on 4B Edge Hardware (and How We Solved Them)

1. **Multi-Tier Blindness (`smolagents` PR #3115 / Issue #1061):**
  * *The Problem:* In a 3-level hierarchy, the root `L0 Supervisor` could see the `L1 Team Leads` (`discovery_lead`, `modernization_lead`), but had zero visibility into the `L2 Specialists` nested beneath them (`dependency_graph_agent`, `security_invariant_agent`, `strangler_sandbox_agent`).
  * *The Fix:* We patched capability propagation upstream so parent agents recursively append a summary of nested sub-agents to their descriptions, giving the root supervisor deterministic routing visibility across all 3 tiers.

2. **Sliding-Window Amnesia & Duplicate Tool Loops (`core/call_ledger.py`):**
  * *The Problem:* Under a 4,096-token sliding window, early `ActionStep` code blocks are evicted as multi-step runs progress—causing compact 4B models to forget completed lookups and re-invoke identical static tool calls.
  * *The Fix:* Each `LedgerCodeAgent` maintains an out-of-window `CallLedger` keyed by normalized `(tool_name, args)` AST fingerprints, pinning a `<= 420`-character `[Executed Calls Ledger]` digest beneath the system prompt and short-circuiting redundant `OK` static calls prior to `python_executor` execution (while leaving dynamic loop variables unblocked).

3. **Verbose Prompt Hallucinations (Custom Code-First Jinja2 Templates):**
  * *The Problem:* Default `managed_agent` system prompts ask sub-agents to write multi-section prose reports (`### 1. Task outcome (short version)...`). Under a 4,096-token ceiling, this verbosity caused the 4B model to hallucinate theoretical summaries in Step 1 instead of emitting executable `<code>...</code>` blocks.
  * *The Fix:* We engineered compact, code-first Jinja2 prompt overrides and strict per-tier constraints that force every agent to invoke its assigned tool/sub-agent in Step 1 and pass the output directly to `final_answer`.

4. **Silent Token-Ceiling Loops (`smolagents` PR #3110 / Issue #1783):**
  * *The Problem:* When extracting large static AST/SQL dependency graphs, outputs occasionally hit `max_completion_tokens` mid-JSON (`{"file_name": ...`). Because the closing `}` was missing, `parse_json_blob` raised a misleading "output does not contain any JSON blob" error, tricking the agent into regenerating the exact same oversized response in an infinite loop.
  * *The Fix:* We added explicit truncated JSON detection so the parser immediately surfaces a token-limit truncation error, allowing the agent to compact its output on retry.

5. **AST-Level `<code>` Sanitization & Deterministic Sandboxing:**
  * *The Problem:* Small models occasionally leak markdown fences or trailing prose inside Python execution blocks.
  * *The Fix:* Strict AST-level `<code>` sanitization (`ast.parse`) paired with `SandboxRunner` (SQLite + FastAPI verification) guarantees that every inter-agent handoff and refactored endpoint is syntactically and functionally verified in a single iteration.

### Why This Scales Up to Frontier Models

An orchestration harness that achieves **100% single-pass determinism (`iterations_used: 1`)** on a 4B local NPU transfers effortlessly to 70B+ cloud models—delivering lower Time-To-First-Token (TTFT), minimal KV-cache footprint, and zero wasted retry tokens.

### 📚 Theoretical Alignment & Related Work: Deterministic "Expert Blocks"

Our neuro-symbolic architecture aligns with recent research on **Expert Block Frameworks for Small LLMs** (Naphade et al., arXiv:2509.15561).

Naphade et al. demonstrate that locally-run small LLMs (14B–32B) can match 100B+ frontier models (within ~0.9% of GPT-4) when paired with a **Trajectory Context Summarizer (TCS)**—a deterministic block that transforms raw, noisy trajectories into structured context before LLM reasoning.

**SpaghettiLens-AI (`v0.6.0`)** extends this exact principle to multi-tier software modernization on 4B edge NPUs:
- **Deterministic Context Summarizers (`L2 Discovery Specialists` + `CallLedger`)**: Instead of feeding raw, noisy legacy monoliths into a 4,096-token context window, `core/schema_graph.py` compresses raw Perl/PHP ASTs and SQL DDL schemas into a structured JSON dependency and invariant graph, while `core/call_ledger.py` preserves a bounded AST call digest across sliding-window truncations.
- **Deterministic Verification Blocks (`L2 Sandbox Specialist`)**: `core/sandbox_runner.py` replaces open-ended LLM self-critique with hard symbolic verification (`ast.parse`, parameterized SQL enforcement, and `decimal.Decimal` ledger checks), enabling a 4B parameter model (`qwen3-4b-instruct-2507`) to achieve deterministic, single-pass refactoring (`iterations_used: 1`) on consumer NPU hardware.

---

## 📜 License

Distributed under the MIT License. Created by Giuseppe Camiolo.
