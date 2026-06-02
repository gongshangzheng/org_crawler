"""统一的 LLM 调用客户端，供翻译和总结共用。

环境变量：
  LLM_API_KEY   — API Key（必填）
  LLM_API_URL   — 接口地址，如 https://api.minimax.chat/v1/chat/completions（必填）
  LLM_MODEL     — 模型名称，如 MiniMax-M1（必填）

兼容别名：
  MINIMAX_API_KEY / MINIMAX_API_URL / MINIMAX_MODEL
  OPENAI_API_KEY / OPENAI_API_URL / OPENAI_MODEL
  ANTHROPIC_API_KEY / ANTHROPIC_API_URL / ANTHROPIC_MODEL
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

try:
    from ..utils.logger import get_logger
except ImportError:  # 兼容直接执行：python src/html_blog_digest.py
    import logging

    def get_logger() -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        return logging.getLogger("arxiv_paper_digest")

_logger = get_logger()


def _load_local_env() -> None:
    """加载 skill 根目录下的 .env，避免直接调用 digest/translator 时环境变量缺失。"""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    skill_root = Path(__file__).resolve().parents[2]
    load_dotenv(skill_root / ".env", override=False)


_load_local_env()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _strip_reasoning_blocks(text: str) -> str:
    """去掉 MiniMax-M1 等 reasoning 模型可能返回的 <think>...</think> 内容。"""
    import re
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S | re.I).strip()
    return cleaned or text.strip()


def _extract_text(resp: dict) -> str | None:
    """从 LLM 响应中提取文本，兼容 OpenAI 和 Anthropic 两种格式。"""
    # OpenAI 格式: choices[0].message.content
    if "choices" in resp:
        try:
            return _strip_reasoning_blocks(resp["choices"][0]["message"]["content"])
        except (KeyError, IndexError):
            pass
    # Anthropic 格式: content[0].text
    if "content" in resp and isinstance(resp["content"], list):
        try:
            for block in resp["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    return _strip_reasoning_blocks(block["text"])
        except (KeyError, IndexError):
            pass
    return None


def call_llm(prompt: str, *, max_tokens: int = 4000, temperature: float = 0.7, timeout: int = 120) -> str | None:
    """调用 LLM，返回生成文本；失败返回 None。

    自动检测 Anthropic / OpenAI 风格：
      - URL 包含 /anthropic → Anthropic Messages API
      - 否则 → OpenAI Chat Completions API
    """
    api_key = _env("LLM_API_KEY") or _env("MINIMAX_API_KEY") or _env("ANTHROPIC_API_KEY") or _env("OPENAI_API_KEY")
    api_url = _env("LLM_API_URL") or _env("MINIMAX_API_URL") or _env("ANTHROPIC_API_URL") or _env("OPENAI_API_URL")
    model = _env("LLM_MODEL") or _env("MINIMAX_MODEL") or _env("ANTHROPIC_MODEL") or _env("OPENAI_MODEL")

    # MiniMax 常用兜底：如果只配置了 MINIMAX_API_KEY 和模型，默认走 OpenAI 兼容端点。
    if api_key and model and not api_url and (_env("MINIMAX_API_KEY") or "minimax" in model.lower()):
        api_url = "https://api.minimax.chat/v1/chat/completions"

    if not (api_key and api_url and model):
        _logger.warning(
            "LLM 环境变量未配置，至少需要 API key、API URL、model；"
            "支持 LLM_* / MINIMAX_* / OPENAI_* / ANTHROPIC_*"
        )
        return None

    is_anthropic = "/anthropic" in api_url.lower()

    if is_anthropic:
        endpoint = api_url.rstrip("/")
        if not endpoint.endswith("/v1/messages"):
            endpoint += "/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        })
    else:
        # OpenAI 兼容（MiniMax、DeepSeek 等通用）
        endpoint = api_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

    req = urllib.request.Request(endpoint, data=payload.encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode())
            return _extract_text(resp)
    except Exception as e:
        _logger.warning(f"LLM 调用失败: {e}")
        return None


def call_llm_batch(prompts: list[str], *, max_tokens: int = 4000, temperature: float = 0.7) -> list[str | None]:
    """批量调用 LLM，返回对应结果列表。"""
    return [call_llm(p, max_tokens=max_tokens, temperature=temperature) for p in prompts]
