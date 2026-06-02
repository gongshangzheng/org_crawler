"""翻译器模块：使用 LLM（MiniMax 等 OpenAI 兼容接口）实现自动翻译。

与 html_blog_digest 的总结功能共用同一个 LLM 客户端（src/tools/llm_client.py），
通过环境变量 LLM_API_KEY / LLM_API_URL / LLM_MODEL 配置。
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from ..utils.logger import get_logger
    from .llm_client import call_llm
except ImportError:  # 兼容直接脚本导入：PYTHONPATH=src python -c 'from tools import Translator'
    import logging
    from tools.llm_client import call_llm

    def get_logger() -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        return logging.getLogger("arxiv_paper_digest")

_TITLE_PROMPT = (
    "你是一位学术翻译专家。请将以下英文学术论文标题翻译为中文。\n"
    "要求：\n"
    "1. 翻译准确、自然，术语使用中文领域通用译法\n"
    "2. 只输出翻译结果，不要加任何解释、括号标注或原文\n"
    "3. 如果标题中有专有名词（如模型名称、数据集名），保留英文原文\n\n"
    "标题：{title}"
)

_SUMMARY_PROMPT = (
    "你是一位学术翻译专家。请将以下英文学术论文摘要翻译为中文。\n"
    "要求：\n"
    "1. 翻译准确、流畅，术语使用中文领域通用译法\n"
    "2. 保持学术摘要的严谨风格\n"
    "3. 只输出翻译结果，不要加任何解释、括号标注或原文\n"
    "4. 专有名词（模型名、数据集名等）保留英文\n\n"
    "摘要：{summary}"
)

_ITEM_PROMPT = (
    "你是一位学术翻译专家。请将以下英文学术论文的标题和摘要翻译为中文。\n"
    "要求：\n"
    "1. 翻译准确、流畅，术语使用中文领域通用译法\n"
    "2. 保持学术摘要的严谨风格\n"
    "3. 专有名词（模型名、数据集名等）保留英文\n"
    "4. 严格按以下 JSON 格式输出，不要加任何其他内容：\n"
    '{{"title_zh": "中文标题", "summary_zh": "中文摘要"}}\n\n'
    "标题：{title}\n\n"
    "摘要：{summary}"
)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else ""
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取 JSON 对象。兼容纯 JSON、```json 代码块、前后少量废话。"""
    cleaned = _strip_code_fence(text)
    candidates = [cleaned]
    match = re.search(r"\{.*\}", cleaned, flags=re.S)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _clean_translation(text: str | None) -> str | None:
    """清理 LLM 翻译输出。"""
    if not text:
        return None
    cleaned = _strip_code_fence(text).strip()
    cleaned = re.sub(r"<think>.*?</think>\s*", "", cleaned, flags=re.S | re.I).strip()
    # 去掉常见的模型前缀
    cleaned = re.sub(r"^(翻译结果|中文标题|中文摘要)[:：]\s*", "", cleaned).strip()
    return cleaned or None


class Translator:
    """翻译器类，使用 LLM 实现标题和摘要的自动翻译。

    不再依赖阿里云翻译 API。LLM 配置通过环境变量统一管理：
      - LLM_API_KEY / LLM_API_URL / LLM_MODEL
      - 兼容 MINIMAX_* / OPENAI_* / ANTHROPIC_* 别名
    """

    def __init__(
        self,
        enabled: bool = True,
        source_lang: str = "en",
        target_lang: str = "zh",
        **_kwargs,  # 兼容旧调用签名中残留的阿里云参数
    ):
        self.enabled = enabled
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.logger = get_logger()

        if self.enabled:
            self.logger.info(f"LLM 翻译器已初始化（{source_lang} -> {target_lang}）")

    def translate(self, text: str, *, prompt_template: str = _TITLE_PROMPT) -> str | None:
        """翻译文本。"""
        if not self.enabled or not text or not text.strip():
            return None

        if "{title}" in prompt_template:
            prompt = prompt_template.format(title=text)
        else:
            prompt = prompt_template.format(summary=text)

        result = _clean_translation(call_llm(prompt, max_tokens=2000, temperature=0.3))
        if result:
            self.logger.debug(f"翻译成功: {text[:50]}... -> {result[:50]}...")
        else:
            self.logger.warning(f"翻译失败，返回 None: {text[:50]}...")
        return result

    def translate_title(self, title: str) -> str | None:
        """翻译标题。"""
        if not self.enabled:
            return None
        return self.translate(title, prompt_template=_TITLE_PROMPT)

    def translate_summary(self, summary: str) -> str | None:
        """翻译摘要。"""
        if not self.enabled:
            return None
        return self.translate(summary, prompt_template=_SUMMARY_PROMPT)

    def translate_item(self, item_dict: dict) -> dict:
        """
        翻译条目（标题和摘要）。

        优先一次 API 调用翻译标题+摘要；如果 JSON 解析失败，则退回分别翻译。
        """
        if not self.enabled:
            return item_dict

        result = item_dict.copy()
        title = item_dict.get("title", "")
        summary = item_dict.get("summary", "")

        if title and summary:
            raw = call_llm(_ITEM_PROMPT.format(title=title, summary=summary), max_tokens=2500, temperature=0.2)
            parsed = _extract_json_object(raw) if raw else None
            if parsed:
                title_zh = _clean_translation(str(parsed.get("title_zh") or ""))
                summary_zh = _clean_translation(str(parsed.get("summary_zh") or ""))
                if title_zh:
                    result["title_zh"] = title_zh
                if summary_zh:
                    result["summary_zh"] = summary_zh
                if title_zh and summary_zh:
                    self.logger.debug(f"批量翻译成功: {title[:40]}...")
                    return result
            elif raw:
                self.logger.debug("批量翻译 JSON 解析失败，退回分别翻译")

        if title and "title_zh" not in result:
            translated_title = self.translate_title(title)
            if translated_title:
                result["title_zh"] = translated_title

        if summary and "summary_zh" not in result:
            translated_summary = self.translate_summary(summary)
            if translated_summary:
                result["summary_zh"] = translated_summary

        return result
