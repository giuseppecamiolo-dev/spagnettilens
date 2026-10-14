import argparse
import subprocess
import sys
import re
import shutil
import os
import tempfile
import shlex
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
        editor_cmd = shlex.split(editor)
        if not editor_cmd:
            editor_cmd = ['nano']
        subprocess.run(editor_cmd + [tf_path])

        with open(tf_path, 'r') as tf:
            prompt = tf.read()
        os.remove(tf_path)
    return prompt

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

    prompt = edit_prompt_manually(prompt)

    print(f"[*] Analisi del file {path.name} (Azione: {action.upper()}) tramite Foundry...")
    
    # TODO: Fix script hanging when executing powershell via subprocess
    # Use tempfile to write prompt to disk and pass filepath to powershell
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False, encoding='utf-8') as tf:
        tf.write(prompt)
        temp_file_path = tf.name

    try:
        # We use cmd.exe /c type <file> | foundry run <model> to pass standard input cleanly,
        # but the prompt mentions not using the `$input |` pipeline to pass STDIN in powershell.
        # "Instead, execute the command directly to rely on standard STDIN inheritance."
        # This implies we can construct the powershell command using cmd.exe redirection
        # `cmd.exe /c "foundry run <model> < \`<temp_file>\`"`
        # Convert WSL path to Windows path for PowerShell if necessary, but PowerShell in WSL
        # can usually handle WSL paths via wslpath, or we can rely on standard file handling if we
        # use wslpath command. Actually, if we just use python subprocess stdin, it works seamlessly.

        # We will translate the WSL path to a Windows path to be perfectly safe, or just use python to open the file
        # and pass it as stdin to Popen. The prompt says: "Use tempfile to write prompt to disk and pass filepath to powershell".

        # Convert the temp file path to a Windows path using wslpath if available
        if shutil.which("wslpath"):
            try:
                wslpath_process = subprocess.run(["wslpath", "-w", temp_file_path], capture_output=True, text=True, check=True)
                win_temp_file_path = wslpath_process.stdout.strip()
            except subprocess.CalledProcessError:
                win_temp_file_path = temp_file_path
        else:
            win_temp_file_path = temp_file_path

        ps_command = f"cmd.exe /c 'foundry run {model} < \"{win_temp_file_path}\"'"

        # Prefer pwsh.exe (PowerShell Core) if available, otherwise powershell.exe
        ps_executable = "pwsh.exe" if shutil.which("pwsh.exe") else "powershell.exe"

        # Esecuzione trasparente di PowerShell da WSL
        process = subprocess.Popen(
            [ps_executable, "-Command", ps_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        
        # Attendi la risposta (niente input via stdin qui perché lo fa nativamente powershell leggendo il file)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"\n[!] Errore da {ps_executable}: {stderr}", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*50 + "\n")
        print(stdout.strip())
        print("\n" + "="*50 + "\n")
        
    except FileNotFoundError:
        print(f"\n[!] Impossibile trovare l'eseguibile. Assicurati di eseguire lo script in WSL su Windows o che PowerShell sia nel PATH.", file=sys.stderr)
    except Exception as e:
        print(f"\n[!] Errore imprevisto: {e}", file=sys.stderr)
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegacyLens-AI: AI-powered Legacy Analyzer via PowerShell interop")
    parser.add_argument("file", help="Percorso del file legacy da analizzare")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello da usare in Foundry")
    
    args = parser.parse_args()
    
    analyze_legacy_code(args.file, args.action, args.model)
