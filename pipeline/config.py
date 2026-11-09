"""Configuracao: "agora" do ambiente simulado e credenciais do AI proxy lidas do .env.

O token nunca e impresso, logado nem colocado em mensagem de erro.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

NOW = datetime(2026, 11, 2, 8, 0)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_BASE_URL = "https://ai-proxy.example.com/v1"
DEFAULT_MODEL = "gpt-6-astra"


class MissingToken(RuntimeError):
    """AI_PROXY_API_KEY ausente no ambiente e no .env."""


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str = field(repr=False)  # fora do repr para nunca aparecer em log
    model: str


def _read_env_file(path: Path) -> dict[str, str]:
    """Parser minimo de .env: CHAVE=valor por linha, ignora vazias e comentarios."""
    if not path.exists():
        return {}
    valores = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def _get(nome: str, arquivo: dict[str, str]) -> str:
    return os.environ.get(nome) or arquivo.get(nome, "")


def model_name() -> str:
    """Nome do modelo configurado, sem exigir o token (usado no log)."""
    return _get("AI_PROXY_MODEL", _read_env_file(ENV_PATH)) or DEFAULT_MODEL


def load_settings() -> Settings:
    arquivo = _read_env_file(ENV_PATH)
    api_key = _get("AI_PROXY_API_KEY", arquivo)
    if not api_key:
        raise MissingToken("AI_PROXY_API_KEY ausente (defina no .env)")
    return Settings(
        base_url=_get("AI_PROXY_BASE_URL", arquivo) or DEFAULT_BASE_URL,
        api_key=api_key,
        model=_get("AI_PROXY_MODEL", arquivo) or DEFAULT_MODEL,
    )
