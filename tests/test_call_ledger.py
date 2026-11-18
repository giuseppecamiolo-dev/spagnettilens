from __future__ import annotations

import pytest

from core.call_ledger import CallLedger, extract_calls_with_args


def test_positional_and_keyword_normalization_match():
    aliases = {"extract_static_dependency_graph": ("file_path", "schema_path")}
    registered = {"extract_static_dependency_graph"}

    c_pos = extract_calls_with_args(
        'extract_static_dependency_graph("fixtures/spaghettiCode.php", "fixtures/schema.sql")',
        registered_names=registered,
        arg_aliases=aliases,
    )
    c_kw = extract_calls_with_args(
        'extract_static_dependency_graph(schema_path="fixtures/schema.sql", file_path="fixtures/spaghettiCode.php")',
        registered_names=registered,
        arg_aliases=aliases,
    )

    assert len(c_pos) == 1
    assert len(c_kw) == 1
    assert c_pos[0].is_static is True
    assert c_kw[0].is_static is True
    assert c_pos[0].arg_fingerprint == c_kw[0].arg_fingerprint


def test_dynamic_expression_marked_non_static_and_never_short_circuited():
    aliases = {"extract_static_dependency_graph": ("file_path", "schema_path")}
    ledger = CallLedger(
        registered_names={"extract_static_dependency_graph"},
        arg_aliases=aliases,
    )

    # Record a static call first
    ledger.record_step(
        step_num=1,
        code_action='extract_static_dependency_graph("fixtures/spaghettiCode.php")',
        status="OK",
        outcome_summary="4 tables",
    )

    # Loop variable call must not be treated as a duplicate of the static call
    dynamic_code = (
        "for path in target_files:\n"
        "    extract_static_dependency_graph(path)\n"
    )
    skip, msg = ledger.should_short_circuit(dynamic_code)
    assert skip is False
    assert msg == ""


def test_short_circuit_blocks_identical_ok_call_but_allows_retry_after_error():
    aliases = {"audit_security_and_ledger_invariants": ("file_path", "schema_path")}
    ledger = CallLedger(
        registered_names={"audit_security_and_ledger_invariants"},
        arg_aliases=aliases,
    )

    code = 'audit_security_and_ledger_invariants(file_path="fixtures/spaghettiCode.php")'

    # 1. Record an ERROR outcome -> retry should still be permitted
    ledger.record_step(step_num=1, code_action=code, status="ERROR", outcome_summary="Timeout")
    skip_err, _ = ledger.should_short_circuit(code)
    assert skip_err is False

    # 2. Record an OK outcome -> identical call should now short-circuit
    ledger.record_step(step_num=2, code_action=code, status="OK", outcome_summary="LEDGER_INVARIANT found")
    skip_ok, msg = ledger.should_short_circuit(code)
    assert skip_ok is True
    assert "Skipped duplicate tool call(s)" in msg
    assert "step 1" in msg
    assert "LEDGER_INVARIANT found" in msg


def test_mixed_step_with_one_new_call_is_not_short_circuited():
    aliases = {
        "extract_static_dependency_graph": ("file_path", "schema_path"),
        "audit_security_and_ledger_invariants": ("file_path", "schema_path"),
    }
    ledger = CallLedger(
        registered_names=set(aliases.keys()),
        arg_aliases=aliases,
    )

    ledger.record_step(
        step_num=1,
        code_action='extract_static_dependency_graph("fixtures/spaghettiCode.php")',
        status="OK",
    )

    # Step contains one already-executed call AND one brand-new call -> must execute
    mixed_code = (
        'g = extract_static_dependency_graph("fixtures/spaghettiCode.php")\n'
        's = audit_security_and_ledger_invariants("fixtures/spaghettiCode.php")\n'
    )
    skip, _ = ledger.should_short_circuit(mixed_code)
    assert skip is False


def test_format_digest_respects_char_budget_and_tracks_hit_counts():
    ledger = CallLedger(
        registered_names={"tool_a", "tool_b", "tool_c"},
        max_digest_entries=5,
        max_digest_chars=160,
    )

    ledger.record_step(1, 'tool_a("alpha")', status="OK", outcome_summary="ok")
    ledger.record_step(2, 'tool_a("alpha")', status="OK", outcome_summary="ok")
    ledger.record_step(3, 'tool_b("beta_long_argument_string")', status="OK")
    ledger.record_step(4, 'tool_c("gamma_long_argument_string")', status="OK")

    digest = ledger.format_digest()
    assert digest.startswith("[Executed Calls Ledger")
    assert "[x2]" in digest
    assert len(digest) <= 160

    ledger.clear()
    assert ledger.format_digest() == ""


def test_syntax_error_in_code_action_is_handled_gracefully():
    calls = extract_calls_with_args(
        "def broken(:\n    extract_static_dependency_graph('a.php'",
        registered_names={"extract_static_dependency_graph"},
    )
    assert calls == []
