"""索引文件管理器"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class IndexManager:
    """索引文件管理器，用于管理 index.org 文件"""
    
    def __init__(self, index_path: Path):
        """
        初始化索引管理器
        
        Args:
            index_path: 索引文件路径
        """
        self.index_path = index_path
        # 确保父目录存在
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
    
    def update_index(self, 
                    site_name: str,
                    crawl_time: datetime,
                    items: List[Dict],
                    date_file_path: Optional[Path] = None):
        """
        更新索引文件，在文件最前面添加新的更新记录
        
        Args:
            site_name: 网站名称
            crawl_time: 爬取时间
            items: 条目列表
            date_file_path: 日期文件路径（用于创建链接），如果为None则不创建链接
        """
        # 生成新的更新记录
        new_section = self._generate_update_section(
            site_name, crawl_time, items, date_file_path
        )
        
        # 读取现有内容
        existing_content = ""
        if self.index_path.exists():
            existing_content = self.index_path.read_text(encoding='utf-8')
        
        # 如果文件为空，添加文件头
        if not existing_content.strip():
            header = self._generate_header(site_name)
            new_content = header + "\n\n" + new_section
            if existing_content.strip():
                new_content += "\n\n" + existing_content
        else:
            # 在文件最前面添加新内容
            new_content = new_section + "\n\n" + existing_content
        
        # 写入文件
        self.index_path.write_text(new_content, encoding='utf-8')
    
    def _generate_header(self, site_name: str) -> str:
        """
        生成索引文件头
        
        Args:
            site_name: 网站名称
            
        Returns:
            文件头内容
        """
        lines = [
            f"#+TITLE: {site_name.upper()} 论文索引",
            f"#+AUTHOR: Org Crawler",
            f"#+CREATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"* {site_name.upper()} 论文索引",
            "",
            "本文档包含所有爬取的论文索引信息。",
            ""
        ]
        return "\n".join(lines)
    
    def _generate_update_section(self,
                                 site_name: str,
                                 crawl_time: datetime,
                                 items: List[Dict],
                                 date_file_path: Optional[Path] = None) -> str:
        """
        生成更新记录部分
        
        Args:
            site_name: 网站名称
            crawl_time: 爬取时间
            items: 条目列表
            date_file_path: 日期文件路径（用于创建链接）
            
        Returns:
            更新记录内容
        """
        lines = []
        
        # 一级标题
        date_str = crawl_time.strftime('%Y-%m-%d')
        time_str = crawl_time.strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"* 更新于 {time_str}")
        lines.append("")
        
        # 如果有日期文件路径，添加链接
        if date_file_path and date_file_path.exists():
            # 计算相对路径
            try:
                rel_path = date_file_path.relative_to(self.index_path.parent)
                lines.append(f"详细内容: [[{rel_path}][{date_str}.org]]")
                lines.append("")
            except ValueError:
                # 如果无法计算相对路径，使用绝对路径
                lines.append(f"详细内容: [[{date_file_path}][{date_str}.org]]")
                lines.append("")
        
        # 表格头
        lines.append("| 标题 | 作者 | 发布时间 | 链接 | ArXiv ID |")
        lines.append("|------+------+----------+------+----------|")
        
        # 添加每个条目
        for item in items:
            title = item.get('title', '无标题')
            # 截断过长的标题（保留前80个字符）
            if len(title) > 80:
                title = title[:77] + "..."
            
            # 作者（只显示前2个）
            authors = item.get('authors', [])
            if authors:
                if len(authors) <= 2:
                    authors_str = ", ".join(authors)
                else:
                    authors_str = ", ".join(authors[:2]) + f" 等{len(authors)}人"
            else:
                authors_str = "-"
            
            # 发布时间
            published_time = item.get('published_time', item.get('published_time_str', '-'))
            
            # 链接
            link = item.get('link', '')
            if link:
                link_str = f"[[{link}][查看]]"
            else:
                link_str = "-"
            
            # ArXiv ID
            arxiv_id = item.get('arxiv_id', '-')
            
            # 转义表格中的特殊字符
            title = title.replace('|', '\\|')
            authors_str = authors_str.replace('|', '\\|')
            
            lines.append(f"| {title} | {authors_str} | {published_time} | {link_str} | {arxiv_id} |")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def get_all_items(self) -> List[Dict]:
        """
        从索引文件中提取所有条目（用于去重等操作）
        
        Returns:
            条目列表
        """
        if not self.index_path.exists():
            return []
        
        # 这里可以实现解析逻辑，如果需要的话
        # 目前返回空列表，因为主要功能是写入
        return []

