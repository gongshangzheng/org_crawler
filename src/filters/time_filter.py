"""按时间范围过滤"""

from datetime import datetime, timedelta
from typing import Optional

from .base import BaseFilter
from ..models.crawl_item import CrawlItem


class TimeRangeFilter(BaseFilter):
    """
    按时间范围过滤：
    - 可以配置绝对时间 start / end（字符串）
    - 也可以配置相对时间 relative_days / relative_hours（相对于当前时间之前）
    - 支持 date_only 模式：只比较日期部分（忽略时分秒），适用于 ArXiv 等只有日期的时间
    - 支持 yesterday 快捷选项：自动设置为昨天的 00:00:00 到今天的 00:00:00
    - 支持 relative_days_start / relative_days_end：设置相对于今天的日期范围
    
    注意：时间区间为左开右闭 (start, end]，即：
    - start 时间点不包含（发布时间必须 > start）
    - end 时间点包含（发布时间必须 <= end）
    """

    def __init__(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        relative_days: Optional[int] = None,
        relative_hours: Optional[int] = None,
        relative_days_start: Optional[int] = None,
        relative_days_end: Optional[int] = None,
        yesterday: bool = False,
        date_only: bool = False,
        negate: bool = False,
    ):
        super().__init__(negate=negate)
        self.start_str = start
        self.end_str = end
        self.relative_days = relative_days
        self.relative_hours = relative_hours
        self.relative_days_start = relative_days_start
        self.relative_days_end = relative_days_end
        self.yesterday = yesterday
        self.date_only = date_only

    def _parse_datetime(self, value: str) -> Optional[datetime]:
        """尽量解析多种常见的时间格式"""
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _normalize_to_date(self, dt: datetime) -> datetime:
        """将时间标准化为当天的 00:00:00（用于日期比较）"""
        return datetime.combine(dt.date(), datetime.min.time())

    def _get_range(self) -> (Optional[datetime], Optional[datetime]):
        now = datetime.now()
        today_start = self._normalize_to_date(now)

        start_dt = None
        end_dt = None

        # yesterday 快捷选项：昨天的 00:00:00 到今天的 00:00:00
        if self.yesterday:
            yesterday_start = today_start - timedelta(days=1)
            start_dt = yesterday_start
            end_dt = today_start
            return start_dt, end_dt

        # relative_days_start / relative_days_end：相对于今天的日期范围
        if self.relative_days_start is not None or self.relative_days_end is not None:
            if self.relative_days_start is not None:
                start_dt = today_start - timedelta(days=self.relative_days_start)
            if self.relative_days_end is not None:
                end_dt = today_start - timedelta(days=self.relative_days_end)
            # 如果只设置了 start，end 默认为今天
            if start_dt and end_dt is None:
                end_dt = today_start
            return start_dt, end_dt

        # 绝对时间优先
        if self.start_str:
            start_dt = self._parse_datetime(self.start_str)
            if self.date_only and start_dt:
                start_dt = self._normalize_to_date(start_dt)
        if self.end_str:
            end_dt = self._parse_datetime(self.end_str)
            if self.date_only and end_dt:
                end_dt = self._normalize_to_date(end_dt)

        # 相对时间（相对于当前时间向前推）
        if self.relative_days is not None:
            start_dt = now - timedelta(days=self.relative_days)
            if self.date_only:
                start_dt = self._normalize_to_date(start_dt)
        if self.relative_hours is not None:
            start_dt = now - timedelta(hours=self.relative_hours)
            if self.date_only:
                start_dt = self._normalize_to_date(start_dt)

        return start_dt, end_dt

    def get_range_str(self) -> str:
        """
        获取时间范围的字符串表示，用于日志输出
        
        Returns:
            时间范围的字符串描述（说明区间为左开右闭）
        """
        start_dt, end_dt = self._get_range()
        
        if start_dt and end_dt:
            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            mode_str = "（仅日期）" if self.date_only else ""
            return f"({start_str}, {end_str}]{mode_str}（左开右闭）"
        elif start_dt:
            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            mode_str = "（仅日期）" if self.date_only else ""
            return f"({start_str}, +∞){mode_str}（左开）"
        elif end_dt:
            end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            mode_str = "（仅日期）" if self.date_only else ""
            return f"(-∞, {end_str}]{mode_str}（右闭）"
        else:
            return "无时间限制"

    def match(self, item: CrawlItem) -> bool:
        """
        判断条目是否匹配时间范围
        
        时间区间为左开右闭 (start, end]：
        - start_dt < pub <= end_dt
        - 即：pub > start_dt 且 pub <= end_dt
        """
        start_dt, end_dt = self._get_range()
        pub = item.published_time
        if not isinstance(pub, datetime):
            return False

        # 如果启用 date_only，将发布时间也标准化为当天的 00:00:00
        if self.date_only:
            pub = self._normalize_to_date(pub)

        # 左开：发布时间必须 > start_dt（不包含 start_dt）
        if start_dt and pub <= start_dt:
            return False
        # 右闭：发布时间必须 <= end_dt（包含 end_dt）
        if end_dt and pub > end_dt:
            return False
        return True


