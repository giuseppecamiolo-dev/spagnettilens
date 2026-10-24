import unittest
from pathlib import Path
from core.schema_graph import build_dependency_graph


class TestSchemaGraph(unittest.TestCase):
    def test_perl_invoice_script_graph_extraction(self) -> None:
        perl_code = Path("spaghettiCode.pl").read_text(encoding="utf-8")
        graph = build_dependency_graph(perl_code, "spaghettiCode.pl")

        self.assertEqual(graph.language, "Perl")
        self.assertIn("CGI_PARAM:student_code", graph.http_or_cli_inputs)
        self.assertIn("invoices", graph.tables_referenced)
        self.assertTrue(any("SQL_INJECTION" in f for f in graph.security_and_invariant_findings))
        self.assertTrue(any("LEDGER_INVARIANT" in f for f in graph.security_and_invariant_findings))

    def test_php_booking_script_graph_extraction(self) -> None:
        php_code = Path("spaghettiCode.php").read_text(encoding="utf-8")
        graph = build_dependency_graph(php_code, "spaghettiCode.php")

        self.assertEqual(graph.language, "PHP")
        self.assertIn("GET:id", graph.http_or_cli_inputs)
        self.assertIn("POST:course", graph.http_or_cli_inputs)
        self.assertIn("enrollments", graph.tables_referenced)
        self.assertTrue(any("DEPRECATED_RUNTIME" in f for f in graph.security_and_invariant_findings))
        self.assertTrue(any("SQL_INJECTION" in f for f in graph.security_and_invariant_findings))


if __name__ == "__main__":
    unittest.main()
