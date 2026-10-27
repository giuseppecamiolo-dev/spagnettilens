from dataclasses import dataclass, field
from typing import List, Optional

from core.providers import LLMProvider
from core.sandbox_runner import SandboxResult, extract_code_block, verify_refactored_code
from core.schema_graph import LegacyDependencyGraph, build_dependency_graph


@dataclass
class StranglerAttempt:
    iteration: int
    raw_response: str
    extracted_code: str
    sandbox_result: SandboxResult


@dataclass
class StranglerReport:
    source_file: str
    success: bool
    iterations_used: int
    final_code: str
    dependency_graph: LegacyDependencyGraph
    attempts: List[StranglerAttempt] = field(default_factory=list)


class StranglerAgent:
    """
    Agente Neuro-Simbolico che esegue il refactoring di codice legacy (Perl/PHP)
    in Python moderno (FastAPI/Pydantic) con verifica deterministica in sandbox e self-healing.
    """

    def __init__(self, provider: LLMProvider, max_retries: int = 3) -> None:
        self.provider = provider
        self.max_retries = max(1, max_retries)

    def build_initial_prompt(
        self,
        legacy_code: str,
        dep_graph: LegacyDependencyGraph,
        schema_sql: Optional[str] = None,
    ) -> str:
        prompt = (
            f"You are an autonomous Principal Backend Architect modernizing a legacy {dep_graph.language} "
            f"module ({dep_graph.file_name}) into clean, production-grade Python 3.11+.\n\n"
            "STRICT ARCHITECTURAL & SECURITY REQUIREMENTS:\n"
            "1. Eliminate all SQL Injection risks by using parameterized queries (?, :param, or %s) exclusively.\n"
            "2. Replace hardcoded credentials with `os.environ.get(...)`.\n"
            "3. Separate database access and business logic from presentation.\n"
            "4. Use FastAPI / Pydantic or standard CLI/urllib.parse instead of the deprecated `cgi` module.\n"
            "5. If monetary calculations or LEDGER_INVARIANT findings are present, you MUST use `decimal.Decimal` "
            "(or integer cents) for all currency arithmetic.\n"
            "6. Return valid, self-contained Python 3 code enclosed in a ```python ... ``` markdown block.\n\n"
            f"Legacy Source Code:\n```\n{legacy_code}\n```\n\n"
            f"Static Dependency & Invariant Graph (JSON):\n{dep_graph.to_json()}\n"
        )
        if schema_sql:
            prompt += f"\nRelational Database Schema (SQL):\n```sql\n{schema_sql}\n```\n"
        return prompt

    def build_repair_prompt(
        self,
        initial_prompt: str,
        previous_code: str,
        sandbox_result: SandboxResult,
    ) -> str:
        return (
            f"{initial_prompt}\n\n"
            "--- SELF-HEALING FEEDBACK LOOP ---\n"
            "Your previous refactoring attempt failed deterministic sandbox verification:\n"
            f"```python\n{previous_code}\n```\n\n"
            f"{sandbox_result.to_feedback_prompt()}\n\n"
            "Provide the corrected Python 3 implementation inside a ```python ... ``` block."
        )

    def run(
        self,
        legacy_code: str,
        file_name: str,
        schema_sql: Optional[str] = None,
    ) -> StranglerReport:
        dep_graph = build_dependency_graph(legacy_code, file_name, schema_sql=schema_sql)
        require_ledger = any(
            "LEDGER_INVARIANT" in finding
            for finding in dep_graph.security_and_invariant_findings
        )

        initial_prompt = self.build_initial_prompt(legacy_code, dep_graph, schema_sql)
        current_prompt = initial_prompt
        attempts: List[StranglerAttempt] = []
        final_code = ""

        for iteration in range(1, self.max_retries + 1):
            raw_output = "".join(self.provider.stream(current_prompt))
            candidate_code = extract_code_block(raw_output)
            final_code = candidate_code

            sandbox_res = verify_refactored_code(
                raw_output,
                schema_sql=schema_sql,
                require_ledger_precision=require_ledger,
                execute_smoke_test=True,
            )

            attempts.append(
                StranglerAttempt(
                    iteration=iteration,
                    raw_response=raw_output,
                    extracted_code=candidate_code,
                    sandbox_result=sandbox_res,
                )
            )

            if sandbox_res.passed:
                return StranglerReport(
                    source_file=dep_graph.file_name,
                    success=True,
                    iterations_used=iteration,
                    final_code=candidate_code,
                    dependency_graph=dep_graph,
                    attempts=attempts,
                )

            current_prompt = self.build_repair_prompt(
                initial_prompt, candidate_code, sandbox_res
            )

        return StranglerReport(
            source_file=dep_graph.file_name,
            success=False,
            iterations_used=len(attempts),
            final_code=final_code,
            dependency_graph=dep_graph,
            attempts=attempts,
        )
