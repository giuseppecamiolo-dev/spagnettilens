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


def test_diff_empty_traces_not_marked_match_exact():
    baseline = _make_trace("gemini/gemini-3.5-flash", [], sandbox_passed=False)
    candidate = _make_trace("npu/qwen3-4b-instruct-2507", [], sandbox_passed=False)

    report = diff_hierarchy_traces(baseline, candidate)
    assert report.divergence_kind == "EMPTY_TRACE"
    assert report.normalized_similarity == 0.0


def test_extract_candidate_python_code_nested_braces_and_dict_literal():
    nested_code = "def ok():\n    return {'status': 'ok'}\n"
    json_payload = json.dumps(
        {
            "source_file": "fixtures/legacy_invoice_batch.pl",
            "success": True,
            "final_code": nested_code,
        }
    )
    assert extract_candidate_python_code(f"Summary:\n{json_payload}") == nested_code.strip()

    dict_str = str({"source_file": "x.pl", "final_code": nested_code})
    assert extract_candidate_python_code(dict_str) == nested_code.strip()


def test_attach_trace_collectors_captures_callback_registry_steps():
    from smolagents import tool
    from smolagents.models import ChatMessage, MessageRole, Model
    from core.smol_hierarchy import LedgerCodeAgent
    from core.trace_diff import _attach_trace_collectors

    @tool
    def extract_static_dependency_graph(file_path: str) -> str:
        """Mock graph tool.

        Args:
            file_path: path
        """
        return "{}"

    class _DummyModel(Model):
        def __init__(self) -> None:
            super().__init__(model_id="dummy")
            self.step = 0

        def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
            self.step += 1
            if self.step == 1:
                return ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content='Thought: call tool\n<code>\nres = extract_static_dependency_graph(file_path="a.pl")\n</code>',
                )
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content='Thought: finish\n<code>\nfinal_answer("done")\n</code>',
            )

    agent = LedgerCodeAgent(
        tools=[extract_static_dependency_graph],
        model=_DummyModel(),
        name="spaghettilens_supervisor",
    )
    tiers = _attach_trace_collectors(agent, registered_names=("extract_static_dependency_graph",))
    agent.run("test")

    assert tiers["spaghettilens_supervisor"].flattened_calls == ["extract_static_dependency_graph"]
    assert tiers["spaghettilens_supervisor"].step_topology == [["extract_static_dependency_graph"], []]


def test_diff_report_renders_baseline_gate_errors():
    baseline = _make_trace(
        "gemini/gemini-3.5-flash",
        [["discovery_lead"]],
        sandbox_passed=False,
        sandbox_errors=["RUNTIME_VIOLATION: stub only"],
    )
    candidate = _make_trace("npu/qwen3-4b-instruct-2507", [["discovery_lead"]], sandbox_passed=True)
    md = diff_hierarchy_traces(baseline, candidate).to_markdown()
    assert "**Baseline Gate Errors:** `['RUNTIME_VIOLATION: stub only']`" in md
