"""智源社区 RSS 爬虫实现"""

from datetime import datetime
from typing import Dict, List, Optional

from .rss_crawler import BaseRSSCrawler
from ..models.site_config import SiteConfig


class ZhiyuanRSSCrawler(BaseRSSCrawler):
    """智源社区 RSS 爬虫，专门处理智源社区的特殊格式"""
    
    def __init__(self, site_config: SiteConfig, translator=None):
        """
        初始化智源社区 RSS 爬虫
        
        Args:
            site_config: 网站配置
            translator: 翻译器实例（可选）
        """
        super().__init__(site_config, translator=translator)
    
    def extract_other_info(self, entry: Dict) -> Dict:
        """
        提取其他信息（智源社区特定）
        
        Args:
            entry: RSS 条目
            
        Returns:
            其他信息的字典
        """
        # 调用父类方法获取基础信息
        other_info = super().extract_other_info(entry)
        
        # 智源社区特定的解析
        # 提取摘要
        other_info['summary'] = self._extract_summary(entry)
        
        # 提取作者信息
        other_info['authors'] = self._extract_authors(entry)
        
        # 提取分类/标签
        other_info['categories'] = self._extract_categories(entry)
        
        # 提取智源社区ID（如果有）
        link = self.extract_link(entry)
        other_info['zhiyuan_id'] = self._extract_zhiyuan_id(entry, link)
        
        return other_info
    
    def _extract_summary(self, entry: Dict) -> str:
        """
        提取摘要，处理智源社区的特殊格式
        
        Args:
            entry: RSS 条目
            
        Returns:
            清理后的摘要文本
        """
        # 优先使用 summary 字段
        description = entry.get('summary', '')
        if not description:
            description = entry.get('description', '')
        
        if not description:
            return ''
        
        # 清理摘要文本
        return description.strip()
    
    def _extract_authors(self, entry: Dict) -> List[str]:
        """
        提取作者信息（智源社区特定）
        
        Args:
            entry: RSS 条目
            
        Returns:
            作者列表
        """
        authors = []
        
        # 方法1: 检查标准的 authors 字段
        if hasattr(entry, 'authors') and entry.authors:
            authors = [author.get('name', '') if isinstance(author, dict) else str(author) 
                      for author in entry.authors]
        # 方法2: 检查 author 字段（单个）
        elif hasattr(entry, 'author') and entry.author:
            authors = [entry.author]
        # 方法3: 从字典中获取
        elif isinstance(entry, dict):
            if 'authors' in entry:
                authors = entry['authors']
            elif 'author' in entry:
                authors = [entry['author']]
        # 方法4: 尝试从 dc:creator 获取（如果使用 Dublin Core）
        if not authors:
            if hasattr(entry, 'dc_creators') and entry.dc_creators:
                authors = entry.dc_creators
            elif hasattr(entry, 'dc_creator') and entry.dc_creator:
                if isinstance(entry.dc_creator, list):
                    authors = entry.dc_creator
                else:
                    authors = [entry.dc_creator]
            elif isinstance(entry, dict):
                if 'dc_creators' in entry:
                    authors = entry['dc_creators']
                elif 'dc_creator' in entry:
                    creator = entry['dc_creator']
                    authors = [creator] if isinstance(creator, str) else creator
        
        # 如果还是没有，使用父类方法
        if not authors:
            authors = self._extract_authors_generic(entry)
        
        # 清理作者名称（去除多余空格）
        cleaned_authors = [author.strip() for author in authors if author and author.strip()]
        return cleaned_authors
    
    def _extract_categories(self, entry: Dict) -> List[str]:
        """
        提取分类/标签（智源社区特定）
        
        Args:
            entry: RSS 条目
            
        Returns:
            分类列表
        """
        categories = []
        
        # 方法1: 检查 tags 字段（feedparser 标准格式）
        if hasattr(entry, 'tags') and entry.tags:
            categories = [tag.get('term', '') if isinstance(tag, dict) else str(tag)
                        for tag in entry.tags]
        # 方法2: 检查 category 字段
        elif hasattr(entry, 'category') and entry.category:
            if isinstance(entry.category, list):
                categories = [str(cat) for cat in entry.category]
            else:
                categories = [str(entry.category)]
        # 方法3: 从字典中获取
        elif isinstance(entry, dict):
            if 'tags' in entry:
                tags = entry['tags']
                categories = [tag.get('term', '') if isinstance(tag, dict) else str(tag)
                           for tag in tags]
            elif 'category' in entry:
                cat = entry['category']
                categories = [cat] if isinstance(cat, str) else [str(c) for c in cat]
        
        # 如果还是没有，使用父类方法
        if not categories:
            categories = self._extract_categories_generic(entry)
        
        # 清理分类名称
        cleaned_categories = [cat.strip() for cat in categories if cat and cat.strip()]
        return cleaned_categories
    
    def _extract_zhiyuan_id(self, entry: Dict, link: str) -> str:
        """
        提取智源社区ID
        
        可以从以下位置提取：
        1. guid
        2. link: "https://hub.baai.ac.cn/papers/xxx" -> "xxx"
        3. id 字段
        
        Args:
            entry: RSS 条目
            link: 论文链接
            
        Returns:
            智源社区ID
        """
        zhiyuan_id = ''
        
        # 方法1: 从 guid 中提取
        guid = ''
        if hasattr(entry, 'id'):
            guid = entry.id
        elif hasattr(entry, 'guid'):
            guid = entry.guid if isinstance(entry.guid, str) else getattr(entry.guid, 'value', '')
        elif isinstance(entry, dict):
            guid = entry.get('id', '') or entry.get('guid', '')
        
        if guid:
            zhiyuan_id = guid
        
        # 方法2: 从链接中提取（格式：https://hub.baai.ac.cn/papers/xxx）
        if not zhiyuan_id and 'hub.baai.ac.cn' in link:
            # 尝试从URL路径中提取ID
            parts = link.split('/')
            if 'papers' in parts:
                idx = parts.index('papers')
                if idx + 1 < len(parts):
                    zhiyuan_id = parts[idx + 1].split('?')[0]  # 移除查询参数
        
        return zhiyuan_id

