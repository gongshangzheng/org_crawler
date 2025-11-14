"""Org-mode 格式导出器"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict

from ..models.crawl_result import CrawlResult


class OrgExporter:
    """Org-mode 格式导出器"""
    
    def __init__(self):
        """初始化导出器"""
        pass
    
    def export(self, result: CrawlResult, output_path: Path):
        """
        导出为 org-mode 格式
        
        Args:
            result: 爬取结果
            output_path: 输出文件路径
        """
        # 确保父目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        org_content = self._generate_org_content(result)
        
        # 如果文件已存在，追加新条目
        if output_path.exists():
            existing_content = output_path.read_text(encoding='utf-8')
            # 检查是否已有相同日期的内容，如果有则合并
            org_content = self._merge_org_content(existing_content, org_content, result)
        
        output_path.write_text(org_content, encoding='utf-8')
    
    def _generate_org_content(self, result: CrawlResult) -> str:
        """
        生成 org-mode 内容
        
        Args:
            result: 爬取结果
            
        Returns:
            org-mode 格式的字符串
        """
        lines = []
        
        # 文件头
        date_str = result.crawl_time.strftime('%Y-%m-%d')
        lines.append(f"#+TITLE: {result.site_name.upper()} 爬取结果 - {date_str}")
        lines.append(f"#+DATE: {date_str}")
        lines.append(f"#+AUTHOR: Org Crawler")
        lines.append(f"#+CREATED: {result.crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 如果没有条目，添加说明
        if result.items_count == 0:
            lines.append(f"* 本次爬取无新条目")
            lines.append(f"")
            lines.append(f"爬取时间: {result.crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if result.error_message:
                lines.append(f"错误信息: {result.error_message}")
            return "\n".join(lines)
        
        # 添加条目
        for idx, item in enumerate(result.items, 1):
            lines.extend(self._format_item(item, idx, result.crawl_time))
            lines.append("")  # 条目之间的空行
        
        return "\n".join(lines)
    
    def _format_item(self, item: Dict, index: int, crawl_time: datetime) -> List[str]:
        """
        格式化单个条目
        
        Args:
            item: 条目字典
            index: 条目索引
            crawl_time: 爬取时间
            
        Returns:
            格式化的行列表
        """
        lines = []
        
        # 主标题
        title = item.get('title', '无标题')
        published_time = item.get('published_time', '')
        lines.append(f"* 条目 {index}: {title} [{published_time}]")
        
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
        
        # 分类
        if item.get('categories'):
            lines.append("** 分类")
            categories_str = ", ".join(item['categories'])
            lines.append(categories_str)
            lines.append("")
        
        # 元数据
        lines.append("** 元数据")
        if item.get('published_time'):
            lines.append(f"- 发布时间: {item['published_time']}")
        if item.get('arxiv_id'):
            lines.append(f"- ArXiv ID: {item['arxiv_id']}")
        if item.get('arxiv_announce_type'):
            lines.append(f"- 公告类型: {item['arxiv_announce_type']}")
        lines.append(f"- 爬取时间: {crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 分隔线
        lines.append("---")
        
        return lines
    
    def _merge_org_content(self, existing: str, new: str, result: CrawlResult) -> str:
        """
        合并现有的和新的 org 内容
        
        Args:
            existing: 现有内容
            new: 新内容
            result: 爬取结果
            
        Returns:
            合并后的内容
        """
        # 简单实现：如果新内容有条目，则追加到现有内容
        if result.items_count > 0:
            # 提取新内容的条目部分（跳过文件头）
            new_lines = new.split('\n')
            # 找到第一个 "* 条目" 的位置
            start_idx = 0
            for i, line in enumerate(new_lines):
                if line.startswith('* 条目'):
                    start_idx = i
                    break
            
            if start_idx > 0:
                # 追加新条目到现有内容
                existing_lines = existing.split('\n')
                # 移除现有内容的最后一个空行（如果有）
                while existing_lines and not existing_lines[-1].strip():
                    existing_lines.pop()
                
                # 添加分隔和说明
                existing_lines.append("")
                existing_lines.append(f"* 更新于 {result.crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
                existing_lines.append("")
                
                # 添加新条目
                existing_lines.extend(new_lines[start_idx:])
                return "\n".join(existing_lines)
        
        return existing

