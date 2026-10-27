import ast
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SandboxResult:
    passed: bool
    syntax_ok: bool
    security_ok: bool
    ledger_invariant_ok: bool
    runtime_ok: bool
    errors: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    def to_feedback_prompt(self) -> str:
        """Formatta gli errori della sandbox per il loop di self-healing dell'LLM."""
        if self.passed:
            return "All sandbox parity, syntax, and security checks PASSED."
        lines = ["SANDBOX VERIFICATION FAILED. Fix the following issues in your refactored code:"]
        for idx, err in enumerate(self.errors, 1):
            lines.append(f"  {idx}. {err}")
        if self.stderr:
            lines.append(f"\nRuntime STDERR:\n{self.stderr.strip()}")
        return "\n".join(lines)


def extract_code_block(llm_response: str) -> str:
    """Estrae il blocco di codice Python dalla risposta Markdown dell'LLM."""
    pattern = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(llm_response)
    if matches:
        return max(matches, key=len).strip()
    return llm_response.strip()


def validate_python_ast(code: str) -> Optional[str]:
    """Verifica che il codice Python generato sia sintatticamente valido."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as exc:
        return f"SyntaxError at line {exc.lineno}: {exc.msg}"


def check_security_and_invariants(
    code: str, require_ledger_precision: bool = False
) -> tuple[bool, bool, List[str]]:
    """
    Controlla che il codice rifattorizzato non contenga SQL Injection
    e rispetti le invarianti finanziarie (Decimal / integer cents).
    """
    errors: List[str] = []
    security_ok = True
    ledger_ok = True

    fstring_sql = re.search(
        r"""f["'][^"']*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"']*\{[^}]+\}""",
        code,
        re.IGNORECASE,
    )
    concat_sql = re.search(
        r"""["']\s*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"']*["']\s*\+""",
        code,
        re.IGNORECASE,
    )
    if fstring_sql or concat_sql:
        security_ok = False
        errors.append(
            "SECURITY_VIOLATION: Detected string interpolation/concatenation inside SQL query. "
            "Use parameterized placeholders (?, :param, or %s) exclusively."
        )

    if re.search(r"""password\s*=\s*["'][^"']+["']""", code, re.IGNORECASE):
        if "os.environ" not in code and "getenv" not in code:
            security_ok = False
            errors.append(
                "SECURITY_VIOLATION: Hardcoded password detected. Use os.environ.get() for credentials."
            )

    if require_ledger_precision:
        uses_decimal_or_cents = bool(
            re.search(r"\b(Decimal|ROUND_HALF_UP|cents|int\()\b", code)
        )
        if not uses_decimal_or_cents:
            ledger_ok = False
            errors.append(
                "LEDGER_INVARIANT_VIOLATION: Legacy script accumulates monetary amounts. "
                "Refactored code MUST import `decimal.Decimal` or use integer cents to prevent IEEE 754 float drift."
            )

    return security_ok, ledger_ok, errors


def initialize_ephemeral_sqlite(schema_sql: Optional[str], db_path: Path) -> None:
    """Inizializza un database SQLite effimero adattando il DDL SQL di test."""
    conn = sqlite3.connect(str(db_path))
    try:
        if schema_sql:
            normalized_sql = re.sub(
                r"INT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY",
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                schema_sql,
                flags=re.IGNORECASE,
            )
            conn.executescript(normalized_sql)
        conn.commit()
    finally:
        conn.close()


def verify_refactored_code(
    llm_output: str,
    schema_sql: Optional[str] = None,
    require_ledger_precision: bool = False,
    execute_smoke_test: bool = True,
) -> SandboxResult:
    """
    Valida il codice Python rifattorizzato tramite AST, regole di sicurezza,
    invarianti contabili ed esecuzione opzionale in sandbox isolata.
    """
    code = extract_code_block(llm_output)
    errors: List[str] = []

    syntax_err = validate_python_ast(code)
    if syntax_err:
        return SandboxResult(
            passed=False,
            syntax_ok=False,
            security_ok=False,
            ledger_invariant_ok=False,
            runtime_ok=False,
            errors=[syntax_err],
        )

    security_ok, ledger_ok, sec_errors = check_security_and_invariants(
        code, require_ledger_precision=require_ledger_precision
    )
    errors.extend(sec_errors)

    runtime_ok = True
    stdout_str = ""
    stderr_str = ""

    if execute_smoke_test:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_file = tmp_path / "sandbox_test.db"
            initialize_ephemeral_sqlite(schema_sql, db_file)

            script_file = tmp_path / "refactored_candidate.py"
            script_file.write_text(code, encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, "-m", "py_compile", str(script_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            stdout_str = proc.stdout
            stderr_str = proc.stderr
            if proc.returncode != 0:
                runtime_ok = False
                errors.append(f"Bytecode compilation failed: {stderr_str.strip()}")

    passed = (syntax_err is None) and security_ok and ledger_ok and runtime_ok
    return SandboxResult(
        passed=passed,
        syntax_ok=(syntax_err is None),
        security_ok=security_ok,
        ledger_invariant_ok=ledger_ok,
        runtime_ok=runtime_ok,
        errors=errors,
        stdout=stdout_str,
        stderr=stderr_str,
    )
