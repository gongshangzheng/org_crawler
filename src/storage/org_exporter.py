"""Org-mode 格式导出器（向后兼容）"""

from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from .base_exporter import BaseOrgExporter
from ..utils.keyword_classifier import KeywordClassifier


class OrgExporter(BaseOrgExporter):
    """Org-mode 格式导出器（向后兼容，继承自BaseOrgExporter）"""
    
    def _format_item_detailed(self, item: Dict, index: int, crawl_time: datetime, output_path: Optional[Path] = None) -> List[str]:
        """详细格式：包含所有信息（默认实现）"""
        lines = []
        
        # 使用标题模板
        lines.append(self._render_title(item, index, crawl_time, output_path))
        
        # Properties
        lines.append(":PROPERTIES:")
        if item.get('link'):
            lines.append(f":URL: {item['link']}")
        if item.get('id'):
            lines.append(f":ID: {item['id']}")
        if item.get('arxiv_id'):
            lines.append(f":ARXIV_ID: {item['arxiv_id']}")
        if item.get('categories'):
            categories_str = ", ".join(item['categories'])
            lines.append(f":CATEGORIES: {categories_str}")
        if item.get('published_time'):
            lines.append(f":PUBLISHED_TIME: {item['published_time']}")
        if item.get('arxiv_announce_type'):
            lines.append(f":ARXIV_ANNOUNCE_TYPE: {item['arxiv_announce_type']}")
        lines.append(f":CRAWL_TIME: {crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        lines.append(":END:")
        lines.append("")
        
        # 标题
        lines.append("** 标题")
        lines.append(item.get('title', ''))
        lines.append("")
        
        # 标题（中文）- 如果有翻译
        if item.get('title_zh'):
            lines.append("** 标题（中文）")
            lines.append(item['title_zh'])
            lines.append("")
        
        # 链接
        if item.get('link'):
            lines.append("** 链接")
            lines.append(f"[[{item['link']}][{item['link']}]]")
            lines.append("")
        
        # 摘要
        if item.get('summary'):
            lines.append("** 摘要")
            summary = item['summary'].replace('\n', ' ')
            lines.append(summary)
            lines.append("")
        
        # 摘要（中文）- 如果有翻译
        if item.get('summary_zh'):
            lines.append("** 摘要（中文）")
            summary_zh = item['summary_zh'].replace('\n', ' ')
            lines.append(summary_zh)
            lines.append("")
        
        # LLM 摘要
        if item.get('llm_summary'):
            lines.append("** LLM 摘要")
            lines.append(item['llm_summary'])
            lines.append("")
        
        # 作者
        if item.get('authors'):
            lines.append("** 作者")
            authors_str = ", ".join(item['authors'])
            lines.append(authors_str)
            lines.append("")
        
        # 关键词
        if item.get('keywords'):
            lines.append("** 关键词")
            if isinstance(item['keywords'], list):
                keywords_str = ", ".join(item['keywords'])
            else:
                keywords_str = str(item['keywords'])
            lines.append(keywords_str)
            lines.append("")
        
        return lines
