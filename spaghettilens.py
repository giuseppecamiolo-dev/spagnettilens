import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from core.providers import create_provider
from core.schema_graph import build_dependency_graph
from core.strangler_agent import StranglerAgent
# smolagents integration
from core.smol_hierarchy import build_spaghettilens_smol_hierarchy

DEFAULT_MODEL = "qwen2.5-coder-0.5b"


def get_prompt_for_action(action: str, code: str, extension: str) -> str:
    language = "Perl" if extension == ".pl" else "PHP"

    system_persona = f"You are a Senior Backend Engineer specializing in legacy {language} modernization."

    prompts = {
        "document": f"{system_persona} Add comprehensive PHPDoc or POD comments to the following code. Do not change the code execution.\n\nCode:\n{code}",
        "security": f"{system_persona} Analyze this legacy {language} code for security vulnerabilities (e.g., SQL Injection) and deprecated functions. List issues and fixes.\n\nCode:\n{code}",
        "refactor": f"{system_persona} Refactor this legacy {language} code into a modern, secure format. Separate business logic from presentation.\n\nCode:\n{code}",
    }

    return prompts.get(action, prompts["security"])


def edit_prompt_manually(prompt: str) -> str:
    print("\n--- Current Prompt ---")
    print(prompt)
    print("----------------------\n")
    try:
        choice = input("Do you want to manually modify the prompt before proceeding? (y/N): ").strip().lower()
    except EOFError:
        choice = "n"

    if choice == "y":
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tf:
            tf.write(prompt)
            tf_path = tf.name

        editor = os.environ.get("EDITOR", "nano")
        editor_cmd = shlex.split(editor)
        if not editor_cmd:
            editor_cmd = ["nano"]
        subprocess.run(editor_cmd + [tf_path])

        with open(tf_path, "r", encoding="utf-8", errors="replace") as tf:
            prompt = tf.read()
        os.remove(tf_path)
    return prompt


def analyze_legacy_code(
    file_path: str,
    action: str,
    model: str,
    provider_name: str = "foundry",
    interactive: bool = True,
    schema_path: Optional[str] = None,
    dump_graph_only: bool = False,
    agent_mode: bool = False,
    smolagents_mode: bool = False,
    max_retries: int = 3,
) -> None:
    path = Path(file_path)
    if not path.is_file() and (Path("fixtures") / file_path).is_file():
        path = Path("fixtures") / file_path
    if not path.is_file():
        print(f"Error: File {file_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    if not re.match(r"^[\w.:/-]+$", model):
        print(f"Error: Invalid model name: {model}", file=sys.stderr)
        sys.exit(1)

    code = path.read_text(encoding="utf-8", errors="replace")

    schema_sql: Optional[str] = None
    if schema_path:
        s_path = Path(schema_path)
        if s_path.is_file():
            schema_sql = s_path.read_text(encoding="utf-8", errors="replace")

    dep_graph = build_dependency_graph(code, str(path), schema_sql=schema_sql)

    if dump_graph_only:
        print(dep_graph.to_json())
        return

    try:
        provider = create_provider(provider_name, model)

        if smolagents_mode:
            print(
                f"[*] Starting Multi-Level smolagents Hierarchy (Supervisor -> L1 -> L2) on {path.name} "
                f"via {provider_name.upper()} ({model}) [max_retries={max_retries}]..."
            )
            supervisor = build_spaghettilens_smol_hierarchy(
                provider=provider,
                model_name=model,
                max_retries=max_retries,
                default_file_path=file_path,
                default_schema_path=schema_path or "",
            )
            task = (
                f"Modernize legacy file source: '{file_path}' (SQL schema file: '{schema_path or ''}'). "
                "1. First, call `discovery_lead` to get the audit and dependency graph. "
                "2. Second, call `modernization_lead` to execute the Strangler refactoring and verify it in the sandbox. "
                "Do not loop back to discovery."
            )
            result = supervisor.run(task)
            print("\n" + "=" * 50 + "\n")
            print(result)
            print("\n" + "=" * 50 + "\n")
            return

        if agent_mode:
            print(
                f"[*] Starting StranglerAgent on {path.name} via {provider_name.upper()} ({model}) "
                f"[max_retries={max_retries}]..."
            )
            agent = StranglerAgent(provider=provider, max_retries=max_retries)
            report = agent.run(code, str(path), schema_sql=schema_sql)

            for attempt in report.attempts:
                status = "PASSED" if attempt.sandbox_result.passed else "FAILED"
                print(f"  -> Iteration {attempt.iteration}: Sandbox {status}")
                for err in attempt.sandbox_result.errors:
                    print(f"     [!] {err}")

            print("\n" + "=" * 50 + "\n")
            print(report.final_code)
            print("\n" + "=" * 50 + "\n")

            if not report.success:
                print(
                    f"[!] The agent failed to pass all sandbox checks after {report.iterations_used} attempts.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        prompt = get_prompt_for_action(action, code, path.suffix)
        prompt += f"\n\nStatic Dependency & Invariant Graph (JSON):\n{dep_graph.to_json()}"

        if schema_sql:
            prompt += f"\n\nRelational Database Schema (SQL):\n{schema_sql}"

        if interactive:
            prompt = edit_prompt_manually(prompt)

        print(
            f"[*] Analyzing file {path.name} (Action: {action.upper()}) "
            f"via {provider_name.upper()} ({model})..."
        )

        print("\n" + "=" * 50 + "\n")
        for token in provider.stream(prompt):
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n" + "=" * 50 + "\n")
    except FileNotFoundError:
        print(
            "\n[!] Executable not found. Ensure the script is running in WSL on Windows or that the binary is in PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Error during inference: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SpaghettiLens-AI: AI-powered Legacy Code Analyzer & Refactoring Orchestrator"
    )
    parser.add_argument("file", help="Path to the legacy file to analyze")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use (e.g., llama3, muse-spark)")
    parser.add_argument(
        "--provider",
        choices=["foundry", "npu", "ollama", "meta", "baseten", "fireworks", "modal", "openai"],
        default="foundry",
        help="Inference backend (default: foundry)",
    )
    parser.add_argument("--schema", default=None, help="Optional path to the SQL schema file (.sql)")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip interactive editor confirmation (useful for agentic pipelines)",
    )
    parser.add_argument(
        "--dump-graph",
        action="store_true",
        help="Extract and print only the static JSON dependency graph without invoking the LLM",
    )
    parser.add_argument(
        "--smolagents",
        action="store_true",
        help="Enable the 3-level CodeAgent hierarchy (huggingface/smolagents PR #3115)",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Enable the StranglerAgent loop with deterministic sandbox verification and self-healing",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of self-healing attempts in --agent mode (default: 3)",
    )

    args = parser.parse_args()

    analyze_legacy_code(
        args.file,
        args.action,
        args.model,
        provider_name=args.provider,
        interactive=not args.no_interactive,
        schema_path=args.schema,
        dump_graph_only=args.dump_graph,
        smolagents_mode=args.smolagents,
        agent_mode=args.agent,
        max_retries=args.max_retries,
    )
