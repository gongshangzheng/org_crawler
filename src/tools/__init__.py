"""工具模块：包含翻译器、LLM 客户端等实用工具。

使用 lazy export，避免直接执行 `python src/html_blog_digest.py` 时，
导入 tools.llm_client 却被 translator 的包相对导入牵连失败。
"""

from .llm_client import call_llm

__all__ = ["Translator", "call_llm"]


def __getattr__(name: str):
    if name == "Translator":
        from .translator import Translator
        return Translator
    raise AttributeError(name)
