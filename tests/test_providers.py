import json
import os
import unittest
from unittest.mock import MagicMock, patch

from core.providers import (
    FoundryInteropProvider,
    NpuRunInteropProvider,
    OllamaCLIProvider,
    OllamaHTTPProvider,
    OpenAICompatibleProvider,
    create_provider,
)


class TestLLMProviders(unittest.TestCase):
    def test_factory_creates_expected_provider_types(self) -> None:
        self.assertIsInstance(create_provider("foundry", "llama3"), FoundryInteropProvider)
        self.assertIsInstance(create_provider("npu", "qwen3-4b-instruct-2507"), NpuRunInteropProvider)
        self.assertIsInstance(create_provider("ollama", "llama3"), OllamaCLIProvider)
        self.assertIsInstance(create_provider("ollama-http", "llama3"), OllamaHTTPProvider)
        self.assertIsInstance(
            create_provider("meta", "muse-spark", api_key="test-key"),
            OpenAICompatibleProvider,
        )

    def test_factory_rejects_unknown_provider_or_invalid_model(self) -> None:
        with self.assertRaises(ValueError):
            create_provider("unknown_backend", "model-x")
        with self.assertRaises(ValueError):
            create_provider("ollama", "llama3; rm -rf /")

    @patch("urllib.request.urlopen")
    def test_ollama_http_provider_streams_ndjson_tokens(self, mock_urlopen: MagicMock) -> None:
        ndjson_lines = [
            json.dumps({"message": {"content": "SELECT "}, "done": False}).encode("utf-8") + b"\n",
            json.dumps({"message": {"content": "* FROM invoices;"}, "done": True}).encode("utf-8") + b"\n",
        ]
        mock_response = MagicMock()
        mock_response.__enter__.return_value = ndjson_lines
        mock_urlopen.return_value = mock_response

        provider = create_provider("ollama-http", "llama3")
        output = provider.generate("Refactor SQL query", system_prompt="You are an ERP architect.")
        self.assertEqual(output, "SELECT * FROM invoices;")

    @patch("subprocess.Popen")
    def test_npu_provider_executes_powershell_bridge(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("sub calculate_balance { return $total; }", "")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        provider = create_provider("npu", "qwen3-4b-instruct-2507")
        result = provider.generate("Refactor spaghettiCode.pl")
        self.assertIn("calculate_balance", result)

    @patch("urllib.request.urlopen")
    def test_openai_compatible_meta_sse_streaming(self, mock_urlopen: MagicMock) -> None:
        sse_events = [
            b'data: {"choices": [{"delta": {"content": "def "}}]}\n',
            b'data: {"choices": [{"delta": {"content": "get_invoice():"}}]}\n',
            b"data: [DONE]\n",
        ]
        mock_response = MagicMock()
        mock_response.__enter__.return_value = sse_events
        mock_urlopen.return_value = mock_response

        with patch.dict(os.environ, {"META_API_KEY": "meta-secret-key"}):
            provider = create_provider("meta", "muse-spark")
            output = provider.generate("Generate FastAPI endpoint")
            self.assertEqual(output, "def get_invoice():")


if __name__ == "__main__":
    unittest.main()
