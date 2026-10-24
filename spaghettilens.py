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

DEFAULT_MODEL = "llama3"


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
) -> None:
    path = Path(file_path)
    if not path.is_file():
        print(f"Errore: Il file {file_path} non esiste.", file=sys.stderr)
        sys.exit(1)

    if not re.match(r"^[\w.:/-]+$", model):
        print(f"Errore: Nome modello non valido: {model}", file=sys.stderr)
        sys.exit(1)

    code = path.read_text(encoding="utf-8", errors="replace")

    schema_sql: Optional[str] = None
    if schema_path:
        s_path = Path(schema_path)
        if s_path.is_file():
            schema_sql = s_path.read_text(encoding="utf-8", errors="replace")

    # Build deterministic static dependency & invariant graph
    dep_graph = build_dependency_graph(code, str(path), schema_sql=schema_sql)

    if dump_graph_only:
        print(dep_graph.to_json())
        return

    prompt = get_prompt_for_action(action, code, path.suffix)
    prompt += f"\n\nStatic Dependency & Invariant Graph (JSON):\n{dep_graph.to_json()}"

    if schema_sql:
        prompt += f"\n\nRelational Database Schema (SQL):\n{schema_sql}"

    if interactive:
        prompt = edit_prompt_manually(prompt)

    print(
        f"[*] Analisi del file {path.name} (Azione: {action.upper()}) "
        f"tramite {provider_name.upper()} ({model})..."
    )

    try:
        provider = create_provider(provider_name, model)
        print("\n" + "=" * 50 + "\n")
        for token in provider.stream(prompt):
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n" + "=" * 50 + "\n")
    except FileNotFoundError:
        print(
            "\n[!] Impossibile trovare l'eseguibile. Assicurati di eseguire lo script in WSL su Windows o che il binario sia nel PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Errore durante l'inferenza: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SpaghettiLens-AI: AI-powered Legacy Code Analyzer & Refactoring Orchestrator"
    )
    parser.add_argument("file", help="Percorso del file legacy da analizzare")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello da usare (es. llama3, muse-spark)")
    parser.add_argument(
        "--provider",
        choices=["foundry", "npu", "ollama", "meta", "baseten", "fireworks", "modal", "openai"],
        default="foundry",
        help="Backend di inferenza (default: foundry)",
    )
    parser.add_argument("--schema", default=None, help="Percorso opzionale al file schema SQL (.sql)")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Salta la conferma interattiva dell'editor (utile per pipeline agentiche)",
    )
    parser.add_argument("--dump-graph", action="store_true", help="Estrae e stampa solo il grafo statico JSON senza invocare l'LLM")

    args = parser.parse_args()

    analyze_legacy_code(
        args.file,
        args.action,
        args.model,
        provider_name=args.provider,
        interactive=not args.no_interactive,
        schema_path=args.schema,
    )
