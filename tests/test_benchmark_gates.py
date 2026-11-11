"""
SpaghettiLens-AI (v0.5.0) - Automated Test Suite for Benchmark Verification Gates
---------------------------------------------------------------------------------
Compatible with both `pytest` and `python -m unittest` for zero-dependency CI runs.
Validates the 4 deterministic verification gates in `benchmarks/run_eval.py`:
  - Gate 1: Syntactic & Type Validity (AST parsing & callable entry points)
  - Gate 2: Security & SQL Parameterization (f-string / concatenation rejection)
  - Gate 3: Financial Precision (decimal.Decimal & ROUND_HALF_UP enforcement)
  - Gate 4: Behavioral & API Equivalence (sandbox execution across test vectors)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure repository root and benchmarks/ directory are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from run_eval import (
    FLOAT_HAZARD_CANDIDATE,
    SQL_INJECTION_CANDIDATE,
    SYNTHETIC_FIXTURES,
    TRUNCATED_SYNTAX_CANDIDATE,
    VALID_REFACTORED_SERVICE,
    DeterministicSandboxVerifier,
    execute_evaluation_suite,
)


class TestBenchmarkVerificationGates(unittest.TestCase):
    # ========================================================================
    # Gate 1 Tests: Syntactic & Type Validity
    # ========================================================================

    def test_gate_1_accepts_valid_python_service(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_1_syntax_and_types(VALID_REFACTORED_SERVICE)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_gate_1_rejects_syntax_error(self) -> None:
        broken_code = "def calculate_invoice_total(subtotal_str:\n    pass"
        ok, err = DeterministicSandboxVerifier.verify_gate_1_syntax_and_types(broken_code)
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertIn("SyntaxError", err or "")

    def test_gate_1_rejects_module_without_callable_function(self) -> None:
        constants_only = "TAX_RATE = 0.22\nLEDGER_TABLE = 'ledger_entries'\n"
        ok, err = DeterministicSandboxVerifier.verify_gate_1_syntax_and_types(constants_only)
        self.assertFalse(ok)
        self.assertEqual(err, "Missing callable endpoint or service function definition")

    # ========================================================================
    # Gate 2 Tests: Security & SQL Parameterization
    # ========================================================================

    def test_gate_2_accepts_parameterized_bind_query(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_2_sql_parameterization(VALID_REFACTORED_SERVICE)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_gate_2_rejects_fstring_sql_interpolation(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_2_sql_parameterization(SQL_INJECTION_CANDIDATE)
        self.assertFalse(ok)
        self.assertEqual(err, "Unparameterized SQL detected inside f-string interpolation")

    def test_gate_2_rejects_string_concatenation_sql(self) -> None:
        concat_sql_code = (
            "def get_orders(uid: str):\n"
            '    q = "SELECT * FROM orders WHERE user_id = " + uid\n'
            "    return q\n"
        )
        ok, err = DeterministicSandboxVerifier.verify_gate_2_sql_parameterization(concat_sql_code)
        self.assertFalse(ok)
        self.assertEqual(err, "Unparameterized SQL string concatenation/formatting detected")

    def test_gate_2_rejects_missing_parameterized_constructs(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_2_sql_parameterization(TRUNCATED_SYNTAX_CANDIDATE)
        self.assertFalse(ok)
        self.assertEqual(err, "Missing SQLAlchemy parameterized query constructs")

    # ========================================================================
    # Gate 3 Tests: Financial Precision (Decimal & ROUND_HALF_UP)
    # ========================================================================

    def test_gate_3_accepts_strict_decimal_quantization(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_3_financial_precision(VALID_REFACTORED_SERVICE)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_gate_3_rejects_float_cast_hazard(self) -> None:
        ok, err = DeterministicSandboxVerifier.verify_gate_3_financial_precision(FLOAT_HAZARD_CANDIDATE)
        self.assertFalse(ok)
        self.assertEqual(err, "Forbidden float() cast detected in financial calculation")

    def test_gate_3_rejects_missing_round_half_up(self) -> None:
        missing_rounding_code = (
            "from decimal import Decimal\n"
            "def calculate_invoice_total(a: str, b: str) -> Decimal:\n"
            "    return Decimal(a) * Decimal(b)\n"
        )
        ok, err = DeterministicSandboxVerifier.verify_gate_3_financial_precision(missing_rounding_code)
        self.assertFalse(ok)
        self.assertEqual(err, "Missing explicit Decimal quantization with ROUND_HALF_UP")

    # ========================================================================
    # Gate 4 Tests: Behavioral & API Equivalence
    # ========================================================================

    def test_gate_4_passes_perl_billing_fixture_vectors(self) -> None:
        fixture = SYNTHETIC_FIXTURES[0]
        ok, err = DeterministicSandboxVerifier.verify_gate_4_behavioral_equivalence(
            VALID_REFACTORED_SERVICE, fixture.test_vectors
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_gate_4_passes_php_auth_order_fixture_vectors(self) -> None:
        fixture = SYNTHETIC_FIXTURES[1]
        ok, err = DeterministicSandboxVerifier.verify_gate_4_behavioral_equivalence(
            VALID_REFACTORED_SERVICE, fixture.test_vectors
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_gate_4_rejects_unvalidated_negative_or_injection_inputs(self) -> None:
        naive_decimal_service = (
            "from decimal import Decimal, ROUND_HALF_UP\n"
            "def calculate_invoice_total(subtotal_str: str, tax_rate_str: str) -> Decimal:\n"
            "    gross = Decimal(subtotal_str) * (Decimal('1.00') + Decimal(tax_rate_str))\n"
            "    return gross.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
        )
        fixture = SYNTHETIC_FIXTURES[0]
        ok, err = DeterministicSandboxVerifier.verify_gate_4_behavioral_equivalence(
            naive_decimal_service, fixture.test_vectors
        )
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertIn("Failed to reject invalid/malicious input vector", err or "")

    # ========================================================================
    # End-to-End Evaluation Harness Determinism Test
    # ========================================================================

    def test_end_to_end_evaluation_suite_reproducibility(self) -> None:
        reports_a, logs_a = execute_evaluation_suite(runs_per_fixture=10, seed=42)
        reports_b, logs_b = execute_evaluation_suite(runs_per_fixture=10, seed=42)

        self.assertEqual(len(reports_a), 5)
        self.assertEqual(len(logs_a), 100)
        self.assertEqual([r.passes for r in reports_a], [3, 7, 2, 17, 19])
        self.assertEqual([r.pass_rate_pct for r in reports_a], [15.0, 35.0, 10.0, 85.0, 95.0])
        self.assertEqual([m.tokens_used for m in logs_a], [m.tokens_used for m in logs_b])


if __name__ == "__main__":
    unittest.main(verbosity=2)
