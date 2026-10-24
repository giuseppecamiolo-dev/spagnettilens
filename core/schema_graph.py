from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class LegacyDependencyGraph:
    file_name: str
    language: str
    subroutines_or_functions: List[str] = field(default_factory=list)
    http_or_cli_inputs: List[str] = field(default_factory=list)
    database_connections: List[str] = field(default_factory=list)
    sql_queries_detected: List[str] = field(default_factory=list)
    tables_referenced: List[str] = field(default_factory=list)
    security_and_invariant_findings: List[str] = field(default_factory=list)
    schema_tables: Dict[str, List[str]] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def parse_sql_schema(schema_sql: str) -> Dict[str, List[str]]:
    """Extracts table names and column definitions from a SQL CREATE TABLE dump."""
    tables: Dict[str, List[str]] = {}
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(schema_sql):
        table_name = match.group(1)
        body = match.group(2)
        columns: List[str] = []
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.upper().startswith(
                ("PRIMARY KEY", "FOREIGN KEY", "KEY", "INDEX", "CONSTRAINT", "UNIQUE")
            ):
                continue
            col_name = line.split()[0].strip("`\"'")
            columns.append(col_name)
        tables[table_name] = columns
    return tables


def build_dependency_graph(
    code: str, file_path: str, schema_sql: Optional[str] = None
) -> LegacyDependencyGraph:
    path = Path(file_path)
    language = "Perl" if path.suffix.lower() == ".pl" else "PHP"

    # 1. Subroutines / functions
    func_matches = re.findall(r"\b(?:sub|function)\s+([a-zA-Z_]\w*)", code)

    # 2. HTTP / CGI / CLI inputs
    inputs: set[str] = set()
    for method, key in re.findall(
        r"\$_(GET|POST|REQUEST|SESSION|COOKIE)\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", code
    ):
        inputs.add(f"{method}:{key}")
    for key in re.findall(r"->param\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
        inputs.add(f"CGI_PARAM:{key}")

    # 3. Database connection strings & deprecated drivers
    db_conns: List[str] = []
    findings: List[str] = []

    if "DBI->connect" in code:
        db_conns.append("Perl DBI->connect")
        if re.search(r'DBI->connect\s*\([^)]*["\'][^"\']+["\']\s*,\s*["\'][^"\']+["\']', code):
            findings.append("SECURITY: Hardcoded database credentials in DBI->connect()")

    if "mysql_connect" in code or "mysql_query" in code:
        db_conns.append("PHP ext/mysql (Deprecated/Removed in PHP 7+)")
        findings.append("DEPRECATED_RUNTIME: Legacy PHP mysql_* extension detected; migrate to PDO/MySQLi")

    if re.search(r"\$db_pass\s*=\s*['\"][^'\"]+['\"]", code):
        findings.append("SECURITY: Hardcoded database password in source file")

    # 4. Embedded SQL statements & referenced tables
    sql_pattern = re.compile(
        r"([\"']\s*(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\b.*?[\"'])",
        re.IGNORECASE | re.DOTALL,
    )
    queries = [re.sub(r"\s+", " ", q.strip("\"' \n\t")) for q in sql_pattern.findall(code)]

    tables: set[str] = set()
    table_regex = re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE)\s+[`\"']?([a-zA-Z_]\w*)[`\"']?",
        re.IGNORECASE,
    )
    for q in queries:
        for t in table_regex.findall(q):
            tables.add(t)
        if re.search(r"\$[a-zA-Z_]\w*", q):
            findings.append(f"SQL_INJECTION: Unparameterized variable interpolation in query [{q}]")

    # 5. Financial / Ledger floating-point drift detection
    if re.search(r"\$\w*amount\w*\s*\+=", code, re.IGNORECASE):
        findings.append(
            "LEDGER_INVARIANT: Floating-point accumulation on monetary amount detected; "
            "use integer cents or SQL DECIMAL aggregation to prevent rounding drift."
        )

    # 6. XSS / Unescaped HTML output detection
    if re.search(r"echo\s+\$_(?:GET|POST|REQUEST)|action=.*<\?php\s+echo\s+\$", code):
        findings.append("XSS_VULNERABILITY: Unescaped variable echoed directly into HTML attribute/body")

    schema_map = parse_sql_schema(schema_sql) if schema_sql else {}

    return LegacyDependencyGraph(
        file_name=path.name,
        language=language,
        subroutines_or_functions=sorted(set(func_matches)),
        http_or_cli_inputs=sorted(inputs),
        database_connections=db_conns,
        sql_queries_detected=queries,
        tables_referenced=sorted(tables),
        security_and_invariant_findings=findings,
        schema_tables=schema_map,
    )
