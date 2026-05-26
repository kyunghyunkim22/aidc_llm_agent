"""vLLM(OpenAI 호환) endpoint 용 ChatOpenAI 팩토리."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


def build_llm() -> ChatOpenAI:
    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
    model = os.environ.get("LLM_MODEL", "/models/gemma-4-e4b-it")
    api_key = os.environ.get("LLM_API_KEY", "EMPTY")
    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=0,
        stream_usage=True,
    )
