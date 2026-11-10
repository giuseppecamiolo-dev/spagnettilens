import argparse
import subprocess
import sys
import re
import shutil
import os
import tempfile
import shlex
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
    if not path.is_file() and (Path("fixtures") / file_path).is_file():
        path = Path("fixtures") / file_path
    if not path.is_file():
        print(f"Error: File {file_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    # Validate model name to prevent command injection
    if not re.match(r'^[\w.-]+$', model):
        print(f"Error: Invalid model name: {model}", file=sys.stderr)
        sys.exit(1)

    # Handle legacy encodings gracefully
    code = path.read_text(encoding="utf-8", errors="replace")
    prompt = get_prompt_for_action(action, code, path.suffix)

    prompt = edit_prompt_manually(prompt)

    print(f"[*] Analyzing file {path.name} (Action: {action.upper()}) via npurun...")
    
    # npurun requires the prompt as a trailing argument, not via standard input.
    # So we tell PowerShell to read from stdin, store it in a variable, and pass it as an argument.
    ps_command = f'$prompt = [Console]::In.ReadToEnd().Trim(); npurun run {model} "$prompt"'
    
    # Prefer pwsh.exe (PowerShell Core) if available, otherwise powershell.exe
    ps_executable = "pwsh.exe" if shutil.which("pwsh.exe") else "powershell.exe"

    try:
        # Transparently execute PowerShell from WSL
        process = subprocess.Popen(
            [ps_executable, "-Command", ps_command],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        
        # Send the prompt to PowerShell and wait for the response
        stdout, stderr = process.communicate(input=prompt)
        
        if process.returncode != 0:
            print(f"\n[!] Error from {ps_executable}: {stderr}", file=sys.stderr)
            sys.exit(1)

        print("\n" + "="*50 + "\n")
        print(stdout.strip())
        print("\n" + "="*50 + "\n")
        
    except FileNotFoundError:
        print(f"\n[!] Could not find {ps_executable}. Ensure you are running this script in WSL on Windows or that PowerShell is in your PATH.", file=sys.stderr)
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegacyLens-AI: AI-powered Legacy Analyzer via PowerShell interop")
    parser.add_argument("file", help="Path to the legacy file to analyze")
    parser.add_argument("--action", choices=["document", "security", "refactor"], default="security")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use in npurun")
    
    args = parser.parse_args()
    
    analyze_legacy_code(args.file, args.action, args.model)
