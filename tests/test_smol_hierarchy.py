import json
from smolagents.models import ChatMessage, MessageRole, Model

from core.providers import LLMConfig, LLMProvider
from core.smol_hierarchy import (
    SpaghettiProviderModel,
    build_spaghettilens_smol_hierarchy,
    create_spaghettilens_tools,
)


class DummyLLMProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(LLMConfig(provider="ollama", model="llama3"))
        self.last_system_prompt = None
        self.last_prompt = None

    def stream(self, prompt: str, system_prompt=None):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        yield "```python\nimport os\ndef clean():\n    return 42\n```"


class FakeSmolCodeModel(Model):
    def generate(self, messages, **kwargs):
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content='Thought: Done\n<code>\nfinal_answer("VERIFIED")\n</code>',
        )


def test_smol_hierarchy_propagates_level2_specialists_to_supervisor():
    provider = DummyLLMProvider()
    supervisor = build_spaghettilens_smol_hierarchy(
        provider=provider,
        smol_model=FakeSmolCodeModel(),
    )

    discovery_desc = supervisor.managed_agents["discovery_lead"].description
    modernization_desc = supervisor.managed_agents["modernization_lead"].description

    # Verify that the Supervisor (Level 0) sees the 3 Level 2 sub-agents (PR #3115 / Issue #1061)
    assert "dependency_graph_agent" in discovery_desc
    assert "security_invariant_agent" in discovery_desc
    assert "strangler_sandbox_agent" in modernization_desc


def test_spaghetti_provider_model_separates_system_prompt():
    provider = DummyLLMProvider()
    model = SpaghettiProviderModel(provider=provider)

    msg = model.generate(
        [
            ChatMessage(role=MessageRole.SYSTEM, content="System rules"),
            ChatMessage(role=MessageRole.USER, content="Refactor legacy file"),
        ]
    )

    assert "def clean():" in msg.content
    assert provider.last_system_prompt == "System rules"
    assert "Refactor legacy file" in provider.last_prompt


def test_spaghettilens_tools_audit_and_strangler_execution(tmp_path):
    legacy_php = tmp_path / "legacy.php"
    legacy_php.write_text("<?php $id = $_GET['id']; mysql_query('SELECT * FROM users WHERE id=' . $id); ?>")

    provider = DummyLLMProvider()
    tools = create_spaghettilens_tools(provider=provider, max_retries=1)

    audit_json = tools["audit"](file_path=str(legacy_php))
    audit_data = json.loads(audit_json)
    assert audit_data["language"] == "PHP"

    strangler_json = tools["strangler"](file_path=str(legacy_php))
    strangler_data = json.loads(strangler_json)
    assert strangler_data["success"] is True
    assert "def clean():" in strangler_data["final_code"]


def test_spaghetti_provider_model_preserves_code_tags_with_stop_sequences_and_empty_fallback():
    class StopSeqProvider(LLMProvider):
        def __init__(self, response_text: str) -> None:
            super().__init__(LLMConfig(provider="npu", model="qwen3-4b-instruct-2507"))
            self.response_text = response_text

        def stream(self, prompt: str, system_prompt=None):
            yield self.response_text

    # Case 1: stop_sequences=["</code>"] must NOT strip </code>
    model_with_tags = SpaghettiProviderModel(
        provider=StopSeqProvider('Thought: Run audit\n<code>\nfinal_answer("OK")\n</code>\nExtra')
    )
    res1 = model_with_tags.generate(
        [ChatMessage(role=MessageRole.USER, content="Go")],
        stop_sequences=["</code>", "Observation:"],
    )
    assert "<code>" in res1.content and "</code>" in res1.content

    # Case 2: Markdown ```python ... ``` converted to <code>...</code>
    model_md = SpaghettiProviderModel(
        provider=StopSeqProvider('Thought: Done\n```python\nfinal_answer("MD_OK")\n```')
    )
    res2 = model_md.generate([ChatMessage(role=MessageRole.USER, content="Go")])
    assert "<code>\nfinal_answer(\"MD_OK\")\n</code>" in res2.content

    # Case 3: Empty NPU output gracefully falls back to valid <code> block
    model_empty = SpaghettiProviderModel(provider=StopSeqProvider(""))
    res3 = model_empty.generate([ChatMessage(role=MessageRole.USER, content="Go")])
    assert "<code>" in res3.content and "</code>" in res3.content


def test_sanitize_python_code_body_repairs_npu_log_regressions():
    from core.smol_hierarchy import _normalize_code_agent_output

    # Regression 1 from spaghetti.log: stubbing tool with `def ...: pass` + raw markdown lines
    raw_step1 = (
        "Thought: Extract graph\n"
        "<code>\n"
        "def extract_static_dependency_graph(file_path: str, schema_path: str) -> str:\n"
        '    """Builds the static dependency and invariant graph (JSON)."""\n'
        "    pass\n\n"
        "dependency_graph = extract_static_dependency_graph(file_path='spaghettiCode.php', schema_path='fixtures/schema.sql')\n"
        "### 1. Task outcome (short version):\n"
        "The dependency graph for spaghettiCode.php has been extracted.\n"
        'final_answer("Extracted")\n'
        "</code>"
    )
    norm1 = _normalize_code_agent_output(raw_step1)
    assert "def extract_static_dependency_graph" not in norm1
    assert "The dependency graph for spaghettiCode.php has been extracted." not in norm1
    assert "dependency_graph = extract_static_dependency_graph(" in norm1

    # Regression 2 from spaghetti.log: quadruple quotes `""""`
    raw_quad = 'Thought: Done\n<code>\nfinal_answer(\n""""\n### 1. Task outcome:\nSafe\n"""")\n</code>'
    norm2 = _normalize_code_agent_output(raw_quad)
    assert '""""' not in norm2
    assert "final_answer(" in norm2

    # Regression 3 from spaghetti.log: bare string literal expression without final_answer()
    raw_bare_str = 'Thought: Summary\n<code>\n"The dependency graph reveals a complex network."\n</code>'
    norm3 = _normalize_code_agent_output(raw_bare_str)
    assert 'final_answer("The dependency graph reveals a complex network.")' in norm3

    # Regression 4 from spaghetti.log: truncated/unterminated final_answer("...
    raw_trunc = 'Thought: Returning\n<code>\nfinal_answer("Thought: I have extracted the graph\n\nThe dependency'
    norm4 = _normalize_code_agent_output(raw_trunc)
    assert "<code>" in norm4 and "</code>" in norm4
    assert "final_answer(" in norm4


def test_strict_prompt_templates_eliminate_three_section_prose_template():
    provider = DummyLLMProvider()
    supervisor = build_spaghettilens_smol_hierarchy(
        provider=provider,
        smol_model=FakeSmolCodeModel(),
    )

    for agent_name in ("discovery_lead", "modernization_lead"):
        lead = supervisor.managed_agents[agent_name]
        assert "strict" in lead.system_prompt and "Python" in lead.system_prompt
        assert "### 1. Task outcome" not in lead.prompt_templates["managed_agent"]["task"]
        for sub_agent in lead.managed_agents.values():
            assert "strict" in sub_agent.system_prompt and "Python" in sub_agent.system_prompt
            assert "### 1. Task outcome" not in sub_agent.prompt_templates["managed_agent"]["task"]


def test_managed_agent_def_stubs_and_snake_case_filename_resolved(tmp_path):
    from core.smol_hierarchy import _normalize_code_agent_output

    # 1. Stubs of managed agents (`def dependency_graph_agent...`) must be stripped
    stubbed_lead_code = (
        "<code>\n"
        "def dependency_graph_agent(task: str, additional_args: dict = {}) -> str:\n"
        '    """Extracts the static dependency graph."""\n'
        "    pass\n\n"
        "dep_res = dependency_graph_agent(task='Extract graph')\n"
        "final_answer(str(dep_res))\n"
        "</code>"
    )
    normalized = _normalize_code_agent_output(stubbed_lead_code)
    assert "def dependency_graph_agent" not in normalized
    assert "dep_res = dependency_graph_agent(" in normalized

    # 2. snake_case `spaghetti_code.php` resolves to `spaghettiCode.php` fallback
    real_file = tmp_path / "spaghettiCode.php"
    real_file.write_text("<?php $id = $_GET['id']; mysql_query('SELECT * FROM t WHERE id=' . $id); ?>")

    provider = DummyLLMProvider()
    tools = create_spaghettilens_tools(
        provider=provider,
        max_retries=1,
        default_file_path=str(real_file),
    )
    graph_json = tools["graph"](file_path="spaghetti_code.php")
    graph_data = json.loads(graph_json)
    assert graph_data["file_name"] == "spaghettiCode.php"


def test_ledger_code_agent_guarded_executor_preserves_executor_interface():
    from smolagents import tool
    from smolagents.local_python_executor import CodeOutput
    from core.smol_hierarchy import LedgerCodeAgent, _GuardedPythonExecutor

    @tool
    def ping(val: str) -> str:
        """Return val.

        Args:
            val: input string
        """
        return f"pong:{val}"

    class _RunModel(Model):
        def __init__(self) -> None:
            super().__init__(model_id="dummy")
            self.calls = 0

        def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content='Thought: call ping\n<code>\nres = ping(val="a")\n</code>',
                )
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content='Thought: finish\n<code>\nfinal_answer("ok")\n</code>',
            )

    agent = LedgerCodeAgent(tools=[ping], model=_RunModel(), name="guarded_test_agent")
    assert isinstance(agent.python_executor, _GuardedPythonExecutor)
    assert hasattr(agent.python_executor, "send_variables")
    assert hasattr(agent.python_executor, "send_tools")

    result = agent.run("run ping and finish")
    assert result == "ok"

    # Duplicate static call must short-circuit with a CodeOutput object
    dup_out = agent.python_executor('res = ping(val="a")')
    assert isinstance(dup_out, CodeOutput)
    assert dup_out.is_final_answer is False
    assert "Skipped duplicate tool call(s)" in dup_out.logs


def test_normalize_code_agent_output_repairs_additional_args_typo():
    from core.smol_hierarchy import _normalize_code_agent_output

    raw = (
        "<code>\n"
        "sec_res = security_invariant_agent(task='Audit security', additionalorary_args={'file_path': 'x.pl'})\n"
        "</code>"
    )
    normalized = _normalize_code_agent_output(raw)
    assert "additionalorary_args" not in normalized
    assert "additional_args={'file_path': 'x.pl'}" in normalized





