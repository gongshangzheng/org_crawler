"""网站配置数据模型"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class SiteConfig:
    """网站配置类"""
    name: str                    # 网站名称（用于文件夹命名）
    url: str                     # 网站地址或 RSS 链接
    crawl_type: str             # 爬取类型：'rss' 或 'custom'
    update_frequency: int       # 更新频率（分钟）
    storage_path: str           # 存储路径（相对于 data/）
    enabled: bool               # 是否启用
    keywords: List[str] = field(default_factory=list)  # 关键词列表（用于过滤）
    custom_config: Dict = field(default_factory=dict)  # 自定义配置
    last_crawl_time: Optional[datetime] = None  # 最后爬取时间
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SiteConfig':
        """从字典创建 SiteConfig"""
        return cls(
            name=data['name'],
            url=data['url'],
            crawl_type=data['crawl_type'],
            update_frequency=data.get('update_frequency', 120),  # 默认 120 分钟
            storage_path=data['storage_path'],
            enabled=data.get('enabled', True),
            keywords=data.get('keywords', []),
            custom_config=data.get('custom_config', {}),
            last_crawl_time=None
        )

