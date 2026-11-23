from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path
from typing import Any, Optional

from smolagents import ActionStep, CodeAgent, Tool, tool
from smolagents.agents import EMPTY_PROMPT_TEMPLATES, PromptTemplates
from smolagents.local_python_executor import CodeOutput
from smolagents.models import ChatMessage, MessageRole, Model

from core.call_ledger import CallLedger
from core.providers import LLMProvider
from core.sandbox_runner import verify_refactored_code
from core.schema_graph import build_dependency_graph
from core.strangler_agent import StranglerAgent

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
NPURUN_LOG_RE = re.compile(
    r"^.*?\b(?:INFO|WARN|DEBUG)\s+(?:npurun_core\S*|qnn\S*):.*$",
    re.MULTILINE,
)
MARKDOWN_CODE_FENCE_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
CODE_TAG_RE = re.compile(r"<code>(.*?)</code>", re.DOTALL)
TOOL_DEF_STUB_RE = re.compile(
    r"^\s*def\s+(?:extract_static_dependency_graph|audit_security_and_ledger_invariants|"
    r"execute_strangler_refactoring|run_standalone_sandbox_check|"
    r"dependency_graph_agent|security_invariant_agent|strangler_sandbox_agent|"
    r"discovery_lead|modernization_lead)\s*\([^)]*\)\s*(?:->\s*[^:]+)?:\s*\n"
    r"(?:\s+(?:\"\"\".*?\"\"\"|'''.*?'''|pass|#.*)\s*\n)+",
    re.MULTILINE | re.DOTALL,
)

DEFAULT_TOOL_ARG_ALIASES: dict[str, tuple[str, ...]] = {
    "extract_static_dependency_graph": ("file_path", "schema_path"),
    "audit_security_and_ledger_invariants": ("file_path", "schema_path"),
    "execute_strangler_refactoring": ("file_path", "schema_path"),
    "run_standalone_sandbox_check": (
        "candidate_python_code",
        "require_ledger_precision",
        "schema_path",
    ),
    "dependency_graph_agent": ("task", "additional_args"),
    "security_invariant_agent": ("task", "additional_args"),
    "strangler_sandbox_agent": ("task", "additional_args"),
    "discovery_lead": ("task", "additional_args"),
    "modernization_lead": ("task", "additional_args"),
}


def _strip_npu_noise(text: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", text)
    cleaned = NPURUN_LOG_RE.sub("", cleaned)
    return cleaned.strip()


def _summarize_step_observation(observations: Any, max_len: int = 56) -> str:
    if observations is None:
        return ""
    compact = re.sub(r"\s+", " ", str(observations)).strip()
    if not compact:
        return ""
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."


def _sanitize_python_code_body(code_body: str) -> str:
    """
    Repairs common small-model / NPU code generation bugs inside a <code>...</code> block:
    1. Strips `def <tool_name>(...): pass` stub re-definitions that shadow real smolagents tools.
    2. Strips raw Markdown lines (e.g. `### 1. Task outcome...`, `- **SQL...`) mixed outside strings.
    3. Repairs quadruple quotes and unterminated `final_answer(...)` string literals.
    4. Wraps bare string-literal expressions into `final_answer(...)`.
    """
    cleaned = TOOL_DEF_STUB_RE.sub("", code_body).strip()
    cleaned = cleaned.replace('""""', '"""')
    cleaned = re.sub(r"\badditional[a-z_]*_args\s*=", "additional_args=", cleaned)

    try:
        tree = ast.parse(cleaned)
        if (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            return f"final_answer({json.dumps(tree.body[0].value.value)})"
        return cleaned
    except SyntaxError:
        pass

    kept_lines: list[str] = []
    in_final_answer = False
    final_answer_buf: list[str] = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if in_final_answer:
            final_answer_buf.append(line)
            continue
        if stripped.startswith("final_answer("):
            in_final_answer = True
            final_answer_buf.append(line)
            continue
        if not stripped or stripped.startswith("#"):
            kept_lines.append(line)
            continue
        try:
            ast.parse(stripped)
            kept_lines.append(line)
        except SyntaxError:
            continue

    if final_answer_buf:
        raw_fa = "\n".join(final_answer_buf).strip()
        try:
            ast.parse(raw_fa)
            kept_lines.append(raw_fa)
        except SyntaxError:
            inner = re.sub(r"^final_answer\s*\(\s*", "", raw_fa) 
            inner = re.sub(r"\s*\)\s*$", "", inner)
            inner = inner.strip("\"' \n\t")
            kept_lines.append(f"final_answer({json.dumps(inner or 'Completed.')})")

    candidate = "\n".join(kept_lines).strip()
    if candidate:
        try:
            tree = ast.parse(candidate)
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                return f"final_answer({json.dumps(tree.body[0].value.value)})"
            return candidate
        except SyntaxError:
            pass

    return f"final_answer({json.dumps(cleaned)})"


def _normalize_code_agent_output(output: str) -> str:
    """
    Ensures the LLM response contains a valid, AST-parseable `<code>...</code>` block:
    1. Converts ```python ... ``` markdown fences into <code>...</code> if missing.
    2. Closes unclosed <code> tags caused by stop_sequences or max_tokens truncation.
    3. Sanitizes the Python body inside <code>...</code> to prevent SyntaxErrors and tool-shadowing.
    """
    text = output.strip()
    if not text:
        return 'Thought: Completed.\n<code>\nfinal_answer("Task completed.")\n</code>'

    if "<code>" in text:
        if "</code>" not in text:
            text = f"{text}\n</code>"
        match = CODE_TAG_RE.search(text)
        if match:
            sanitized_body = _sanitize_python_code_body(match.group(1))
            prefix = text[: match.start()].strip() or "Thought: Executing step."
            return f"{prefix}\n<code>\n{sanitized_body}\n</code>"
        return text

    fence_match = MARKDOWN_CODE_FENCE_RE.search(text)
    if fence_match:
        code_body = _sanitize_python_code_body(fence_match.group(1).strip())
        prefix = text[: fence_match.start()].strip()
        thought = prefix if prefix else "Thought: Executing code step."
        if not thought.lower().startswith("thought:"):
            thought = f"Thought: {thought}"
        return f"{thought}\n<code>\n{code_body}\n</code>"

    code_indicators = (
        "final_answer(",
        "extract_static_dependency_graph(",
        "audit_security_and_ledger_invariants(",
        "execute_strangler_refactoring(",
        "run_standalone_sandbox_check(",
        "dependency_graph_agent(",
        "security_invariant_agent(",
        "strangler_sandbox_agent(",
        "discovery_lead(",
        "modernization_lead(",
    )
    if any(ind in text for ind in code_indicators):
        lines = text.splitlines()
        thought_lines: list[str] = []
        code_lines: list[str] = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if not in_code and (
                any(ind in stripped for ind in code_indicators)
                or re.match(r"^[a-zA-Z_]\w*\s*=", stripped)
                or stripped.startswith(("import ", "from ", "print(", "def "))
            ):
                in_code = True
            if in_code:
                code_lines.append(line)
            else:
                thought_lines.append(line)

        thought_str = "\n".join(thought_lines).strip() or "Thought: Executing step."
        if not thought_str.lower().startswith("thought:"):
            thought_str = f"Thought: {thought_str}"
        code_str = _sanitize_python_code_body("\n".join(code_lines).strip())
        return f"{thought_str}\n<code>\n{code_str}\n</code>"

    safe_literal = json.dumps(text)
    return f"Thought: Returning final answer.\n<code>\nfinal_answer({safe_literal})\n</code>"


class SpaghettiProviderModel(Model):
    """Adapts SpaghettiLens-AI's LLMProvider to the smolagents.Model interface."""

    def __init__(self, provider: LLMProvider, model_id: Optional[str] = None, **kwargs: Any) -> None:
        resolved_id = model_id or getattr(getattr(provider, "config", None), "model", "spaghettilens-llm")
        super().__init__(model_id=resolved_id, **kwargs)
        self.provider = provider

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict) and "text" in part
            )
        return str(content or "")

    def generate(
        self,
        messages: list[ChatMessage | dict],
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatMessage:
        system_parts: list[str] = []
        conversation_parts: list[str] = []

        # Sliding window: retain the system prompt and only the last 4 messages to stay within the NPU's 4096-token limit
        trimmed_messages = messages if len(messages) <= 4 else [messages[0]] + messages[-3:]

        for msg in trimmed_messages:
            role = msg.role if isinstance(msg, ChatMessage) else msg.get("role", "user")
            raw_content = msg.content if isinstance(msg, ChatMessage) else msg.get("content", "")
            text = self._extract_text(raw_content).strip()
            if not text:
                continue

            role_str = str(role.value if hasattr(role, "value") else role).lower()
            if role_str == "system":
                system_parts.append(text)
            else:
                conversation_parts.append(f"[{role_str.upper()}]\n{text}")

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        user_prompt = "\n\n".join(conversation_parts)

        output = _strip_npu_noise(self.provider.generate(user_prompt, system_prompt=system_prompt))

        # Progressive fallback if the prompt exceeds the NPU context window and returns an empty string
        if not output and len(conversation_parts) > 1:
            compact_user_prompt = conversation_parts[0] + "\n\n" + conversation_parts[-1]
            output = _strip_npu_noise(
                self.provider.generate(compact_user_prompt, system_prompt=system_prompt)
            )
        if not output and conversation_parts:
            short_system = (
                "You are a Python CodeAgent. Always respond with Thought: ... followed by "
                "<code>\nfinal_answer(\"...\")\n</code>."
            )
            output = _strip_npu_noise(
                self.provider.generate(conversation_parts[-1][-1500:], system_prompt=short_system)
            )

        if stop_sequences:
            for stop_seq in stop_sequences:
                if stop_seq in output:
                    if stop_seq.strip() == "</code>":
                        output = output.split(stop_seq)[0] + "\n</code>"
                    else:
                        output = output.split(stop_seq)[0]

        output = _normalize_code_agent_output(output)
        return ChatMessage(role=MessageRole.ASSISTANT, content=output)


class _GuardedPythonExecutor:
    """Wraps a smolagents PythonExecutor to short-circuit duplicate static calls while preserving executor methods."""

    def __init__(self, raw_executor: Any, call_ledger: CallLedger) -> None:
        self._raw = raw_executor
        self._call_ledger = call_ledger

    def __call__(self, code_action: str, *exec_args: Any, **exec_kwargs: Any) -> Any:
        skip, skip_msg = self._call_ledger.should_short_circuit(code_action)
        if skip:
            return CodeOutput(output=skip_msg, logs=skip_msg, is_final_answer=False)
        return self._raw(code_action, *exec_args, **exec_kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)


class LedgerCodeAgent(CodeAgent):
    """
    CodeAgent subclass equipped with an out-of-window CallLedger:
    1. Injects a compact digest of executed tool/sub-agent calls into the sliding window.
    2. Short-circuits redundant static calls that already succeeded earlier in the run.
    3. Records completed ActionSteps via step_callbacks.
    """

    def __init__(
        self,
        *args: Any,
        enable_duplicate_guard: bool = True,
        max_digest_entries: int = 8,
        max_digest_chars: int = 420,
        **kwargs: Any,
    ) -> None:
        user_callbacks = dict(kwargs.pop("step_callbacks", None) or {})
        existing_action_cb = user_callbacks.get(ActionStep)

        def _on_action_step(step: ActionStep, agent: CodeAgent) -> None:
            if getattr(step, "code_action", None):
                status = "ERROR" if getattr(step, "error", None) else "OK"
                summary = _summarize_step_observation(getattr(step, "observations", None))
                self.call_ledger.record_step(
                    step_num=getattr(step, "step_number", 0),
                    code_action=step.code_action,
                    status=status,
                    outcome_summary=summary,
                )
            if callable(existing_action_cb):
                existing_action_cb(step, agent)

        user_callbacks[ActionStep] = _on_action_step
        super().__init__(*args, step_callbacks=user_callbacks, **kwargs)

        registered_names: set[str] = set()
        if getattr(self, "tools", None):
            registered_names.update(self.tools.keys())
        if getattr(self, "managed_agents", None):
            registered_names.update(self.managed_agents.keys())

        self.call_ledger = CallLedger(
            registered_names=registered_names,
            arg_aliases=DEFAULT_TOOL_ARG_ALIASES,
            max_digest_entries=max_digest_entries,
            max_digest_chars=max_digest_chars,
        )
        self.enable_duplicate_guard = enable_duplicate_guard

        if self.enable_duplicate_guard and getattr(self, "python_executor", None) is not None:
            self.python_executor = _GuardedPythonExecutor(
                raw_executor=self.python_executor,
                call_ledger=self.call_ledger,
            )

    def write_memory_to_messages(self, summary_mode: bool = False) -> list[ChatMessage | dict]:
        messages = super().write_memory_to_messages(summary_mode=summary_mode)
        digest = self.call_ledger.format_digest()
        if not digest or len(messages) < 2:
            return messages

        ledger_msg = ChatMessage(
            role=MessageRole.USER,
            content=[{"type": "text", "text": digest}],
        )
        # Keep system prompt (messages[0]) + task prompt (messages[1]), inject compact ledger,
        # and retain the latest 2 messages so total length stays <= 5 and survives provider trimming.
        if len(messages) <= 3:
            return [messages[0], messages[1], ledger_msg] + messages[2:]
        return [messages[0], messages[1], ledger_msg] + messages[-2:]


def _iter_hierarchy_agents(root_agent: CodeAgent) -> list[CodeAgent]:
    """Depth-first traversal over root supervisor, team leads, and specialists."""
    visited: set[int] = set()
    ordered: list[CodeAgent] = []

    def _visit(agent: CodeAgent) -> None:
        if id(agent) in visited:
            return
        visited.add(id(agent))
        ordered.append(agent)
        managed = getattr(agent, "managed_agents", None) or {}
        for sub in managed.values():
            _visit(sub)

    _visit(root_agent)
    return ordered


def reset_hierarchy_ledgers(root_agent: CodeAgent) -> None:
    """Clears CallLedger state across all tiers in the hierarchy between runs."""
    for agent in _iter_hierarchy_agents(root_agent):
        ledger = getattr(agent, "call_ledger", None)
        if isinstance(ledger, CallLedger):
            ledger.clear()


def get_hierarchy_ledger_digests(root_agent: CodeAgent) -> dict[str, str]:
    """Returns non-empty CallLedger digests keyed by agent name for observability/debugging."""
    digests: dict[str, str] = {}
    for agent in _iter_hierarchy_agents(root_agent):
        ledger = getattr(agent, "call_ledger", None)
        if isinstance(ledger, CallLedger):
            digest = ledger.format_digest()
            if digest:
                digests[getattr(agent, "name", "unknown_agent")] = digest
    return digests


def _resolve_legacy_path(file_path: str, fallback_path: str = "") -> Path:
    """
    Resolves the legacy file path even if the NPU model converts camelCase to snake_case
    (e.g., 'spaghetti_code.php' -> 'spaghettiCode.php').
    """
    path = Path(file_path)
    if path.is_file():
        return path
    if (Path("fixtures") / file_path).is_file():
        return Path("fixtures") / file_path
    if fallback_path and Path(fallback_path).is_file():
        return Path(fallback_path)
    if fallback_path and (Path("fixtures") / fallback_path).is_file():
        return Path("fixtures") / fallback_path

    search_dirs = [path.parent if str(path.parent) != "" else Path("."), Path("fixtures")]
    normalized_target = re.sub(r"[_\-\s]", "", path.name).lower()
    for search_dir in search_dirs:
        if search_dir.is_dir():
            for candidate in search_dir.iterdir():
                if candidate.is_file() and re.sub(r"[_\-\s]", "", candidate.name).lower() == normalized_target:
                    return candidate
    return path


def create_spaghettilens_tools(
    provider: LLMProvider,
    max_retries: int = 3,
    default_file_path: str = "fixtures/spaghettiCode.php",
    default_schema_path: str = "fixtures/schema.sql",
) -> dict[str, Tool]:
    """Exposes SpaghettiLens-AI's neuro-symbolic modules as smolagents tools."""

    @tool
    def extract_static_dependency_graph(file_path: str, schema_path: str = "") -> str:
        """
        Builds the static dependency and invariant graph (JSON) for a legacy PHP or Perl file.

        Args:
            file_path: Path to the legacy source file (.php or .pl).
            schema_path: Optional path to a SQL schema file (.sql). Leave empty if not applicable.
        """
        path = _resolve_legacy_path(file_path, default_file_path)
        if not path.is_file():
            return f"Error: File '{file_path}' does not exist."
        code = path.read_text(encoding="utf-8", errors="replace")
        resolved_schema = schema_path or default_schema_path
        schema_sql: Optional[str] = None
        if resolved_schema and Path(resolved_schema).is_file():
            schema_sql = Path(resolved_schema).read_text(encoding="utf-8", errors="replace")
        dep_graph = build_dependency_graph(code, str(path), schema_sql=schema_sql)
        return dep_graph.to_json()

    @tool
    def audit_security_and_ledger_invariants(file_path: str, schema_path: str = "") -> str:
        """
        Audits a legacy PHP or Perl file for SQL injection, tainted inputs, deprecated modules,
        and LEDGER_INVARIANT currency precision requirements.

        Args:
            file_path: Path to the legacy source file (.php or .pl).
            schema_path: Optional path to a SQL schema file (.sql). Leave empty if not applicable.
        """
        path = _resolve_legacy_path(file_path, default_file_path)
        if not path.is_file():
            return f"Error: File '{file_path}' does not exist."
        code = path.read_text(encoding="utf-8", errors="replace")
        resolved_schema = schema_path or default_schema_path
        schema_sql: Optional[str] = None
        if resolved_schema and Path(resolved_schema).is_file():
            schema_sql = Path(resolved_schema).read_text(encoding="utf-8", errors="replace")

        dep_graph = build_dependency_graph(code, str(path), schema_sql=schema_sql)
        require_ledger = any(
            "LEDGER_INVARIANT" in finding
            for finding in dep_graph.security_and_invariant_findings
        )
        return json.dumps(
            {
                "file_name": dep_graph.file_name,
                "language": dep_graph.language,
                "require_ledger_decimal_precision": require_ledger,
                "security_and_invariant_findings": dep_graph.security_and_invariant_findings,
            },
            indent=2,
        )

    @tool
    def execute_strangler_refactoring(file_path: str, schema_path: str = "") -> str:
        """
        Executes the neuro-symbolic StranglerAgent loop with deterministic sandbox verification
        and self-healing, returning the refactored Python 3.11+ code and sandbox report.

        Args:
            file_path: Path to the legacy source file (.php or .pl).
            schema_path: Optional path to a SQL schema file (.sql). Leave empty if not applicable.
        """
        path = _resolve_legacy_path(file_path, default_file_path)
        if not path.is_file():
            return f"Error: File '{file_path}' does not exist."
        code = path.read_text(encoding="utf-8", errors="replace")
        resolved_schema = schema_path or default_schema_path
        schema_sql: Optional[str] = None
        if resolved_schema and Path(resolved_schema).is_file():
            schema_sql = Path(resolved_schema).read_text(encoding="utf-8", errors="replace")

        agent = StranglerAgent(provider=provider, max_retries=max_retries)
        report = agent.run(code, str(path), schema_sql=schema_sql)

        return json.dumps(
            {
                "source_file": report.source_file,
                "success": report.success,
                "iterations_used": report.iterations_used,
                "attempts": [
                    {
                        "iteration": a.iteration,
                        "passed": a.sandbox_result.passed,
                        "errors": a.sandbox_result.errors,
                    }
                    for a in report.attempts
                ],
                "final_code": report.final_code,
            },
            indent=2,
        )

    @tool
    def run_standalone_sandbox_check(
        candidate_python_code: str,
        require_ledger_precision: bool = False,
        schema_path: str = "",
    ) -> str:
        """
        Verifies a candidate Python 3 code snippet inside the deterministic sandbox runner
        (checking AST rules, SQL injection patterns, Decimal ledger invariants, and smoke tests).

        Args:
            candidate_python_code: Python 3 code (raw or inside a ```python block) to validate.
            require_ledger_precision: Set True if LEDGER_INVARIANT requires decimal.Decimal.
            schema_path: Optional path to a SQL schema file (.sql). Leave empty if not applicable.
        """
        schema_sql: Optional[str] = None
        if schema_path and Path(schema_path).is_file():
            schema_sql = Path(schema_path).read_text(encoding="utf-8", errors="replace")

        res = verify_refactored_code(
            candidate_python_code,
            schema_sql=schema_sql,
            require_ledger_precision=require_ledger_precision,
            execute_smoke_test=True,
        )
        return json.dumps(
            {
                "passed": res.passed,
                "errors": res.errors,
                "feedback": res.to_feedback_prompt() if not res.passed else "SANDBOX_PASSED",
            },
            indent=2,
        )

    return {
        "graph": extract_static_dependency_graph,
        "audit": audit_security_and_ledger_invariants,
        "strangler": execute_strangler_refactoring,
        "sandbox": run_standalone_sandbox_check,
    }


def build_strict_prompt_templates() -> PromptTemplates:
    """
    Overrides smolagents' verbose default system_prompt and 3-section `managed_agent.task`
    template, turning agents into pure Python code executors compatible with the NPU's
    compact context window.
    """
    templates = copy.deepcopy(EMPTY_PROMPT_TEMPLATES)
    templates["system_prompt"] = (
        "You are a strict, silent Python code executor. You have access to tools.\n"
        "CRITICAL RULES:\n"
        "1. NEVER output conversational text, Markdown, or explanations. Do not write 'Thought:' or 'Summary:'.\n"
        "2. Your entire output MUST be exactly one Python <code>...</code> block.\n"
        "3. In Step 1, call your tool and print the result.\n"
        "4. In Step 2, call `final_answer(str(result))` to return the data.\n\n"
        "Available Python Tools:\n"
        "{{code_block_opening_tag}}\n"
        "{%- for tool in tools.values() %}\n"
        "{{ tool.to_code_prompt() }}\n"
        "{% endfor %}\n"
        "{{code_block_closing_tag}}\n\n"
        "{%- if managed_agents and managed_agents.values() | list %}\n"
        "Available Managed Agents (call like Python functions):\n"
        "{{code_block_opening_tag}}\n"
        "{%- for agent in managed_agents.values() %}\n"
        "def {{ agent.name }}(task: str, additional_args: dict[str, Any] = {}) -> str:\n"
        '    """{{ agent.description }}"""\n'
        "{% endfor %}\n"
        "{{code_block_closing_tag}}\n"
        "{%- endif %}\n"
        "Authorized imports: {{authorized_imports}}\n"
        "{%- if custom_instructions %}\n"
        "{{custom_instructions}}\n"
        "{%- endif %}\n"
    )
    templates["managed_agent"]["task"] = (
        "You are agent '{{name}}'. Execute this task using Python code inside <code>...</code>:\n"
        "Task: {{task}}\n"
        "Call your assigned tool or managed agent first, print the output, and pass the result as a single string to `final_answer`."
    )
    templates["managed_agent"]["report"] = (
        "Output from '{{name}}':\n{{final_answer}}"
    )
    return templates


def build_spaghettilens_smol_hierarchy(
    provider: LLMProvider,
    model_name: Optional[str] = None,
    max_retries: int = 3,
    smol_model: Optional[Model] = None,
    execution_timeout: int = 1800,
    default_file_path: str = "fixtures/spaghettiCode.php",
    default_schema_path: str = "fixtures/schema.sql",
    enable_duplicate_guard: bool = True,
) -> LedgerCodeAgent:
    llm = smol_model or SpaghettiProviderModel(provider=provider, model_id=model_name)
    tools_map = create_spaghettilens_tools(
        provider=provider,
        max_retries=max_retries,
        default_file_path=default_file_path,
        default_schema_path=default_schema_path,
    )
    authorized_imports = ["json", "re"]
    exec_cfg = {"timeout_seconds": execution_timeout}
    strict_templates = build_strict_prompt_templates()

    concise_rule = (
        "\nCRITICAL SYNTAX RULES FOR CODE AND FINAL ANSWER:\n"
        "1. Always wrap your Python code inside <code>...</code> tags.\n"
        "2. NEVER define functions with `def ...` — all tools are already imported and ready to call.\n"
        "3. Call `final_answer` with a single string argument.\n"
        "4. NEVER pass multiple arguments separated by commas to `final_answer`.\n"
    )

    # ── LEVEL 2: Specialists ────────────────────────────────────────────────
    dependency_graph_agent = LedgerCodeAgent(
        name="dependency_graph_agent",
        description="Extracts the static dependency graph, SQL queries, HTTP inputs, and table references from legacy code.",
        tools=[tools_map["graph"]],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=4,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "Execute this exact code in Step 1:\n"
            "<code>\n"
            f"res = extract_static_dependency_graph(file_path='{default_file_path}', schema_path='{default_schema_path}')\n"
            "final_answer(res)\n"
            "</code>"
            + concise_rule
        ),
    )

    security_invariant_agent = LedgerCodeAgent(
        name="security_invariant_agent",
        description="Audits security vulnerabilities (SQLi, XSS, hardcoded secrets) and ledger decimal invariants.",
        tools=[tools_map["audit"]],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=4,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "Execute this exact code in Step 1:\n"
            "<code>\n"
            f"res = audit_security_and_ledger_invariants(file_path='{default_file_path}', schema_path='{default_schema_path}')\n"
            "final_answer(res)\n"
            "</code>"
            + concise_rule
        ),
    )

    strangler_sandbox_agent = LedgerCodeAgent(
        name="strangler_sandbox_agent",
        description="Executes the Strangler Fig refactoring into Python 3.11+ and verifies it in the deterministic sandbox.",
        tools=[tools_map["strangler"], tools_map["sandbox"]],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=4,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "Execute this exact code in Step 1:\n"
            "<code>\n"
            f"res = execute_strangler_refactoring(file_path='{default_file_path}', schema_path='{default_schema_path}')\n"
            "final_answer(res)\n"
            "</code>"
            + concise_rule
        ),
    )

    # ── LEVEL 1: Team Leads ─────────────────────────────────────────────────
    discovery_lead = LedgerCodeAgent(
        name="discovery_lead",
        description="Team Lead that coordinates dependency_graph_agent and security_invariant_agent to audit legacy files.",
        tools=[],
        managed_agents=[dependency_graph_agent, security_invariant_agent],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=5,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "You are the Discovery Team Lead. You must only execute this exact code in Step 1:\n"
            "<code>\n"
            f"dep_res = dependency_graph_agent(task='Extract graph', additional_args={{'file_path': '{default_file_path}'}})\n"
            f"sec_res = security_invariant_agent(task='Audit security', additional_args={{'file_path': '{default_file_path}'}})\n"
            "print(dep_res, sec_res)\n"
            "final_answer(str(dep_res) + '\\n' + str(sec_res))\n"
            "</code>\n"
            "Do not write any other text."
        ),
    )

    modernization_lead = LedgerCodeAgent(
        name="modernization_lead",
        description="Team Lead that delegates legacy code refactoring and deterministic sandbox verification to strangler_sandbox_agent.",
        tools=[],
        managed_agents=[strangler_sandbox_agent],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=5,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "You are the Modernization Team Lead. You must only execute this exact code in Step 1:\n"
            "<code>\n"
            f"sandbox_res = strangler_sandbox_agent(task='Refactor and verify in sandbox', additional_args={{'file_path': '{default_file_path}', 'schema_path': '{default_schema_path}'}})\n"
            "print(sandbox_res)\n"
            "final_answer(str(sandbox_res))\n"
            "</code>\n"
            "Do not write any other text."
        ),
    )

    # ── LEVEL 0: Root Supervisor ────────────────────────────────────────────
    supervisor = LedgerCodeAgent(
        name="spaghettilens_supervisor",
        description="Root orchestrator for SpaghettiLens-AI hierarchical legacy modernization.",
        tools=[],
        managed_agents=[discovery_lead, modernization_lead],
        model=llm,
        prompt_templates=copy.deepcopy(strict_templates),
        max_steps=6,
        additional_authorized_imports=authorized_imports,
        executor_kwargs=exec_cfg,
        enable_duplicate_guard=enable_duplicate_guard,
        instructions=(
            "You are the SpaghettiLens-AI Root Supervisor. You must only execute this exact code in Step 1:\n"
            "<code>\n"
            f"disc_res = discovery_lead(task='Audit security and dependency graph', additional_args={{'file_path': '{default_file_path}'}})\n"
            f"mod_res = modernization_lead(task='Execute Strangler refactoring and sandbox verification', additional_args={{'file_path': '{default_file_path}', 'schema_path': '{default_schema_path}'}})\n"
            "print(disc_res, mod_res)\n"
            "final_answer(str(disc_res) + '\\n\\n' + str(mod_res))\n"
            "</code>\n"
            "Do not write any other text."
        ),
    )

    # Ensure Level 2 sub-agent capabilities are propagated to Level 1 descriptions
    # even when running against upstream PyPI smolagents without PR #3115 merged yet.
    for lead in supervisor.managed_agents.values():
        if getattr(lead, "managed_agents", None):
            sub_desc = "\n".join(
                f"  - {k}: {v.description}" for k, v in lead.managed_agents.items()
            )
            delegation_note = (
                f"\n\nThis agent can internally delegate to the following sub-agents:\n{sub_desc}"
            )
            if delegation_note not in lead.description:
                lead.description += delegation_note

    # Convenience helpers attached to root supervisor for multi-run benchmarks
    supervisor.reset_ledgers = lambda: reset_hierarchy_ledgers(supervisor)  # type: ignore[attr-defined]
    supervisor.get_ledger_digests = lambda: get_hierarchy_ledger_digests(supervisor)  # type: ignore[attr-defined]

    return supervisor


build_spaghettilens_hierarchy = build_spaghettilens_smol_hierarchy
