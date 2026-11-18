from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

CallStatus = Literal["OK", "ERROR", "SKIPPED"]


@dataclass(frozen=True)
class ExtractedCall:
    """Single registered tool or sub-agent invocation parsed from code_action."""

    name: str
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]
    arg_fingerprint: str
    is_static: bool

    def format_signature(self, max_val_len: int = 36) -> str:
        parts: list[str] = []
        for val in self.args:
            parts.append(_truncate_repr(val, max_val_len))
        for k, val in self.kwargs:
            parts.append(f"{k}={_truncate_repr(val, max_val_len)}")
        return f"{self.name}({', '.join(parts)})"


@dataclass
class LedgerEntry:
    """Aggregated record of a normalized tool invocation across agent steps."""

    first_step: int
    last_step: int
    call: ExtractedCall
    status: CallStatus = "OK"
    outcome_summary: str = ""
    hit_count: int = 1


def _ast_node_to_literal(node: ast.AST) -> tuple[Any, bool]:
    """Convert an AST argument node into a canonical Python value if static.

    Returns (value, is_static). Dynamic expressions (Name, Call, Subscript, etc.)
    return a structural placeholder with is_static=False so we never falsely
    deduplicate calls that depend on runtime variables.
    """
    if isinstance(node, ast.Constant):
        return node.value, True
    if isinstance(node, (ast.Tuple, ast.List)):
        items: list[Any] = []
        all_static = True
        for elt in node.elts:
            val, ok = _ast_node_to_literal(elt)
            items.append(val)
            all_static = all_static and ok
        return (tuple(items) if isinstance(node, ast.Tuple) else items), all_static
    if isinstance(node, ast.Dict):
        pairs: list[tuple[Any, Any]] = []
        all_static = True
        for k_node, v_node in zip(node.keys, node.values):
            if k_node is None:
                return f"<dict_unpack:{ast.dump(v_node)}>", False
            k_val, k_ok = _ast_node_to_literal(k_node)
            v_val, v_ok = _ast_node_to_literal(v_node)
            pairs.append((k_val, v_val))
            all_static = all_static and k_ok and v_ok
        try:
            return tuple(sorted(pairs)), all_static
        except TypeError:
            return tuple(pairs), all_static
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        val, ok = _ast_node_to_literal(node.operand)
        if ok and isinstance(val, (int, float)):
            return (-val if isinstance(node.op, ast.USub) else +val), True
    return f"<expr:{ast.unparse(node) if hasattr(ast, 'unparse') else type(node).__name__}>", False


def _truncate_repr(val: Any, max_len: int) -> str:
    if isinstance(val, str) and val.startswith("<expr:") and val.endswith(">"):
        raw = val[6:-1]
    else:
        raw = repr(val)
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _compute_fingerprint(
    name: str,
    args: tuple[Any, ...],
    kwargs: tuple[tuple[str, Any], ...],
    is_static: bool,
) -> str:
    payload = json.dumps(
        {"name": name, "args": args, "kwargs": kwargs, "static": is_static},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def extract_calls_with_args(
    code_action: str,
    registered_names: Iterable[str],
    arg_aliases: dict[str, tuple[str, ...]] | None = None,
) -> list[ExtractedCall]:
    """Walk Python code_action and extract ordered calls to registered tools/agents.

    Args:
        code_action: Python snippet emitted by CodeAgent.
        registered_names: Allowed tool and managed sub-agent function names.
        arg_aliases: Optional mapping of tool_name -> ordered parameter names so
            positional calls like `schema_graph("invoices")` normalize to the
            same fingerprint as `schema_graph(table="invoices")`.
    """
    if not code_action or not code_action.strip():
        return []

    try:
        tree = ast.parse(code_action)
    except SyntaxError:
        return []

    allowed = set(registered_names)
    aliases = arg_aliases or {}
    extracted: list[ExtractedCall] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_name: str | None = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Support obj.tool_name(...) if invoked via namespace
            func_name = node.func.attr

        if not func_name or func_name not in allowed:
            continue

        param_names = aliases.get(func_name, ())
        norm_args: list[Any] = []
        norm_kwargs: dict[str, Any] = {}
        is_static = True

        for idx, arg_node in enumerate(node.args):
            if isinstance(arg_node, ast.Starred):
                norm_args.append(f"<starred:{ast.unparse(arg_node)}>")
                is_static = False
                continue
            val, ok = _ast_node_to_literal(arg_node)
            is_static = is_static and ok
            if idx < len(param_names):
                norm_kwargs[param_names[idx]] = val
            else:
                norm_args.append(val)

        for kw in node.keywords:
            if kw.arg is None:
                norm_kwargs["**kwargs"] = f"<kwunpack:{ast.unparse(kw.value)}>"
                is_static = False
                continue
            val, ok = _ast_node_to_literal(kw.value)
            is_static = is_static and ok
            norm_kwargs[kw.arg] = val

        args_tuple = tuple(norm_args)
        kwargs_tuple = tuple(sorted(norm_kwargs.items()))
        fp = _compute_fingerprint(func_name, args_tuple, kwargs_tuple, is_static)

        extracted.append(
            ExtractedCall(
                name=func_name,
                args=args_tuple,
                kwargs=kwargs_tuple,
                arg_fingerprint=fp,
                is_static=is_static,
            )
        )

    return extracted


@dataclass
class CallLedger:
    """Out-of-window memory of executed tool calls for constrained context budgets."""

    registered_names: set[str]
    arg_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    max_digest_entries: int = 8
    max_digest_chars: int = 420
    _entries: dict[str, LedgerEntry] = field(default_factory=dict)

    def record_step(
        self,
        step_num: int,
        code_action: str,
        status: CallStatus = "OK",
        outcome_summary: str = "",
    ) -> list[LedgerEntry]:
        """Parse code_action from a completed step and update the ledger."""
        calls = extract_calls_with_args(
            code_action=code_action,
            registered_names=self.registered_names,
            arg_aliases=self.arg_aliases,
        )
        updated: list[LedgerEntry] = []

        for call in calls:
            existing = self._entries.get(call.arg_fingerprint)
            if existing is not None:
                existing.last_step = step_num
                existing.hit_count += 1
                existing.status = status
                if outcome_summary:
                    existing.outcome_summary = outcome_summary
                updated.append(existing)
            else:
                entry = LedgerEntry(
                    first_step=step_num,
                    last_step=step_num,
                    call=call,
                    status=status,
                    outcome_summary=outcome_summary,
                )
                self._entries[call.arg_fingerprint] = entry
                updated.append(entry)

        return updated

    def find_redundant_calls(self, code_action: str) -> list[LedgerEntry]:
        """Return prior OK ledger entries that match static calls in code_action.

        Only flags static calls (`is_static=True`) that already succeeded (`OK`),
        so failed calls (`ERROR`) or loop-driven variable calls can still run.
        """
        calls = extract_calls_with_args(
            code_action=code_action,
            registered_names=self.registered_names,
            arg_aliases=self.arg_aliases,
        )
        duplicates: list[LedgerEntry] = []
        for call in calls:
            if not call.is_static:
                continue
            existing = self._entries.get(call.arg_fingerprint)
            if existing is not None and existing.status == "OK":
                duplicates.append(existing)
        return duplicates

    def should_short_circuit(self, code_action: str) -> tuple[bool, str]:
        """Decide whether a step consists exclusively of already-succeeded static calls.

        Returns (should_skip, synthetic_observation_message).
        """
        calls = extract_calls_with_args(
            code_action=code_action,
            registered_names=self.registered_names,
            arg_aliases=self.arg_aliases,
        )
        if not calls:
            return False, ""

        duplicates = self.find_redundant_calls(code_action)
        if len(duplicates) == len(calls):
            lines = [
                "Skipped duplicate tool call(s) already completed earlier in this run:"
            ]
            for dup in duplicates:
                summary = f" ({dup.outcome_summary})" if dup.outcome_summary else ""
                lines.append(
                    f"- {dup.call.format_signature()} already ran at step {dup.first_step}{summary}."
                )
            lines.append(
                "Use the information already retrieved or proceed directly to generating the target code."
            )
            return True, "\n".join(lines)

        return False, ""

    def format_digest(self) -> str:
        """Render a compact, token-bounded summary for injection into the sliding window."""
        if not self._entries:
            return ""

        # Keep the most recently active entries within max_digest_entries
        ordered = sorted(
            self._entries.values(),
            key=lambda e: (e.last_step, e.first_step),
        )[-self.max_digest_entries :]

        header = "[Executed Calls Ledger — Do Not Repeat Completed Lookups]"
        lines = [header]
        used_chars = len(header)

        for entry in ordered:
            repeat_tag = f" [x{entry.hit_count}]" if entry.hit_count > 1 else ""
            summary_tag = f" ({entry.outcome_summary})" if entry.outcome_summary else ""
            line = (
                f"- step {entry.first_step}: "
                f"{entry.call.format_signature()} -> {entry.status}{summary_tag}{repeat_tag}"
            )
            if used_chars + len(line) + 1 > self.max_digest_chars:
                break
            lines.append(line)
            used_chars += len(line) + 1

        return "\n".join(lines) if len(lines) > 1 else ""

    def clear(self) -> None:
        self._entries.clear()
