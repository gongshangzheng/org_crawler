"""爬取结果数据模型"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class CrawlResult:
    """爬取结果类"""
    site_name: str
    crawl_time: datetime
    items_count: int
    items: List[Dict] = field(default_factory=list)  # 爬取到的条目列表
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'site_name': self.site_name,
            'crawl_time': self.crawl_time.isoformat(),
            'items_count': self.items_count,
            'items': self.items,
            'success': self.success,
            'error_message': self.error_message
        }

