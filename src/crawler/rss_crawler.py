"""RSS 爬虫基类实现"""

import feedparser
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from .base import BaseCrawler
from ..models.crawl_result import CrawlResult
from ..models.crawl_item import CrawlItem
from ..models.site_config import SiteConfig


class BaseRSSCrawler(BaseCrawler):
    """RSS 爬虫基类，提供通用的 RSS 解析功能"""
    
    def __init__(self, site_config: SiteConfig):
        """
        初始化 RSS 爬虫
        
        Args:
            site_config: 网站配置
        """
        super().__init__(site_config)
        self.update_frequency_hours = site_config.update_frequency / 60  # 转换为小时
    
    def crawl(self) -> CrawlResult:
        """
        执行 RSS 爬取
        
        Returns:
            CrawlResult: 爬取结果
        """
        crawl_time = datetime.now()
        
        try:
            # 解析 RSS feed
            # feedparser 完全支持标准的 RSS 2.0 格式（包含 <channel> 标签）
            # RSS 2.0 标准结构：<rss><channel><item>...</item></channel></rss>
            # feedparser 会自动解析 <channel> 中的 <item> 元素到 feed.entries
            feed = feedparser.parse(self.site_config.url)
            
            if feed.bozo:
                error_msg = f"RSS 解析错误: {feed.bozo_exception if hasattr(feed, 'bozo_exception') else '未知错误'}"
                return CrawlResult(
                    site_name=self.site_config.name,
                    crawl_time=crawl_time,
                    items_count=0,
                    success=False,
                    error_message=error_msg
                )
            
            # 验证 feed 结构
            # feedparser 解析标准 RSS 2.0 格式（包含 <channel> 标签）后的结构：
            # - feed.entries: 包含所有 <channel><item> 元素的列表
            #   * 每个 entry 对应一个 <item> 元素
            #   * entry.title, entry.link, entry.description 等对应 <item> 的子元素
            # - feed.feed: 包含 <channel> 的元信息（title, link, description 等）
            # 
            # RSS 2.0 标准结构：
            # <rss>
            #   <channel>
            #     <title>...</title>
            #     <item>
            #       <title>...</title>
            #       <link>...</link>
            #       ...
            #     </item>
            #     <item>...</item>
            #   </channel>
            # </rss>
            #
            # feedparser 会自动：
            # 1. 解析 <channel> 标签（存储到 feed.feed）
            # 2. 提取所有 <item> 标签（存储到 feed.entries）
            # 3. 解析每个 <item> 的子元素（title, link, description, pubDate 等）
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                return CrawlResult(
                    site_name=self.site_config.name,
                    crawl_time=crawl_time,
                    items_count=0,
                    success=True,
                    error_message="RSS feed 中没有找到条目"
                )
            
            # 计算时间范围（过去 N 小时）
            time_threshold = crawl_time - timedelta(hours=self.update_frequency_hours)
            
            # 提取条目
            # feed.entries 包含所有 <channel> 中的 <item> 元素
            items = []
            for entry in feed.entries:
                # 解析发布时间
                published_time = self.extract_published_time(entry)
                
                # 只保留时间范围内的条目
                if published_time and published_time >= time_threshold:
                    item = self.parse_entry(entry)
                    if item:
                        items.append(item)
            
            # 过滤器链处理（标题/摘要/作者/时间等），如果未配置则回退到关键词过滤
            filtered_items = self.apply_filters(items)
            
            # 转换为字典列表（用于 CrawlResult）
            items_dict = [item.to_dict() for item in filtered_items]
            
            return CrawlResult(
                site_name=self.site_config.name,
                crawl_time=crawl_time,
                items_count=len(filtered_items),
                items=items_dict,
                success=True
            )
            
        except Exception as e:
            return CrawlResult(
                site_name=self.site_config.name,
                crawl_time=crawl_time,
                items_count=0,
                success=False,
                error_message=f"爬取失败: {str(e)}"
            )
    
    def extract_published_time(self, entry: Dict) -> Optional[datetime]:
        """
        提取发布时间（RSS 通用方法）
        
        Args:
            entry: RSS 条目
            
        Returns:
            datetime 对象，如果解析失败返回 None
        """
        try:
            # feedparser 通常会将发布时间解析为 time.struct_time
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'published'):
                # 尝试解析字符串格式的时间
                time_str = entry.published
                # 处理常见的 RSS 时间格式
                for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%a, %d %b %Y %H:%M:%S %Z']:
                    try:
                        return datetime.strptime(time_str, fmt)
                    except ValueError:
                        continue
        except Exception:
            pass
        
        return None
    
    def extract_title(self, entry: Dict) -> str:
        """
        提取标题
        
        Args:
            entry: RSS 条目
            
        Returns:
            标题字符串
        """
        return entry.get('title', '').strip()
    
    def extract_link(self, entry: Dict) -> str:
        """
        提取链接
        
        Args:
            entry: RSS 条目
            
        Returns:
            链接字符串
        """
        return entry.get('link', '')
    
    def extract_other_info(self, entry: Dict) -> Dict:
        """
        提取其他信息（摘要、作者、分类等）
        
        Args:
            entry: RSS 条目
            
        Returns:
            其他信息的字典
        """
        other_info = {
            'summary': entry.get('summary', entry.get('description', '')).strip(),
            'id': entry.get('id', entry.get('link', '')),
            'authors': self._extract_authors_generic(entry),
            'categories': self._extract_categories_generic(entry),
        }
        return other_info
    
    def _extract_authors_generic(self, entry) -> list:
        """
        提取作者信息（通用方法）
        
        Args:
            entry: RSS 条目
            
        Returns:
            作者列表
        """
        authors = []
        
        # 检查标准的 authors 字段
        if hasattr(entry, 'authors') and entry.authors:
            authors = [author.get('name', '') if isinstance(author, dict) else str(author) 
                       for author in entry.authors]
        # 检查 author 字段（单个）
        elif hasattr(entry, 'author') and entry.author:
            authors = [entry.author]
        # 从字典中获取
        elif isinstance(entry, dict):
            if 'authors' in entry:
                authors = entry['authors']
            elif 'author' in entry:
                authors = [entry['author']]
        
        # 清理作者名称
        cleaned_authors = [author.strip() for author in authors if author and author.strip()]
        return cleaned_authors
    
    def _extract_categories_generic(self, entry) -> list:
        """
        提取分类/标签（通用方法）
        
        Args:
            entry: RSS 条目
            
        Returns:
            分类列表
        """
        categories = []
        
        # 检查 tags 字段（feedparser 标准格式）
        if hasattr(entry, 'tags') and entry.tags:
            categories = [tag.get('term', '') if isinstance(tag, dict) else str(tag)
                         for tag in entry.tags]
        # 检查 category 字段
        elif hasattr(entry, 'category') and entry.category:
            if isinstance(entry.category, list):
                categories = [str(cat) for cat in entry.category]
            else:
                categories = [str(entry.category)]
        # 从字典中获取
        elif isinstance(entry, dict):
            if 'tags' in entry:
                tags = entry['tags']
                categories = [tag.get('term', '') if isinstance(tag, dict) else str(tag)
                           for tag in tags]
            elif 'category' in entry:
                cat = entry['category']
                categories = [cat] if isinstance(cat, str) else [str(c) for c in cat]
        
        # 清理分类名称
        cleaned_categories = [cat.strip() for cat in categories if cat and cat.strip()]
        return cleaned_categories
