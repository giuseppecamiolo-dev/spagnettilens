from pathlib import Path
from typing import Iterator

from core.providers import LLMProvider
from core.sandbox_runner import verify_refactored_code
from core.strangler_agent import StranglerAgent


class MockSelfHealingProvider(LLMProvider):
    """Simula un LLM che sbaglia al 1° tentativo (usa float e f-string SQL) e si corregge al 2°."""

    def __init__(self) -> None:
        self.call_count = 0

    def stream(self, prompt: str) -> Iterator[str]:
        self.call_count += 1
        if self.call_count == 1:
            # Tentativo 1: vulnerabile a SQLi e senza Decimal
            bad_code = (
                "```python\n"
                "import sqlite3\n"
                "def get_invoices(student_code: str):\n"
                "    conn = sqlite3.connect(':memory:')\n"
                "    cur = conn.cursor()\n"
                "    cur.execute(f\"SELECT amount FROM invoices WHERE student_code = '{student_code}'\")\n"
                "    total = 0.0\n"
                "    for row in cur.fetchall():\n"
                "        total += float(row[0])\n"
                "    return total\n"
                "```"
            )
            yield bad_code
        else:
            # Tentativo 2: dopo il feedback della sandbox, usa query parametrizzata e Decimal
            good_code = (
                "```python\n"
                "import os\n"
                "import sqlite3\n"
                "from decimal import Decimal\n\n"
                "def get_invoices(student_code: str) -> Decimal:\n"
                "    db_path = os.environ.get('DB_PATH', ':memory:')\n"
                "    conn = sqlite3.connect(db_path)\n"
                "    cur = conn.cursor()\n"
                "    cur.execute('SELECT amount FROM invoices WHERE student_code = ? AND status = ?', (student_code, 'pending'))\n"
                "    total = Decimal('0.00')\n"
                "    for (amount,) in cur.fetchall():\n"
                "        total += Decimal(str(amount))\n"
                "    return total\n"
                "```"
            )
            yield good_code


def test_sandbox_rejects_sql_injection_and_missing_decimal():
    insecure_output = (
        "```python\n"
        "def run(user_id):\n"
        "    query = f'SELECT * FROM invoices WHERE id = {user_id}'\n"
        "    return query\n"
        "```"
    )
    res = verify_refactored_code(insecure_output, require_ledger_precision=True)
    assert res.passed is False
    assert res.security_ok is False
    assert res.ledger_invariant_ok is False
    assert any("SECURITY_VIOLATION" in e for e in res.errors)
    assert any("LEDGER_INVARIANT_VIOLATION" in e for e in res.errors)


def test_sandbox_rejects_syntax_error():
    broken_output = "```python\ndef broken_func(:\n    pass\n```"
    res = verify_refactored_code(broken_output)
    assert res.passed is False
    assert res.syntax_ok is False
    assert any("SyntaxError" in e for e in res.errors)


def test_strangler_agent_self_healing_loop():
    perl_code = Path("spaghettiCode.pl").read_text(encoding="utf-8")
    schema_sql = Path("fixtures/schema.sql").read_text(encoding="utf-8")

    mock_provider = MockSelfHealingProvider()
    agent = StranglerAgent(provider=mock_provider, max_retries=3)

    report = agent.run(perl_code, "spaghettiCode.pl", schema_sql=schema_sql)

    assert report.success is True
    assert report.iterations_used == 2
    assert len(report.attempts) == 2
    assert report.attempts[0].sandbox_result.passed is False
    assert report.attempts[1].sandbox_result.passed is True
    assert "Decimal" in report.final_code
