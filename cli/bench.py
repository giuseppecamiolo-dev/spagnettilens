from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from core.providers import LLMProvider, create_provider
from core.smol_hierarchy import build_spaghettilens_smol_hierarchy
from core.trace_diff import diff_hierarchy_traces, run_hierarchy_with_trace


def _make_hierarchy_builder(
    model_spec: str,
    fixture_path: str,
    schema_path: str,
    max_retries: int,
    enable_duplicate_guard: bool,
) -> Callable[[], object]:
    """Builds a fresh hierarchy instance bound to a provider parsed from `provider/model`."""
    if "/" in model_spec:
        provider_name, model_name = model_spec.split("/", 1)
    else:
        provider_name, model_name = "npu", model_spec

    def _build():
        provider: LLMProvider = create_provider(provider_name=provider_name, model=model_name)
        return build_spaghettilens_smol_hierarchy(
            provider=provider,
            model_name=model_name,
            max_retries=max_retries,
            default_file_path=fixture_path,
            default_schema_path=schema_path,
            enable_duplicate_guard=enable_duplicate_guard,
        )

    return _build


def run_bench_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spaghettilens bench",
        description="Run reproducible multi-agent trace diffing and 4-gate sandbox verification.",
    )
    parser.add_argument(
        "--fixture",
        default="fixtures/spaghettiCode.php",
        help="Path to legacy .php or .pl fixture file.",
    )
    parser.add_argument(
        "--schema",
        default="fixtures/schema.sql",
        help="Path to SQL schema file (.sql).",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Baseline model spec (e.g. 'gemini/gemini-3.5-flash' or 'openai/gpt-4o').",
    )
    parser.add_argument(
        "--candidate",
        required=True,
        help="Candidate npu/edge model spec (e.g. 'npu/qwen3-4b-instruct-2507').",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Emit static call-inventory topology & flattened sequence diff report.",
    )
    parser.add_argument(
        "--no-duplicate-guard",
        action="store_true",
        help="Disable CallLedger pre-execution duplicate call interception on the candidate.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max StranglerAgent self-healing iterations per run.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path (.json or .md) to save the diff report.",
    )

    args = parser.parse_args(argv)

    print(f"[1/2] Running baseline ({args.baseline}) on {args.fixture}...")
    baseline_trace = run_hierarchy_with_trace(
        build_agent_fn=_make_hierarchy_builder(
            model_spec=args.baseline,
            fixture_path=args.fixture,
            schema_path=args.schema,
            max_retries=args.max_retries,
            enable_duplicate_guard=True,
        ),
        model_label=args.baseline,
        fixture_path=args.fixture,
        schema_path=args.schema,
    )

    print(f"[2/2] Running candidate ({args.candidate}) on {args.fixture}...")
    candidate_trace = run_hierarchy_with_trace(
        build_agent_fn=_make_hierarchy_builder(
            model_spec=args.candidate,
            fixture_path=args.fixture,
            schema_path=args.schema,
            max_retries=args.max_retries,
            enable_duplicate_guard=not args.no_duplicate_guard,
        ),
        model_label=args.candidate,
        fixture_path=args.fixture,
        schema_path=args.schema,
    )

    report = diff_hierarchy_traces(baseline_trace, candidate_trace)

    print("\n" + report.to_markdown() + "\n")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.suffix.lower() == ".md":
            out_path.write_text(report.to_markdown() + "\n", encoding="utf-8")
        else:
            out_path.write_text(report.to_json() + "\n", encoding="utf-8")
        print(f"Saved trace diff report to {out_path}")

    return 0 if report.candidate_passed_gates else 1


if __name__ == "__main__":
    sys.exit(run_bench_cli())
