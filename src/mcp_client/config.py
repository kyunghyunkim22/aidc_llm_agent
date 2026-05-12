from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = "config/mcp_servers.yaml"
ENV_CONFIG_PATH = "MCP_SERVERS_CONFIG"


def _resolve_path(path: str | None) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_CONFIG_PATH, DEFAULT_CONFIG_PATH))


_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


def _expand_env(value: str, *, where: str) -> str:
    """yaml 값의 ${VAR} 를 os.environ 으로 치환. 미설정 변수는 명확한 KeyError."""
    missing: list[str] = []

    def repl(m: re.Match[str]) -> str:
        var = m.group(1)
        if var not in os.environ:
            missing.append(var)
            return m.group(0)
        return os.environ[var]

    expanded = _ENV_PATTERN.sub(repl, value)
    if missing:
        raise KeyError(
            f"{where} 의 환경변수 미설정: {', '.join(sorted(set(missing)))}. "
            f".env 에 추가하거나 export 후 재실행하세요."
        )
    return expanded


def load_server_configs(path: str | None = None) -> dict[str, dict[str, Any]]:
    """yaml 에서 서버 connection dict 들을 로드.

    반환 형식은 langchain_mcp_adapters MultiServerMCPClient 가 그대로 받는다.
        { "<server_name>": { "transport": "streamable_http", "url": "...", ... } }

    url / headers 값의 ${VAR} 는 환경변수로 치환된다. 미설정 시 KeyError.
    """
    file_path = _resolve_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"MCP servers config not found: {file_path}")

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{file_path} 의 최상위는 server-name → config dict 형태여야 한다")

    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"server '{name}' 설정이 dict 가 아니다")
        if "transport" not in cfg or "url" not in cfg:
            raise ValueError(f"server '{name}' 에 transport/url 누락")
        cfg["url"] = _expand_env(str(cfg["url"]), where=f"server '{name}'.url")
        if "headers" in cfg and isinstance(cfg["headers"], dict):
            cfg["headers"] = {
                k: _expand_env(str(v), where=f"server '{name}'.headers.{k}")
                for k, v in cfg["headers"].items()
            }

    return raw
