import argparse
import subprocess
import sys
import re
import shutil
import os
import tempfile
from pathlib import Path

DEFAULT_MODEL = "llama3"

def get_prompt_for_action(action: str, code: str, extension: str) -> str:
    language = "Perl" if extension == ".pl" else "PHP"

    system_persona = f"You are a Senior Backend Engineer specializing in legacy {language} modernization."

    prompts = {
        "document": f"{system_persona} Add comprehensive PHPDoc or POD comments to the following code. Do not change the code execution.\n\nCode:\n{code}",
        "security": f"{system_persona} Analyze this legacy {language} code for security vulnerabilities (e.g., SQL Injection) and deprecated functions. List issues and fixes.\n\nCode:\n{code}",
        "refactor": f"{system_persona} Refactor this legacy {language} code into a modern, secure format. Separate business logic from presentation.\n\nCode:\n{code}"
    }

    return prompts.get(action, prompts["security"])

def edit_prompt_manually(prompt: str) -> str:
    print("\n--- Current Prompt ---")
    print(prompt)
    print("----------------------\n")
    try:
        choice = input("Do you want to manually modify the prompt before proceeding? (y/N): ").strip().lower()
    except EOFError:
        choice = 'n'

    if choice == 'y':
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
            tf.write(prompt)
            tf_path = tf.name

        editor = os.environ.get('EDITOR', 'nano')
        os.system(f"{editor} {tf_path}")

        with open(tf_path, 'r') as tf:
            prompt = tf.read()
        os.remove(tf_path)
    return prompt

def analyze_legacy_code(file_path: str, action: str, model: str) -> None:
    path = Path(file_path)
    if not path.is_file():
        print(f"Errore: Il file {file_path} non esiste.", file=sys.stderr)
        sys.exit(1)


    # Handle legacy encodings gracefully
    code = path.read_text(encoding="utf-8", errors="replace")
    prompt = get_prompt_for_action(action, code, path.suffix)

    prompt = edit_prompt_manually(prompt)

    print(f"[*] Analisi del file {path.name} (Azione: {action.upper()}) tramite Ollama (su WSL)...")

    try:
        # Esecuzione diretta di ollama su WSL
        process = subprocess.Popen(
            ["ollama", "run", model],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

        # Invia il prompt a ollama e attendi la risposta
        stdout, stderr = process.communicate(input=prompt)

        if process.returncode != 0:
            print(f"\n[!] Errore da ollama: {stderr}", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*50 + "\n")
        print(stdout.strip())
        print("\n" + "="*50 + "\n")

    except FileNotFoundError:
        print(f"\n[!] Impossibile trovare 'ollama'. Assicurati che sia installato in WSL.", file=sys.stderr)
    except Exception as e:
        print(f"\n[!] Errore imprevisto: {e}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegacyLens-AI: AI-powered Legacy Analyzer via Ollama (WSL)")
    parser.add_argument("file", help="Percorso del file legacy da analizzare")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello da usare in Ollama")

    args = parser.parse_args()

    analyze_legacy_code(args.file, args.action, args.model)
