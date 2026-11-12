#!/usr/bin/env python3
"""
Live Cloud Frontier Tool-Trace Verifier (Gemini 3.8 Flash via OpenAI Endpoint)
------------------------------------------------------------------------------
"""

import ast
import json
import os
import openai
from smolagents import CodeAgent, OpenAIServerModel, tool
from smolagents.memory import ActionStep

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-api-key-here")

@tool
def extract_sql_schema(legacy_code: str) -> str:
    """Extracts tables, raw queries, and bind parameters from legacy code.

    Args:
        legacy_code: The raw legacy snippet to inspect.
    """
    return json.dumps({
        "tables": ["ledger_entries"],
        "unparameterized_queries": [
            "INSERT INTO ledger_entries (user_id, total) VALUES ($uid,$total)"
        ],
        "float_operations": ["$total = $subtotal * (1 +$tax_rate)"],
    })

@tool
def synthesize_safe_fastapi_service(schema_json: str) -> str:
    """Generates a secure FastAPI microservice using SQLAlchemy bind parameters and Decimal math.

    Args:
        schema_json: JSON string of extracted schema and rules.
    """
    return (
        "from decimal import Decimal, ROUND_HALF_UP\n"
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "@app.post('/calculate')\n"
        "def calculate_invoice_total(subtotal: Decimal, tax_rate: Decimal) -> Decimal:\n"
        "    gross = subtotal * (Decimal('1.00') + tax_rate)\n"
        "    return gross.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
    )

def extract_semantic_tool_trace(agent) -> list[str]:
    """
    Walks the Python AST inside each ActionStep.code_action to extract
    the exact sequence of semantic tool and sub-agent function calls.
    """
    known_callables = (
        set(getattr(agent, "tools", {}).keys())
        | set(getattr(agent, "managed_agents", {}).keys())
        | {"final_answer"}
    )
    trace: list[str] = []

    for step in agent.memory.steps:
        if isinstance(step, ActionStep) and getattr(step, "code_action", None):
            try:
                tree = ast.parse(step.code_action)
                # Preserve top-to-bottom source line order
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in known_callables
                ]
                calls.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
                for call_node in calls:
                    func_name = call_node.func.id  # type: ignore[attr-defined]
                    trace.append(func_name)
            except SyntaxError:
                pass
    return trace

def main():
    print("=" * 70)
    print("Connecting to Google AI Studio: gemini-3.8-flash")
    print("=" * 70)

    # 1. Create a custom OpenAI client with a 10-minute timeout and 3 retries
    custom_client = openai.OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=600.0,
        max_retries=3,
    )

    # 2. Pass it into OpenAIServerModel
    model = OpenAIServerModel(
        model_id="gemini-3.8-flash",
        client=custom_client,
        temperature=0.0,
    )

    agent = CodeAgent(
        tools=[extract_sql_schema, synthesize_safe_fastapi_service],
        model=model,
        max_steps=4,
    )

    task_prompt = (
        "Refactor this legacy billing logic:\n"
        "my $subtotal =$q->param('subtotal');\n"
        "my $tax_rate = 0.22;\n"
        "my $total = $subtotal * (1 +$tax_rate);\n"
        "my $sql = 'INSERT INTO ledger_entries (user_id, total) VALUES ($uid,$total)';\n"
        "$dbh->do($sql);\n\n"
        "First call `extract_sql_schema` to analyze the query. "
        "Then call `synthesize_safe_fastapi_service` to generate safe Python. "
        "Return the resulting code as your final answer."
    )

    result = agent.run(task_prompt)
    semantic_trace = extract_semantic_tool_trace(agent)

    print("\n" + "=" * 70)
    print("LIVE GEMINI 3.8 FLASH TELEMETRY")
    print("=" * 70)
    print(f"Semantic Tool Trajectory : {semantic_trace}")
    print(f"Steps / Iterations Used  : {len([s for s in agent.memory.steps if isinstance(s, ActionStep)])}")
    print(f"Final Answer Preview     :\n{str(result)[:200]}...")

if __name__ == "__main__":
    main()
