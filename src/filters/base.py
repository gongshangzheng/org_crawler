"""过滤器基类"""

from abc import ABC, abstractmethod
from typing import List

from ..models.crawl_item import CrawlItem


class BaseFilter(ABC):
    """过滤器基类，支持可选反选（negate）"""

    def __init__(self, negate: bool = False):
        """
        Args:
            negate: 是否反选。如果为 True，则匹配结果取反。
        """
        self.negate = negate

    def apply(self, items: List[CrawlItem]) -> List[CrawlItem]:
        """对一组条目应用过滤器"""
        result: List[CrawlItem] = []
        for item in items:
            matched = self.match(item)
            if self.negate:
                matched = not matched
            if matched:
                result.append(item)
        return result

    @abstractmethod
    def match(self, item: CrawlItem) -> bool:
        """判断单个条目是否匹配过滤条件"""
        raise NotImplementedError


