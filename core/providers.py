from __future__ import annotations

import abc
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

MODEL_NAME_REGEX = re.compile(r"^[\w.:/-]+$")

DEFAULT_MODELS: Dict[str, str] = {
    "foundry": "llama3",
    "npu": "qwen3-4b-instruct-2507",
    "ollama": "llama3",
    "ollama-http": "llama3",
    "meta": "muse-spark",
    "baseten": "llama3",
    "fireworks": "llama3",
    "modal": "llama3",
}


def validate_model_name(model: str) -> None:
    if not MODEL_NAME_REGEX.match(model):
        raise ValueError(f"Nome modello non valido: {model}")


@dataclass
class LLMConfig:
    provider: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_headers: Dict[str, str] = field(default_factory=dict)


class LLMProvider(abc.ABC):
    def __init__(self, config: LLMConfig) -> None:
        validate_model_name(config.model)
        self.config = config

    @abc.abstractmethod
    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        raise NotImplementedError

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "".join(self.stream(prompt, system_prompt=system_prompt))


class FoundryInteropProvider(LLMProvider):
    """
    Executes `foundry run <model>` via PowerShell/cmd.exe using a wslpath-translated
    temporary file to prevent PowerShell STDIN pipe hangs.
    """

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".txt", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(full_prompt)
            temp_file_path = tf.name

        try:
            if shutil.which("wslpath"):
                try:
                    wslpath_proc = subprocess.run(
                        ["wslpath", "-w", temp_file_path],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    win_temp_file_path = wslpath_proc.stdout.strip()
                except subprocess.CalledProcessError:
                    win_temp_file_path = temp_file_path
            else:
                win_temp_file_path = temp_file_path

            ps_command = f'cmd.exe /c \'foundry run {self.config.model} < "{win_temp_file_path}"\''
            ps_executable = "pwsh.exe" if shutil.which("pwsh.exe") else "powershell.exe"

            process = subprocess.Popen(
                [ps_executable, "-Command", ps_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"Errore da {ps_executable}: {stderr.strip()}")
            yield stdout
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)


class NpuRunInteropProvider(LLMProvider):
    """
    Executes `npurun run <model> "$prompt"` via PowerShell interop.
    Passes prompt via STDIN to [Console]::In.ReadToEnd() so npurun receives it
    safely as a trailing argument without shell-escaping breakage.
    """

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        ps_command = f'$prompt = [Console]::In.ReadToEnd().Trim(); npurun run {self.config.model} "$prompt"'
        ps_executable = "pwsh.exe" if shutil.which("pwsh.exe") else "powershell.exe"

        process = subprocess.Popen(
            [ps_executable, "-Command", ps_command],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = process.communicate(input=full_prompt)
        if process.returncode != 0:
            raise RuntimeError(f"Errore da {ps_executable}: {stderr.strip()}")
        yield stdout


class OllamaCLIProvider(LLMProvider):
    """Executes `ollama run <model>` directly inside WSL via subprocess."""

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        process = subprocess.Popen(
            ["ollama", "run", self.config.model],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = process.communicate(input=full_prompt)
        if process.returncode != 0:
            raise RuntimeError(f"Errore da ollama: {stderr.strip()}")
        yield stdout


class OllamaHTTPProvider(LLMProvider):
    """Streams tokens from Ollama REST API (/api/chat) for agentic loops."""

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        base = (self.config.base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        url = f"{base}/api/chat"

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.config.temperature, "num_predict": self.config.max_tokens},
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Connessione a Ollama HTTP fallita ({url}): {exc}") from exc


class OpenAICompatibleProvider(LLMProvider):
    """SSE client for Meta Model API (Muse Spark/Code), Baseten, Fireworks, and Modal."""

    DEFAULT_ENDPOINTS: Dict[str, str] = {
        "meta": "https://api.llama.com/compat/v1",
        "baseten": "https://inference.baseten.co/v1",
        "fireworks": "https://api.fireworks.ai/inference/v1",
        "modal": "https://api.modal.com/v1",
        "openai": "https://api.openai.com/v1",
    }

    ENV_KEY_MAP: Dict[str, str] = {
        "meta": "META_API_KEY",
        "baseten": "BASETEN_API_KEY",
        "fireworks": "FIREWORKS_API_KEY",
        "modal": "MODAL_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    def _resolve_endpoint(self) -> str:
        base = (
            self.config.base_url
            or os.getenv(f"{self.config.provider.upper()}_BASE_URL")
            or self.DEFAULT_ENDPOINTS.get(self.config.provider, "")
        )
        if not base:
            raise ValueError(f"Nessun base_url configurato per '{self.config.provider}'.")
        return f"{base.rstrip('/')}/chat/completions"

    def _resolve_api_key(self) -> str:
        if self.config.api_key:
            return self.config.api_key
        env_var = self.ENV_KEY_MAP.get(
            self.config.provider, f"{self.config.provider.upper()}_API_KEY"
        )
        key = os.getenv(env_var, "")
        if not key:
            raise RuntimeError(f"API key mancante per '{self.config.provider}'. Imposta {env_var}.")
        return key

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        url = self._resolve_endpoint()
        api_key = self._resolve_api_key()

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SpaghettiLens-AI/0.2.0",
            **self.config.extra_headers,
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        choices = event.get("choices", [])
                        if choices:
                            token = choices[0].get("delta", {}).get("content")
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Errore HTTP {exc.code} da {self.config.provider} ({url}): {err_body}"
            ) from exc


def create_provider(
    provider_name: str,
    model: Optional[str] = None,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LLMProvider:
    normalized = provider_name.strip().lower()
    resolved_model = model or DEFAULT_MODELS.get(normalized, "llama3")
    cfg = LLMConfig(
        provider=normalized,
        model=resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )

    if normalized == "foundry":
        return FoundryInteropProvider(cfg)
    if normalized == "npu":
        return NpuRunInteropProvider(cfg)
    if normalized == "ollama":
        return OllamaCLIProvider(cfg)
    if normalized == "ollama-http":
        return OllamaHTTPProvider(cfg)
    if normalized in {"meta", "baseten", "fireworks", "modal", "openai"}:
        return OpenAICompatibleProvider(cfg)

    raise ValueError(
        f"Provider non supportato: '{provider_name}'. "
        "Supportati: foundry, npu, ollama, ollama-http, meta, baseten, fireworks, modal, openai."
    )
