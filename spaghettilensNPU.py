import argparse
import subprocess
import sys
import re
import shutil
from pathlib import Path

DEFAULT_MODEL = "qwen3-4b-instruct-2507"

def get_prompt_for_action(action: str, code: str, extension: str) -> str:
    language = "Perl" if extension == ".pl" else "PHP"
    
    system_persona = f"You are a Senior Backend Engineer specializing in legacy {language} modernization."
    
    prompts = {
        "document": f"{system_persona} Add comprehensive PHPDoc or POD comments to the following code. Do not change the code execution.\n\nCode:\n{code}",
        "security": f"{system_persona} Analyze this legacy {language} code for security vulnerabilities (e.g., SQL Injection) and deprecated functions. List issues and fixes.\n\nCode:\n{code}",
        "refactor": f"{system_persona} Refactor this legacy {language} code into a modern, secure format. Separate business logic from presentation.\n\nCode:\n{code}"
    }
    
    return prompts.get(action, prompts["security"])

def analyze_legacy_code(file_path: str, action: str, model: str) -> None:
    path = Path(file_path)
    if not path.is_file():
        print(f"Errore: Il file {file_path} non esiste.", file=sys.stderr)
        sys.exit(1)

    # Validate model name to prevent command injection
    if not re.match(r'^[\w.-]+$', model):
        print(f"Errore: Nome modello non valido: {model}", file=sys.stderr)
        sys.exit(1)

    # Handle legacy encodings gracefully
    code = path.read_text(encoding="utf-8", errors="replace")
    prompt = get_prompt_for_action(action, code, path.suffix)

    print(f"[*] Analisi del file {path.name} (Azione: {action.upper()}) tramite npurun...")
    
    # npurun requires the prompt as a trailing argument, not via standard input.
    # So we tell PowerShell to read from stdin, store it in a variable, and pass it as an argument.
    ps_command = f'$prompt = [Console]::In.ReadToEnd().Trim(); npurun run {model} "$prompt"'
    
    # Prefer pwsh.exe (PowerShell Core) if available, otherwise powershell.exe
    ps_executable = "pwsh.exe" if shutil.which("pwsh.exe") else "powershell.exe"

    try:
        # Esecuzione trasparente di PowerShell da WSL
        process = subprocess.Popen(
            [ps_executable, "-Command", ps_command],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        
        # Invia il prompt a PowerShell e attendi la risposta
        stdout, stderr = process.communicate(input=prompt)
        
        if process.returncode != 0:
            print(f"\n[!] Errore da {ps_executable}: {stderr}", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*50 + "\n")
        print(stdout.strip())
        print("\n" + "="*50 + "\n")
        
    except FileNotFoundError:
        print(f"\n[!] Impossibile trovare {ps_executable}. Assicurati di eseguire lo script in WSL su Windows o che PowerShell sia nel PATH.", file=sys.stderr)
    except Exception as e:
        print(f"\n[!] Errore imprevisto: {e}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegacyLens-AI: AI-powered Legacy Analyzer via PowerShell interop")
    parser.add_argument("file", help="Percorso del file legacy da analizzare")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello da usare in npurun")
    
    args = parser.parse_args()
    
    analyze_legacy_code(args.file, args.action, args.model)
