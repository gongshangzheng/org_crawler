"""基础爬虫类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from ..models.site_config import SiteConfig
from ..models.crawl_result import CrawlResult
from ..models.crawl_item import CrawlItem


class BaseCrawler(ABC):
    """所有爬虫的基类"""
    
    def __init__(self, site_config: SiteConfig):
        """
        初始化爬虫
        
        Args:
            site_config: 网站配置
        """
        self.site_config = site_config
    
    @abstractmethod
    def crawl(self) -> CrawlResult:
        """
        执行爬取操作
        
        Returns:
            CrawlResult: 爬取结果
        """
        pass
    
    @abstractmethod
    def extract_published_time(self, entry: Dict) -> Optional[datetime]:
        """
        提取发布时间（每个爬虫需要实现自己的方法）
        
        Args:
            entry: 原始条目数据（可能是 RSS entry、HTML 元素等）
            
        Returns:
            datetime 对象，如果解析失败返回 None
        """
        pass
    
    @abstractmethod
    def extract_title(self, entry: Dict) -> str:
        """
        提取标题
        
        Args:
            entry: 原始条目数据
            
        Returns:
            标题字符串
        """
        pass
    
    @abstractmethod
    def extract_link(self, entry: Dict) -> str:
        """
        提取链接
        
        Args:
            entry: 原始条目数据
            
        Returns:
            链接字符串
        """
        pass
    
    @abstractmethod
    def extract_other_info(self, entry: Dict) -> Dict:
        """
        提取其他信息（摘要、作者、分类等）
        
        Args:
            entry: 原始条目数据
            
        Returns:
            其他信息的字典
        """
        pass
    
    def parse_entry(self, entry: Dict) -> Optional[CrawlItem]:
        """
        解析条目为 CrawlItem（通用方法，调用各个提取方法）
        
        Args:
            entry: 原始条目数据
            
        Returns:
            CrawlItem 对象，如果解析失败返回 None
        """
        try:
            published_time = self.extract_published_time(entry)
            if not published_time:
                return None
            
            title = self.extract_title(entry)
            link = self.extract_link(entry)
            other_info = self.extract_other_info(entry)
            
            return CrawlItem(
                title=title,
                link=link,
                published_time=published_time,
                other_info=other_info
            )
        except Exception:
            return None
    
    def filter_by_keywords(self, items: List[CrawlItem]) -> List[CrawlItem]:
        """
        根据关键词过滤条目，并将匹配的关键词存储到条目中
        
        Args:
            items: 条目列表
            
        Returns:
            过滤后的条目列表
        """
        if not self.site_config.keywords:
            return items
        
        filtered_items = []
        for item in items:
            # 检查标题和摘要中是否包含关键词
            title = item.title.lower()
            summary = item.summary.lower()
            content = f"{title} {summary}"
            
            # 找出所有匹配的关键词
            matched_keywords = []
            for keyword in self.site_config.keywords:
                if keyword.lower() in content:
                    matched_keywords.append(keyword)
            
            # 如果包含任一关键词，则保留
            if matched_keywords:
                # 将匹配的关键词存储到item中
                if 'keywords' not in item.other_info:
                    item.other_info['keywords'] = []
                # 合并关键词（去重）
                existing_keywords = item.other_info.get('keywords', [])
                if isinstance(existing_keywords, str):
                    existing_keywords = [existing_keywords]
                all_keywords = list(set(existing_keywords + matched_keywords))
                item.other_info['keywords'] = all_keywords
                filtered_items.append(item)
        
        return filtered_items

