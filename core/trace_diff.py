from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Optional

from smolagents import ActionStep, CodeAgent

from core.call_ledger import extract_calls_with_args
from core.sandbox_runner import verify_refactored_code
from core.schema_graph import build_dependency_graph
from core.smol_hierarchy import reset_hierarchy_ledgers

DivergenceKind = Literal[
    "MATCH_EXACT",
    "MATCH_TOPOLOGY_VARIANT",
    "ROUTE_DIVERGENCE",
]

OutcomeClassification = Literal[
    "PARITY_PASS",
    "VALID_ALTERNATIVE_PATH",
    "CONFIRMED_SILENT_FAILURE",
    "BOTH_FAILED_GATES",
    "BASELINE_FAILED_CANDIDATE_PASSED",
]

DEFAULT_ALL_REGISTERED_NAMES: tuple[str, ...] = (
    "extract_static_dependency_graph",
    "audit_security_and_ledger_invariants",
    "execute_strangler_refactoring",
    "run_standalone_sandbox_check",
    "dependency_graph_agent",
    "security_invariant_agent",
    "strangler_sandbox_agent",
    "discovery_lead",
    "modernization_lead",
)

PYTHON_BLOCK_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class AgentTierTrace:
    """Recorded static call-inventory trace for a single agent tier in the hierarchy."""

    agent_name: str
    step_topology: list[list[str]] = field(default_factory=list)
    flattened_calls: list[str] = field(default_factory=list)
    step_errors: list[str] = field(default_factory=list)
    duplicate_skips: int = 0

    @property
    def total_steps(self) -> int:
        return len(self.step_topology)

    @property
    def max_calls_per_step(self) -> int:
        return max((len(step) for step in self.step_topology), default=0)


@dataclass
class HierarchyRunTrace:
    """Complete execution trace, extracted artifact, and 4-gate verdict for one model."""

    model_label: str
    fixture_path: str
    schema_path: str
    wall_time_sec: float
    raw_final_output: str
    extracted_python_code: str
    sandbox_passed: bool
    sandbox_errors: list[str]
    tiers: dict[str, AgentTierTrace] = field(default_factory=dict)

    @property
    def global_step_topology(self) -> list[list[str]]:
        topology: list[list[str]] = []
        for tier in self.tiers.values():
            topology.extend(tier.step_topology)
        return topology

    @property
    def global_flattened_calls(self) -> list[str]:
        calls: list[str] = []
        for tier in self.tiers.values():
            calls.extend(tier.flattened_calls)
        return calls

    @property
    def total_duplicate_skips(self) -> int:
        return sum(t.duplicate_skips for t in self.tiers.values())


@dataclass
class TraceDiffReport:
    """Side-by-side comparison between a baseline model and a local/edge candidate."""

    fixture_path: str
    baseline_model: str
    candidate_model: str
    divergence_kind: DivergenceKind
    outcome_classification: OutcomeClassification
    edit_distance: int
    normalized_similarity: float
    baseline_step_topology: list[list[str]]
    candidate_step_topology: list[list[str]]
    baseline_flattened_calls: list[str]
    candidate_flattened_calls: list[str]
    missing_in_candidate: list[str]
    extra_in_candidate: list[str]
    baseline_passed_gates: bool
    candidate_passed_gates: bool
    baseline_gate_errors: list[str]
    candidate_gate_errors: list[str]
    baseline_wall_time_sec: float
    candidate_wall_time_sec: float
    candidate_duplicate_skips: int

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    def to_markdown(self) -> str:
        b_topo = " -> ".join(f"[{', '.join(s) or 'noop'}]" for s in self.baseline_step_topology) or "none"
        c_topo = " -> ".join(f"[{', '.join(s) or 'noop'}]" for s in self.candidate_step_topology) or "none"
        lines = [
            f"### Trace Diff Report: `{self.fixture_path}`",
            "",
            f"- **Route Classification:** `{self.divergence_kind}` (edit distance: `{self.edit_distance}`, similarity: `{self.normalized_similarity:.1%}`)",
            f"- **Oracle Classification:** `{self.outcome_classification}`",
            "",
            "| Metric | Baseline (`" + self.baseline_model + "`) | Candidate (`" + self.candidate_model + "`) |",
            "| :--- | :--- | :--- |",
            f"| **4-Gate Sandbox Verdict** | {'PASS' if self.baseline_passed_gates else 'FAIL'} | {'PASS' if self.candidate_passed_gates else 'FAIL'} |",
            f"| **Flattened Tool Sequence** | `{self.baseline_flattened_calls}` | `{self.candidate_flattened_calls}` |",
            f"| **Step Topology** | `{b_topo}` | `{c_topo}` |",
            f"| **Duplicate Calls Guarded** | 0 | {self.candidate_duplicate_skips} |",
            f"| **Wall Time (s)** | {self.baseline_wall_time_sec:.2f}s | {self.candidate_wall_time_sec:.2f}s |",
        ]
        if self.missing_in_candidate:
            lines.append(f"- **Calls Omitted by Candidate:** `{self.missing_in_candidate}`")
        if self.extra_in_candidate:
            lines.append(f"- **Extra Calls by Candidate:** `{self.extra_in_candidate}`")
        if self.candidate_gate_errors:
            lines.append(f"- **Candidate Gate Errors:** `{self.candidate_gate_errors}`")
        return "\n".join(lines)


def _levenshtein_distance(seq_a: list[str], seq_b: list[str]) -> int:
    if not seq_a:
        return len(seq_b)
    if not seq_b:
        return len(seq_a)

    prev = list(range(len(seq_b) + 1))
    for i, item_a in enumerate(seq_a, start=1):
        curr = [i]
        for j, item_b in enumerate(seq_b, start=1):
            cost = 0 if item_a == item_b else 1
            curr.append(
                min(
                    prev[j] + 1,       # deletion
                    curr[j - 1] + 1,   # insertion
                    prev[j - 1] + cost # substitution
                )
            )
        prev = curr
    return prev[-1]


def extract_candidate_python_code(raw_output: str) -> str:
    """Extracts generated Python code from JSON tool reports, markdown fences, or raw output."""
    text = (raw_output or "").strip()
    if not text:
        return ""

    # Check if StranglerAgent JSON report is embedded in the hierarchy output
    for match in re.finditer(r'\{\s*"source_file"\s*:.*?"final_code"\s*:.*?\}', text, re.DOTALL):
        try:
            payload = json.loads(match.group(0))
            if isinstance(payload, dict) and payload.get("final_code"):
                return str(payload["final_code"]).strip()
        except json.JSONDecodeError:
            pass

    fence_match = PYTHON_BLOCK_RE.search(text)
    if fence_match:
        return fence_match.group(1).strip()

    return text


def _attach_trace_collectors(
    root_agent: CodeAgent,
    registered_names: Iterable[str],
) -> dict[str, AgentTierTrace]:
    """Attaches non-invasive ActionStep observers to all tiers in the hierarchy."""
    allowed = tuple(registered_names)
    tiers: dict[str, AgentTierTrace] = {}
    visited: set[int] = set()

    def _instrument(agent: CodeAgent) -> None:
        if id(agent) in visited:
            return
        visited.add(id(agent))

        name = getattr(agent, "name", "unknown_agent")
        tier_trace = AgentTierTrace(agent_name=name)
        tiers[name] = tier_trace

        callbacks = getattr(agent, "step_callbacks", None)
        if isinstance(callbacks, dict):
            prev_cb = callbacks.get(ActionStep)

            def _trace_cb(step: ActionStep, ag: CodeAgent, _t: AgentTierTrace = tier_trace, _prev: Any = prev_cb) -> None:
                code_action = getattr(step, "code_action", None) or ""
                obs = str(getattr(step, "observations", None) or "")
                if "Skipped duplicate tool call(s)" in obs:
                    _t.duplicate_skips += 1

                calls = extract_calls_with_args(code_action, registered_names=allowed)
                step_names = [c.name for c in calls]
                _t.step_topology.append(step_names)
                _t.flattened_calls.extend(step_names)

                err = getattr(step, "error", None)
                if err:
                    _t.step_errors.append(str(err))

                if callable(_prev):
                    _prev(step, ag)

            callbacks[ActionStep] = _trace_cb

        for sub in (getattr(agent, "managed_agents", None) or {}).values():
            _instrument(sub)

    _instrument(root_agent)
    return tiers


def run_hierarchy_with_trace(
    build_agent_fn: Callable[[], CodeAgent],
    model_label: str,
    fixture_path: str,
    schema_path: str = "fixtures/schema.sql",
    task_prompt: Optional[str] = None,
    registered_names: Iterable[str] = DEFAULT_ALL_REGISTERED_NAMES,
) -> HierarchyRunTrace:
    """Runs one model through the 3-tier hierarchy, records static call inventories, and scores via 4-gate sandbox."""
    agent = build_agent_fn()
    reset_hierarchy_ledgers(agent)
    tiers = _attach_trace_collectors(agent, registered_names=registered_names)

    prompt = task_prompt or (
        f"Modernize legacy file '{fixture_path}' using schema '{schema_path}' "
        "and verify security and ledger invariants in the sandbox."
    )

    t0 = time.perf_counter()
    raw_output = str(agent.run(prompt))
    elapsed = time.perf_counter() - t0

    extracted_code = extract_candidate_python_code(raw_output)

    # Determine ledger precision requirement statically from the source fixture + schema
    fixture_file = Path(fixture_path)
    schema_file = Path(schema_path) if schema_path else None
    schema_sql = schema_file.read_text(encoding="utf-8", errors="replace") if (schema_file and schema_file.is_file()) else None

    require_ledger = False
    if fixture_file.is_file():
        legacy_code = fixture_file.read_text(encoding="utf-8", errors="replace")
        dep_graph = build_dependency_graph(legacy_code, str(fixture_file), schema_sql=schema_sql)
        require_ledger = any(
            "LEDGER_INVARIANT" in finding
            for finding in dep_graph.security_and_invariant_findings
        )

    sandbox_res = verify_refactored_code(
        extracted_code,
        schema_sql=schema_sql,
        require_ledger_precision=require_ledger,
        execute_smoke_test=True,
    )

    return HierarchyRunTrace(
        model_label=model_label,
        fixture_path=fixture_path,
        schema_path=schema_path,
        wall_time_sec=elapsed,
        raw_final_output=raw_output,
        extracted_python_code=extracted_code,
        sandbox_passed=sandbox_res.passed,
        sandbox_errors=list(sandbox_res.errors),
        tiers=tiers,
    )


def diff_hierarchy_traces(
    baseline: HierarchyRunTrace,
    candidate: HierarchyRunTrace,
) -> TraceDiffReport:
    """Compares static call sequences and 4-gate oracle verdicts across two model traces."""
    b_flat = baseline.global_flattened_calls
    c_flat = candidate.global_flattened_calls
    b_topo = baseline.global_step_topology
    c_topo = candidate.global_step_topology

    dist = _levenshtein_distance(b_flat, c_flat)
    denom = max(len(b_flat), len(c_flat), 1)
    similarity = max(0.0, 1.0 - (dist / denom))

    if b_flat == c_flat and b_topo == c_topo:
        div_kind: DivergenceKind = "MATCH_EXACT"
    elif b_flat == c_flat:
        div_kind = "MATCH_TOPOLOGY_VARIANT"
    else:
        div_kind = "ROUTE_DIVERGENCE"

    b_set = set(b_flat)
    c_set = set(c_flat)
    missing = sorted(b_set - c_set)
    extra = sorted(c_set - b_set)

    if baseline.sandbox_passed and candidate.sandbox_passed:
        if div_kind in ("MATCH_EXACT", "MATCH_TOPOLOGY_VARIANT"):
            outcome: OutcomeClassification = "PARITY_PASS"
        else:
            outcome = "VALID_ALTERNATIVE_PATH"
    elif baseline.sandbox_passed and not candidate.sandbox_passed:
        outcome = "CONFIRMED_SILENT_FAILURE"
    elif not baseline.sandbox_passed and candidate.sandbox_passed:
        outcome = "BASELINE_FAILED_CANDIDATE_PASSED"
    else:
        outcome = "BOTH_FAILED_GATES"

    return TraceDiffReport(
        fixture_path=baseline.fixture_path,
        baseline_model=baseline.model_label,
        candidate_model=candidate.model_label,
        divergence_kind=div_kind,
        outcome_classification=outcome,
        edit_distance=dist,
        normalized_similarity=similarity,
        baseline_step_topology=b_topo,
        candidate_step_topology=c_topo,
        baseline_flattened_calls=b_flat,
        candidate_flattened_calls=c_flat,
        missing_in_candidate=missing,
        extra_in_candidate=extra,
        baseline_passed_gates=baseline.sandbox_passed,
        candidate_passed_gates=candidate.sandbox_passed,
        baseline_gate_errors=baseline.sandbox_errors,
        candidate_gate_errors=candidate.sandbox_errors,
        baseline_wall_time_sec=baseline.wall_time_sec,
        candidate_wall_time_sec=candidate.wall_time_sec,
        candidate_duplicate_skips=candidate.total_duplicate_skips,
    )
