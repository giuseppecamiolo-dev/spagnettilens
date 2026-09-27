# SpaghettiLens-AI 🔍

**AI-Powered Legacy Code Analyzer via WSL-PowerShell Interoperability**

SpaghettiLens-AI is a CLI tool designed for Senior Backend Engineers tasked with modernizing legacy codebases (Perl, PHP procedural). It leverages local Large Language Models (LLMs) to automatically document, secure, and refactor aging scripts without sending proprietary company code to third-party cloud APIs (like OpenAI).

By exploiting the seamless interoperability between Windows 11 WSL2 and the native PowerShell environment, this tool runs the Python orchestration layer in a Unix environment while delegating the heavy AI inference to the Windows host. It supports multiple inference backends:
*   **Foundry** (Local model runner) passing data securely via `stdin` piping.
*   **npurun** (NPU-first local LLM runtime for Snapdragon X-series Windows-on-ARM laptops) for highly efficient on-device AI.

## 🚀 Key Features

*   **Zero Data Leakage:** All code analysis happens 100% locally on your machine. Perfect for enterprise environments with strict NDA and data privacy policies.
*   **Automated Documentation:** Generates comprehensive PHPDoc or POD comments for undocumented spaghetti code.
*   **Security Auditing:** Flags deprecated functions (e.g., `mysql_*`) and critical vulnerabilities (e.g., SQL Injections, missing parameter binding).
*   **Migration Scaffolding:** Proposes modernized architectural patterns (e.g., migrating Perl CGI to Perl/Dancer, or procedural PHP to PDO/OOP).
*   **Cross-Environment Execution:** Python logic runs in Linux (WSL), LLM execution runs natively on Windows Host via transparent PowerShell piping.
*   **Hardware Acceleration:** First-class support for Windows-on-ARM NPUs via `npurun`, saving battery and CPU cycles.

## 🛠️ Architecture & Tech Stack

*   **Core:** Python 3 (CLI, Subprocess Orchestration)
*   **Host Environment:** Windows 11 + WSL2 (Debian/Ubuntu)
*   **AI Engine:** Local LLMs via Foundry or npurun (e.g., Qwen2.5, Llama 3, Mistral)
*   **Target Languages:** Perl (CGI, DB_File, GTK), PHP (Legacy Procedural).

## 📜 Scripts Overview

The repository provides two distinct Python scripts depending on your chosen AI backend:

**`spaghettilens.py`**
*   Uses Foundry as the backend.
*   Passes the source code to the LLM via standard input (`stdin`) piping.
*   Ideal for general-purpose CPU/GPU setups.

**`spaghettilensNPU.py`**
*   Uses npurun as the backend.
*   Leverages the Snapdragon X-series NPU for accelerated, low-power inference.
*   Passes the source code dynamically as a PowerShell trailing argument, which is required by the npurun CLI architecture.

## 📦 Installation & Setup

1. Ensure you have Windows 11 with WSL2 enabled and a local LLM engine (Foundry or npurun) accessible via PowerShell.
2. Clone this repository into your WSL environment:
   ```bash
   git clone [https://github.com/giuseppecamiolo-dev/spaghettilens.git](https://github.com/giuseppecamiolo-dev/spaghettilens.git)
   cd spaghettilens``
