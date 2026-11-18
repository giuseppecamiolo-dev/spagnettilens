from __future__ import annotations

import json
import pytest

from core.trace_diff import (
    AgentTierTrace,
    HierarchyRunTrace,
    _levenshtein_distance,
    diff_hierarchy_traces,
    extract_candidate_python_code,
)


def _make_trace(
    model_label: str,
    topology: list[list[str]],
    sandbox_passed: bool,
    sandbox_errors: list[str] | None = None,
    duplicate_skips: int = 0,
    wall_time_sec: float = 1.5,
) -> HierarchyRunTrace:
    flattened = [call for step in topology for call in step]
    tier = AgentTierTrace(
        agent_name="spaghettilens_supervisor",
        step_topology=topology,
        flattened_calls=flattened,
        duplicate_skips=duplicate_skips,
    )
    return HierarchyRunTrace(
        model_label=model_label,
        fixture_path="fixtures/spaghettiCode.php",
        schema_path="fixtures/schema.sql",
        wall_time_sec=wall_time_sec,
        raw_final_output="final_code",
        extracted_python_code="from decimal import Decimal\n",
        sandbox_passed=sandbox_passed,
        sandbox_errors=sandbox_errors or [],
        tiers={"spaghettilens_supervisor": tier},
    )


def test_levenshtein_distance_sequences():
    assert _levenshtein_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
    assert _levenshtein_distance(["a", "b", "c"], ["a", "c"]) == 1
    assert _levenshtein_distance([], ["a", "b"]) == 2
    assert _levenshtein_distance(["x"], ["y"]) == 1


def test_extract_candidate_python_code_from_json_and_fences():
    json_payload = json.dumps(
        {
            "source_file": "fixtures/spaghettiCode.php",
            "success": True,
            "iterations_used": 1,
            "attempts": [],
            "final_code": "from fastapi import FastAPI\napp = FastAPI()",
        }
    )
    wrapped = f"Audit summary...\n\n{json_payload}"
    assert extract_candidate_python_code(wrapped) == "from fastapi import FastAPI\napp = FastAPI()"

    fenced = "Here is the code:\n```python\nx = 42\n```"
    assert extract_candidate_python_code(fenced) == "x = 42"


def test_diff_match_exact_and_parity_pass():
    topo = [["discovery_lead"], ["modernization_lead"]]
    baseline = _make_trace("openai/gpt-4o", topo, sandbox_passed=True)
    candidate = _make_trace("npu/qwen3-4b-instruct-2507", topo, sandbox_passed=True)

    report = diff_hierarchy_traces(baseline, candidate)
    assert report.divergence_kind == "MATCH_EXACT"
    assert report.outcome_classification == "PARITY_PASS"
    assert report.edit_distance == 0
    assert report.normalized_similarity == pytest.approx(1.0)


def test_diff_topology_variant_when_flattened_calls_match():
    # Frontier model chains both calls in 1 step; 4B NPU splits into 2 single-call steps
    baseline = _make_trace(
        "openai/gpt-4o",
        [["discovery_lead", "modernization_lead"]],
        sandbox_passed=True,
    )
    candidate = _make_trace(
        "npu/qwen3-4b-instruct-2507",
        [["discovery_lead"], ["modernization_lead"]],
        sandbox_passed=True,
        duplicate_skips=1,
    )

    report = diff_hierarchy_traces(baseline, candidate)
    assert report.divergence_kind == "MATCH_TOPOLOGY_VARIANT"
    assert report.outcome_classification == "PARITY_PASS"
    assert report.edit_distance == 0
    assert report.candidate_duplicate_skips == 1


def test_diff_route_divergence_with_silent_failure_vs_valid_alternative():
    baseline = _make_trace(
        "openai/gpt-4o",
        [["discovery_lead"], ["modernization_lead"]],
        sandbox_passed=True,
    )

    # Candidate skipped discovery_lead and failed Gate 3 (Decimal precision)
    failing_candidate = _make_trace(
        "npu/qwen3-4b-instruct-2507",
        [["modernization_lead"]],
        sandbox_passed=False,
        sandbox_errors=["Gate 3 failed: float used for currency column"],
    )
    fail_report = diff_hierarchy_traces(baseline, failing_candidate)
    assert fail_report.divergence_kind == "ROUTE_DIVERGENCE"
    assert fail_report.outcome_classification == "CONFIRMED_SILENT_FAILURE"
    assert fail_report.missing_in_candidate == ["discovery_lead"]

    # Candidate used a different route but satisfied all 4 sandbox gates
    passing_alt_candidate = _make_trace(
        "npu/qwen3-4b-instruct-2507",
        [["execute_strangler_refactoring"]],
        sandbox_passed=True,
    )
    alt_report = diff_hierarchy_traces(baseline, passing_alt_candidate)
    assert alt_report.divergence_kind == "ROUTE_DIVERGENCE"
    assert alt_report.outcome_classification == "VALID_ALTERNATIVE_PATH"


def test_diff_report_markdown_and_json_serialization():
    baseline = _make_trace("openai/gpt-4o", [["discovery_lead"]], sandbox_passed=True)
    candidate = _make_trace("npu/qwen3-4b-instruct-2507", [["discovery_lead"]], sandbox_passed=True)

    report = diff_hierarchy_traces(baseline, candidate)
    md = report.to_markdown()
    parsed = json.loads(report.to_json())

    assert "### Trace Diff Report:" in md
    assert "`MATCH_EXACT`" in md
    assert "`PARITY_PASS`" in md
    assert parsed["outcome_classification"] == "PARITY_PASS"
